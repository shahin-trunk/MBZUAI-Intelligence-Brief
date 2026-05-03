#!/usr/bin/env python3.11
"""A/B eval harness for the Ghostwriter prompt.

Replays saved fixtures through two Ghostwriter prompt versions, runs
automated quality checks on each output, and optionally asks Claude to
pick a winner in blind paired comparison.

Purpose
-------

This exists to gate prompt-refactor work with objective signal. The
current card-language quality is validated by human spot-check, which
is slow and biased. A refactor that shortens the prompt to ~45% of its
current length must demonstrably *not* regress quality before it ships.

Usage
-----

    cd backend && python -m evals.eval_ghostwriter_ab \\
        --v1 prompts/ghostwriter_prompt.md \\
        --v2 prompts/ghostwriter_prompt_v2.md

    # Baseline sanity: v1 against itself — all checks should pass.
    cd backend && python -m evals.eval_ghostwriter_ab \\
        --v1 prompts/ghostwriter_prompt.md \\
        --v2 prompts/ghostwriter_prompt.md

    # Skip the LLM-as-judge pass (faster, free).
    cd backend && python -m evals.eval_ghostwriter_ab ... --no-judge

Outputs
-------

* ``backend/evals/output/ghostwriter/{date}_v1.json`` / ``{date}_v2.json``
  — raw parsed Ghostwriter outputs per fixture.
* ``backend/evals/output/ghostwriter/report.md`` — scoreboard + paired
  diff of analysis prose per item for human review.
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import random
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

import anthropic

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
REPO_ROOT = PROJECT_ROOT
PROMPTS_DIR = REPO_ROOT / "prompts"
FIXTURE_DIR = BACKEND_DIR / "tests" / "fixtures" / "prompt_refactor" / "ghostwriter"
OUTPUT_DIR = BACKEND_DIR / "evals" / "output" / "ghostwriter"

JUDGE_MODEL = "claude-sonnet-4-6"
# The eval calls the production router (pipeline.card_batch) which handles
# Ghostwriter invocation internally. GHOSTWRITER_MODEL / GHOSTWRITER_MAX_TOKENS
# no longer live here — they're set by the router to match production.

# Scan thresholds and banned phrases are imported from the validator module
# (pipeline.ghostwriter_validate) once backend/ is on sys.path. That keeps
# the eval and the runtime validator honest — one list, not two.
# The actual imports happen just below, after sys.path is set up.


# ----------------------------------------------------------------------
# Env / IO
# ----------------------------------------------------------------------


def _load_env() -> None:
    # override=True so an empty ANTHROPIC_API_KEY="" in the shell doesn't
    # prevent the real key in the .env file from loading.
    candidates: list[Path] = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "frontend" / ".env.local",
    ]
    parts = PROJECT_ROOT.parts
    if ".claude" in parts and "worktrees" in parts:
        i = parts.index(".claude")
        main_repo = Path(*parts[:i])
        candidates.extend([main_repo / ".env", main_repo / "frontend" / ".env.local"])
    for p in candidates:
        if p.exists():
            load_dotenv(p, override=True)


# ----------------------------------------------------------------------
# Router-based Ghostwriter call
# ----------------------------------------------------------------------

# Make backend/ importable so we can reach pipeline.card_batch and
# pipeline.ghostwriter_validate (canonical BANNED_PHRASES source).
sys.path.insert(0, str(BACKEND_DIR))

from pipeline.card_batch import route_and_run_card_agents  # noqa: E402
from pipeline.ghostwriter_validate import (  # noqa: E402
    BANNED_PHRASES,
    DEPTH_BUDGETS,
    MAX_SENTENCE_WORDS,
)

BANNED_REGEX = [re.compile(p, re.IGNORECASE) for p in BANNED_PHRASES]


async def _call_router(
    client: anthropic.AsyncAnthropic,
    gatekeeper_input: dict,
    date: str,
    prompt_path: Path,
) -> dict:
    """Call the production Ghostwriter router with a specific prompt file.

    ``route_and_run_card_agents`` is the same entry point the orchestrator
    uses. ``prompt_path`` may be any absolute path — the enhanced
    ``load_prompt`` resolves absolute paths directly so we can test
    alternate prompt files without copying them into ``PROMPTS_DIR``.
    """
    result, _usage = await route_and_run_card_agents(
        client=client,
        gatekeeper_payload=gatekeeper_input,
        today=date,
        standard_prompt_filename=str(prompt_path),
        include_dropped=False,
    )
    if result is None:
        return {"items": []}
    return result


# ----------------------------------------------------------------------
# Automated checks
# ----------------------------------------------------------------------


def _count_words(text: str) -> int:
    return len((text or "").split())


def _split_sentences(text: str) -> list[str]:
    """Rough sentence split — good enough for length checks."""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


def _max_sentence_words(text: str) -> int:
    lens = [_count_words(s) for s in _split_sentences(text)]
    return max(lens) if lens else 0


def _count_banned_hits(text: str) -> list[str]:
    hits: list[str] = []
    for rx in BANNED_REGEX:
        for m in rx.finditer(text or ""):
            hits.append(m.group(0))
    return hits


def _check_headline(h: str) -> list[str]:
    issues: list[str] = []
    if _count_words(h) > 15:
        issues.append(f"headline >15 words ({_count_words(h)})")
    if ";" in h:
        issues.append("headline contains ';'")
    # Allow colons in quoted strings but not as subtitle separator
    if re.search(r"(?<!\"):(?!\")", h):
        issues.append("headline contains ':'")
    for junction in (" amid ", " as "):
        if junction.lower() in f" {h.lower()} ":
            issues.append(f"headline uses '{junction.strip()}' as clause joiner")
    return issues


def check_item(input_item: dict, out_item: dict) -> dict:
    """Run all automated checks on a single Ghostwriter output item."""
    analysis = out_item.get("analysis") or ""
    bullets = out_item.get("key_bullets") or []
    bullets_text = " ".join(bullets)
    depth = out_item.get("depth") or "standard"
    budget = DEPTH_BUDGETS.get(depth, DEPTH_BUDGETS["standard"])
    analysis_words = _count_words(analysis)
    bullets_words = _count_words(bullets_text)
    total_words = analysis_words + bullets_words

    banned_hits = _count_banned_hits(analysis) + _count_banned_hits(bullets_text)
    max_sent = _max_sentence_words(analysis)
    headline_issues = _check_headline(out_item.get("headline", ""))

    # Hallucination heuristic: numbers in analysis should also appear in raw_content.
    raw = input_item.get("raw_content") or ""
    nums_in_analysis = set(re.findall(r"\b\d[\d,.]*\b", analysis))
    nums_in_bullets = set(re.findall(r"\b\d[\d,.]*\b", bullets_text))
    nums_in_raw = set(re.findall(r"\b\d[\d,.]*\b", raw))
    number_nothallucinated = [
        n for n in (nums_in_analysis | nums_in_bullets) if n not in nums_in_raw
    ]

    return {
        "id": input_item.get("id"),
        "headline": out_item.get("headline", ""),
        "depth": depth,
        "analysis_words": analysis_words,
        "bullets_words": bullets_words,
        "total_words": total_words,
        "budget": budget,
        "budget_exceeded": total_words > budget,
        "max_sentence_words": max_sent,
        "sentence_over_cap": max_sent > MAX_SENTENCE_WORDS,
        "banned_hits": banned_hits,
        "headline_issues": headline_issues,
        "unverified_numbers": number_nothallucinated,
    }


# ----------------------------------------------------------------------
# LLM-as-judge
# ----------------------------------------------------------------------


JUDGE_PROMPT = """\
You are evaluating two versions of a card for an intelligence brief
delivered to a university president. The president reads this once, at
6am, in under 15 minutes. Good cards are direct, concrete, and useful.
Bad cards are padded, hedgy, chatty, or read like a consulting deck.

Here are the two versions of the same card. They share the exact same
source facts — only voice differs.

VERSION A:
{a}

VERSION B:
{b}

Pick the version that is clearly better for this reader. Your response
must be a single JSON object with these keys:

  "winner": "A" | "B" | "tie"
  "reason": one sentence under 30 words

Return ONLY the JSON object, no markdown.
"""


async def judge_pair(
    client: anthropic.AsyncAnthropic,
    a_item: dict,
    b_item: dict,
) -> dict:
    """Ask Claude to pick a winner between two card versions (blind A/B)."""
    def _render(it: dict) -> str:
        parts = []
        parts.append(f"Headline: {it.get('headline', '')}")
        bullets = it.get("key_bullets") or []
        for b in bullets:
            parts.append(f"- {b}")
        parts.append("")
        parts.append(it.get("analysis", ""))
        return "\n".join(parts)

    # Blind the sides — randomize which output is labeled "A" per call.
    flip = random.random() < 0.5
    first, second = (b_item, a_item) if flip else (a_item, b_item)
    prompt = JUDGE_PROMPT.format(a=_render(first), b=_render(second))
    resp = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
    obj = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        parsed = json.loads(obj.group(0) if obj else text)
    except Exception:
        parsed = {"winner": "tie", "reason": "judge parse failure"}

    # Un-flip the winner label back to v1/v2.
    raw_winner = (parsed.get("winner") or "tie").upper()
    if flip:
        mapping = {"A": "v2", "B": "v1", "TIE": "tie"}
    else:
        mapping = {"A": "v1", "B": "v2", "TIE": "tie"}
    return {
        "winner": mapping.get(raw_winner, "tie"),
        "reason": parsed.get("reason", "").strip(),
    }


# ----------------------------------------------------------------------
# Report rendering
# ----------------------------------------------------------------------


def _summarize(checks: list[dict]) -> dict:
    n = max(len(checks), 1)
    return {
        "items": len(checks),
        "banned_hits_total": sum(len(c["banned_hits"]) for c in checks),
        "sentence_overcap": sum(1 for c in checks if c["sentence_over_cap"]),
        "budget_exceeded": sum(1 for c in checks if c["budget_exceeded"]),
        "headline_failures": sum(1 for c in checks if c["headline_issues"]),
        "unverified_number_items": sum(1 for c in checks if c["unverified_numbers"]),
        "median_words": sorted(c["total_words"] for c in checks)[n // 2],
    }


def _diff_block(a: str, b: str, width: int = 100) -> str:
    """Short unified diff between two strings of prose."""
    a_lines = (a or "").splitlines() or [""]
    b_lines = (b or "").splitlines() or [""]
    diff = difflib.unified_diff(
        a_lines, b_lines, fromfile="v1", tofile="v2", lineterm="", n=1
    )
    return "\n".join(diff)


def render_report(
    fixture_dates: list[str],
    per_fixture: dict,
    judge_scores: dict | None,
) -> str:
    lines: list[str] = []
    lines.append("# Ghostwriter prompt A/B eval report")
    lines.append("")
    lines.append(f"Fixtures: {len(fixture_dates)} dates — {', '.join(fixture_dates)}")
    lines.append("")

    # Aggregate
    agg_v1 = {k: 0 for k in ("items", "banned_hits_total", "sentence_overcap",
                              "budget_exceeded", "headline_failures",
                              "unverified_number_items")}
    agg_v2 = dict(agg_v1)
    all_words_v1: list[int] = []
    all_words_v2: list[int] = []
    for date, per in per_fixture.items():
        s1, s2 = per["summary_v1"], per["summary_v2"]
        for k in agg_v1:
            agg_v1[k] += s1[k]
            agg_v2[k] += s2[k]
        all_words_v1.extend(c["total_words"] for c in per["checks_v1"])
        all_words_v2.extend(c["total_words"] for c in per["checks_v2"])

    def _median(xs: list[int]) -> int:
        if not xs:
            return 0
        xs_sorted = sorted(xs)
        return xs_sorted[len(xs_sorted) // 2]

    lines.append("## Aggregate")
    lines.append("")
    lines.append("| metric | v1 | v2 | delta |")
    lines.append("|---|---|---|---|")
    for label, key in [
        ("items total", "items"),
        ("banned-phrase hits", "banned_hits_total"),
        ("sentences >25 words", "sentence_overcap"),
        ("cards over word budget", "budget_exceeded"),
        ("headline-rule failures", "headline_failures"),
        ("cards with unverified numbers", "unverified_number_items"),
    ]:
        lines.append(f"| {label} | {agg_v1[key]} | {agg_v2[key]} | {agg_v2[key] - agg_v1[key]:+d} |")
    lines.append(
        f"| median total words/card | {_median(all_words_v1)} | {_median(all_words_v2)} "
        f"| {_median(all_words_v2) - _median(all_words_v1):+d} |"
    )
    lines.append("")

    if judge_scores is not None:
        total = sum(judge_scores.values())
        lines.append("## LLM-as-judge (blind paired)")
        lines.append("")
        lines.append(f"v1 wins: **{judge_scores.get('v1', 0)}** / {total}")
        lines.append(f"v2 wins: **{judge_scores.get('v2', 0)}** / {total}")
        lines.append(f"ties: **{judge_scores.get('tie', 0)}** / {total}")
        margin = judge_scores.get("v2", 0) - judge_scores.get("v1", 0)
        pct = (margin / total * 100) if total else 0
        lines.append(f"margin: {margin:+d} ({pct:+.1f}pp)")
        lines.append("")

    # Per-fixture detail
    for date in fixture_dates:
        per = per_fixture[date]
        lines.append(f"## {date}")
        lines.append("")
        for c1, c2, it_v1, it_v2 in zip(
            per["checks_v1"], per["checks_v2"], per["items_v1"], per["items_v2"]
        ):
            lines.append(f"### {c1['headline']}")
            lines.append("")
            lines.append(
                f"- depth: {c1['depth']}  |  words v1/v2: {c1['total_words']}/{c2['total_words']} "
                f"(budget {c1['budget']})"
            )
            lines.append(
                f"- max sentence v1/v2: {c1['max_sentence_words']}/{c2['max_sentence_words']} words"
            )
            if c1["banned_hits"] or c2["banned_hits"]:
                lines.append(f"- banned hits v1: {c1['banned_hits']}")
                lines.append(f"- banned hits v2: {c2['banned_hits']}")
            if c1["headline_issues"] or c2["headline_issues"]:
                lines.append(f"- headline v1: {c1['headline_issues']}")
                lines.append(f"- headline v2: {c2['headline_issues']}")
            if c1["unverified_numbers"] or c2["unverified_numbers"]:
                lines.append(f"- unverified numbers v1: {c1['unverified_numbers']}")
                lines.append(f"- unverified numbers v2: {c2['unverified_numbers']}")
            lines.append("")
            lines.append("**v1 analysis:**")
            lines.append(f"> {it_v1.get('analysis','').strip()}")
            lines.append("")
            lines.append("**v2 analysis:**")
            lines.append(f"> {it_v2.get('analysis','').strip()}")
            lines.append("")
            lines.append("---")
            lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--v1", type=Path, required=True, help="Baseline prompt .md")
    p.add_argument("--v2", type=Path, required=True, help="Candidate prompt .md")
    p.add_argument(
        "--fixtures",
        type=Path,
        default=FIXTURE_DIR,
        help=f"Fixture directory (default: {FIXTURE_DIR}).",
    )
    p.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip the LLM-as-judge paired comparison.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR}).",
    )
    p.add_argument(
        "--limit-items-per-fixture",
        type=int,
        default=None,
        help="Optional cap on items judged per fixture (saves tokens for judge pass).",
    )
    return p.parse_args()


async def run() -> int:
    args = parse_args()
    _load_env()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    fixture_files = sorted(args.fixtures.glob("*.json"))
    if not fixture_files:
        print(f"ERROR: no fixtures found in {args.fixtures}", file=sys.stderr)
        return 1

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    per_fixture: dict[str, dict] = {}
    judge_scores = {"v1": 0, "v2": 0, "tie": 0}
    fixture_dates: list[str] = []

    for path in fixture_files:
        fx = json.loads(path.read_text(encoding="utf-8"))
        date = fx["date"]
        fixture_dates.append(date)
        print(f"\n== {date} ==")
        gk = fx["gatekeeper_input"]

        # Call the production router for each version. The router
        # partitions items by is_model_release (currently a pass-through;
        # model-release branch lands in Step 3 of the refactor) and runs
        # the full retry/ID-contract machinery the orchestrator uses.
        print(f"  v1={args.v1.name}  v2={args.v2.name}")
        out_v1_task = asyncio.create_task(_call_router(client, gk, date, args.v1))
        out_v2_task = asyncio.create_task(_call_router(client, gk, date, args.v2))
        out_v1, out_v2 = await asyncio.gather(out_v1_task, out_v2_task)
        items_v1 = out_v1.get("items") or []
        items_v2 = out_v2.get("items") or []
        print(f"  items v1: {len(items_v1)}  v2: {len(items_v2)}")

        (args.out / f"{date}_v1.json").write_text(
            json.dumps(out_v1, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (args.out / f"{date}_v2.json").write_text(
            json.dumps(out_v2, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Align outputs by id (order may drift).
        def _by_id(items: list[dict]) -> dict[str, dict]:
            return {it.get("id"): it for it in items if it.get("id")}

        by1 = _by_id(items_v1)
        by2 = _by_id(items_v2)
        input_by_id = {it["id"]: it for it in gk["selected"]}
        checks_v1: list[dict] = []
        checks_v2: list[dict] = []
        aligned_v1: list[dict] = []
        aligned_v2: list[dict] = []
        for item_id in gk["allowed_ids"]:
            inp = input_by_id.get(item_id)
            if not inp:
                continue
            v1_it = by1.get(item_id) or {}
            v2_it = by2.get(item_id) or {}
            if not v1_it or not v2_it:
                continue
            aligned_v1.append(v1_it)
            aligned_v2.append(v2_it)
            checks_v1.append(check_item(inp, v1_it))
            checks_v2.append(check_item(inp, v2_it))

        per_fixture[date] = {
            "items_v1": aligned_v1,
            "items_v2": aligned_v2,
            "checks_v1": checks_v1,
            "checks_v2": checks_v2,
            "summary_v1": _summarize(checks_v1),
            "summary_v2": _summarize(checks_v2),
        }

        if not args.no_judge:
            pairs = list(zip(aligned_v1, aligned_v2))
            if args.limit_items_per_fixture:
                pairs = pairs[: args.limit_items_per_fixture]
            judgements = await asyncio.gather(
                *(judge_pair(client, a, b) for a, b in pairs)
            )
            for j in judgements:
                judge_scores[j["winner"]] = judge_scores.get(j["winner"], 0) + 1
            print(
                f"  judge this fixture: "
                f"v1={sum(1 for j in judgements if j['winner']=='v1')} "
                f"v2={sum(1 for j in judgements if j['winner']=='v2')} "
                f"tie={sum(1 for j in judgements if j['winner']=='tie')}"
            )

    report = render_report(
        fixture_dates,
        per_fixture,
        None if args.no_judge else judge_scores,
    )
    report_path = args.out / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nWrote {report_path}")
    print(f"Aggregate judge: {judge_scores}" if not args.no_judge else "(judge skipped)")
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
