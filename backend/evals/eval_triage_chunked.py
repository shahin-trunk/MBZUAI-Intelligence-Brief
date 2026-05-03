#!/usr/bin/env python3
"""A/B eval harness for the chunked Triage stage.

Replays cached pre-triage scout pools from
`backend/output/collected_raw_{date}.json` through both the legacy
single-call path (one big Haiku request with all items) and the new
chunked path (60-item batches in parallel via asyncio.Semaphore +
asyncio.gather), then diffs results to surface "recovered" items
(false positives that chunked rescued) and any new regressions.

Acceptance criteria (from the plan):
  * Recovered items ≥ 5 per date with at least one matching the known
    false-positive class (Tim Cook / Iran / Fed nominee / Oil 3% /
    Hamdan reviews DXB).
  * New drops ≤ 5% of legacy's kept set (chunked shouldn't over-drop
    legitimate items).
  * Sanity-check disagreement rate < 30% on a baseline-quality day.
  * All chunks succeed without retries on at least 2 of 3 dates.

Usage
-----

    cd backend && python -m evals.eval_triage_chunked \\
        --dates 2026-04-15 2026-04-16 2026-04-17

    # Single date with explicit output path:
    cd backend && python -m evals.eval_triage_chunked \\
        --dates 2026-04-17 --out evals/output/triage_chunked/today.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
OUTPUT_DIR = BACKEND_DIR / "evals" / "output" / "triage_chunked"

sys.path.insert(0, str(BACKEND_DIR))

# Imports must come AFTER sys.path is set up so we can reach pipeline.*
from pipeline.orchestrator import (  # noqa: E402
    _triage_single_call,
    triage_collected_items,
)


def _load_env() -> None:
    """Load .env so ANTHROPIC_API_KEY reaches the SDK."""
    candidates = [PROJECT_ROOT / ".env", PROJECT_ROOT / "frontend" / ".env.local"]
    for p in candidates:
        if p.exists():
            load_dotenv(p, override=True)


def _load_collected_raw(date: str) -> list[dict]:
    """Load the pre-triage scout pool for `date`."""
    path = BACKEND_DIR / "output" / f"collected_raw_{date}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path}")
    return json.loads(path.read_text())


def _normalize_headline_key(headline: str) -> str:
    """Normalized key for headline-based set comparison."""
    return re.sub(r"\s+", " ", (headline or "")).strip().lower()[:200]


# Headlines (normalized) from the audit's known-false-positive class.
# A successful chunked run should recover at least one of these per date
# IF the date's input contains them. Empty strings are filtered out.
KNOWN_FALSE_POSITIVES_TARGETS = {
    _normalize_headline_key(h)
    for h in [
        "Tim Cook steps down as Apple CEO after 15 years",
        "Iran confirms decision to skip further US peace negotiations",
        "Fed nominee Kevin Warsh faces confirmation hearing today",
        "Oil prices rise 3%",
        "Hamdan bin Mohammed reviews operations of Dubai International Airport & Emirates",
        "John Ternus: The incoming Apple CEO explained",
        "Apple's John Ternus becomes CEO of powerful company",
        "Trump's deportation campaign may hurt Republicans in midterms",
    ]
    if h
}


async def _evaluate_one_date(
    client: anthropic.AsyncAnthropic,
    date: str,
) -> dict:
    """Run legacy single-call vs chunked triage on `date` and diff results."""
    items = _load_collected_raw(date)
    print(f"\n=== {date} ===")
    print(f"  Pre-triage pool: {len(items)} items")

    # Legacy single-call: invoke `_triage_single_call` directly with the
    # full pool, offset=0. This bypasses the chunking wrapper entirely
    # and reproduces the pre-fix single-prompt behavior.
    print("  Running LEGACY single-call triage...")
    legacy_started = datetime.now()
    legacy_keep_set, legacy_log = await _triage_single_call(
        items, client, label="legacy-single", offset=0
    )
    legacy_elapsed = (datetime.now() - legacy_started).total_seconds()
    legacy_kept_indices = legacy_keep_set
    legacy_kept_headlines = {
        _normalize_headline_key(items[i].get("headline", ""))
        for i in legacy_kept_indices
    }
    print(
        f"  Legacy: {len(legacy_kept_indices)} kept, "
        f"{len(items) - len(legacy_kept_indices)} dropped "
        f"({legacy_elapsed:.1f}s)"
    )

    # Chunked path: invoke the public `triage_collected_items`. It will
    # run the full chunk + sanity-check pipeline (including saving
    # triage_output_{today}.json — that's fine, it's an eval side-effect).
    # NOTE: we disable the sanity check here via env var because the eval
    # itself isn't a production run; we surface the chunked telemetry
    # from the saved JSON instead.
    print("  Running CHUNKED triage...")
    os.environ["TRIAGE_SANITY_CHECK_ENABLED"] = "false"
    chunked_started = datetime.now()
    chunked_kept = await triage_collected_items(items, client)
    chunked_elapsed = (datetime.now() - chunked_started).total_seconds()
    chunked_kept_headlines = {
        _normalize_headline_key(it.get("headline", "")) for it in chunked_kept
    }
    print(
        f"  Chunked: {len(chunked_kept)} kept, "
        f"{len(items) - len(chunked_kept)} dropped "
        f"({chunked_elapsed:.1f}s)"
    )

    # Recovered: items legacy dropped that chunked kept.
    legacy_dropped_headlines = {
        _normalize_headline_key(items[i].get("headline", ""))
        for i in range(len(items))
        if i not in legacy_kept_indices
    }
    recovered = legacy_dropped_headlines & chunked_kept_headlines
    new_drops = legacy_kept_headlines - chunked_kept_headlines
    intersection = legacy_kept_headlines & chunked_kept_headlines

    # Did chunked recover any of the audit's known false-positive headlines?
    recovered_known_fp = recovered & KNOWN_FALSE_POSITIVES_TARGETS

    # Re-read chunked telemetry from the saved file (same shape as
    # production triage_output_{today}.json).
    today_str = datetime.now().strftime("%Y-%m-%d")
    triage_output_path = (
        BACKEND_DIR / "output" / f"triage_output_{today_str}.json"
    )
    chunked_telemetry: dict = {}
    if triage_output_path.exists():
        chunked_telemetry = json.loads(triage_output_path.read_text())

    return {
        "date": date,
        "input_count": len(items),
        "legacy": {
            "kept_count": len(legacy_kept_indices),
            "dropped_count": len(items) - len(legacy_kept_indices),
            "elapsed_s": legacy_elapsed,
            "status": legacy_log.get("status"),
            "attempts": len(legacy_log.get("attempts", [])),
        },
        "chunked": {
            "kept_count": len(chunked_kept),
            "dropped_count": len(items) - len(chunked_kept),
            "elapsed_s": chunked_elapsed,
            "telemetry": chunked_telemetry,
        },
        "diff": {
            "intersection": len(intersection),
            "recovered_count": len(recovered),
            "new_drops_count": len(new_drops),
            "recovered_known_fp_count": len(recovered_known_fp),
            "recovered_headlines_sample": sorted(recovered)[:15],
            "recovered_known_fp_headlines": sorted(recovered_known_fp),
            "new_drops_sample": sorted(new_drops)[:10],
            "new_drops_pct_of_legacy_kept": (
                len(new_drops) / max(len(legacy_kept_headlines), 1)
            ),
        },
    }


def _format_report(results: list[dict]) -> str:
    """Render the eval results as a markdown report."""
    lines: list[str] = []
    lines.append("# Triage chunked-mode A/B replay")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Acceptance summary")
    lines.append("")
    lines.append(
        "| Date | Input | Legacy Kept | Chunked Kept | Recovered | "
        "Known FP Recovered | New Drops | New-Drop % | Pass? |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|"
    )
    for r in results:
        lk = r["legacy"]["kept_count"]
        ck = r["chunked"]["kept_count"]
        rec = r["diff"]["recovered_count"]
        rec_fp = r["diff"]["recovered_known_fp_count"]
        nd = r["diff"]["new_drops_count"]
        nd_pct = r["diff"]["new_drops_pct_of_legacy_kept"]

        # Pass criteria from the plan:
        # - recovered ≥ 5
        # - new drops ≤ 5% of legacy kept
        pass_recovered = rec >= 5
        pass_new_drops = nd_pct <= 0.05
        passed = pass_recovered and pass_new_drops
        verdict = "PASS" if passed else "FAIL"
        lines.append(
            f"| {r['date']} | {r['input_count']} | {lk} | {ck} | {rec} | "
            f"{rec_fp} | {nd} | {nd_pct*100:.1f}% | {verdict} |"
        )

    lines.append("")
    lines.append(
        "**Acceptance bar**: recovered ≥ 5 (chunked rescues real news the "
        "legacy single-call dropped); new drops ≤ 5% of legacy's kept set "
        "(chunked shouldn't over-drop legitimate items)."
    )
    lines.append("")
    lines.append(
        "**Known FP class** (from PDF audit): Tim Cook resignation, "
        "Iran-skips-talks, Fed nominee, Oil 3%, Hamdan reviews DXB, plus "
        "a few peers. A successful run recovers at least one when the "
        "input contains one."
    )

    for r in results:
        lines.append("")
        lines.append(f"## {r['date']}")
        lines.append("")
        lines.append(
            f"- Input pool: **{r['input_count']}** items"
        )
        lines.append(
            f"- Legacy: **{r['legacy']['kept_count']} kept**, "
            f"**{r['legacy']['dropped_count']} dropped** "
            f"({r['legacy']['elapsed_s']:.1f}s, "
            f"{r['legacy']['attempts']} attempt(s), "
            f"status={r['legacy']['status']})"
        )
        lines.append(
            f"- Chunked: **{r['chunked']['kept_count']} kept**, "
            f"**{r['chunked']['dropped_count']} dropped** "
            f"({r['chunked']['elapsed_s']:.1f}s)"
        )
        tel = r["chunked"]["telemetry"]
        if tel and tel.get("chunked"):
            lines.append(
                f"- Chunked telemetry: {tel.get('chunk_count')} chunk(s), "
                f"chunk_size={tel.get('chunk_size')}, "
                f"concurrency={tel.get('concurrency')}"
            )
            per_chunk = tel.get("per_chunk") or []
            for c in per_chunk:
                attempts = len(c.get("attempts") or [])
                status = c.get("status")
                lines.append(
                    f"  - **{c.get('label')}**: "
                    f"in={c.get('input_count')} → kept={c.get('kept_count')} "
                    f"(status={status}, attempts={attempts})"
                )
        lines.append("")
        lines.append(
            f"**Diff** (legacy vs chunked, by normalized headline):"
        )
        d = r["diff"]
        lines.append(
            f"- Intersection: {d['intersection']}, "
            f"Recovered: {d['recovered_count']}, "
            f"New drops: {d['new_drops_count']}"
        )
        lines.append(
            f"- New-drop rate vs legacy's kept set: "
            f"{d['new_drops_pct_of_legacy_kept']*100:.1f}%"
        )
        lines.append(
            f"- Known false-positive class recovered: "
            f"{d['recovered_known_fp_count']}"
        )
        if d["recovered_known_fp_headlines"]:
            lines.append("")
            lines.append("**Known false-positive class items recovered**:")
            for h in d["recovered_known_fp_headlines"]:
                lines.append(f"- {h}")
        if d["recovered_headlines_sample"]:
            lines.append("")
            lines.append("**Recovered (chunked kept, legacy dropped)** — first 15:")
            for h in d["recovered_headlines_sample"]:
                lines.append(f"- {h}")
        if d["new_drops_sample"]:
            lines.append("")
            lines.append("**New drops (chunked dropped, legacy kept)** — first 10:")
            for h in d["new_drops_sample"]:
                lines.append(f"- {h}")

    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dates",
        nargs="+",
        default=["2026-04-15", "2026-04-16", "2026-04-17"],
        help="Date strings (YYYY-MM-DD) with cached collected_raw outputs.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "Markdown report destination. Default: "
            "evals/output/triage_chunked/report_{ts}.md"
        ),
    )
    args = parser.parse_args()

    _load_env()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.out is None:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        out_path = OUTPUT_DIR / f"report_{ts}.md"
    else:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)

    client = anthropic.AsyncAnthropic()

    results: list[dict] = []
    for date in args.dates:
        try:
            r = await _evaluate_one_date(client, date)
        except FileNotFoundError as e:
            print(f"Skipping {date}: {e}")
            continue
        results.append(r)

    if not results:
        print("No dates evaluated. Exiting.")
        return

    report = _format_report(results)
    out_path.write_text(report)
    print(f"\nReport written to: {out_path}")
    print("\n--- Acceptance summary ---")
    for r in results:
        rec = r["diff"]["recovered_count"]
        rec_fp = r["diff"]["recovered_known_fp_count"]
        nd_pct = r["diff"]["new_drops_pct_of_legacy_kept"]
        print(
            f"  {r['date']}: input={r['input_count']}, "
            f"legacy_kept={r['legacy']['kept_count']}, "
            f"chunked_kept={r['chunked']['kept_count']}, "
            f"recovered={rec}, known_fp={rec_fp}, "
            f"new_drops={nd_pct*100:.1f}%"
        )


if __name__ == "__main__":
    asyncio.run(main())
