#!/usr/bin/env python3
"""Shadow-replay the content filter against historical pipeline output.

Loads `scout_output_raw_{date}.json` (post-dedup, pre-content-filter items)
and `content_filter_output_{date}.json` (prior-prompt verdicts) from
`backend/output/`, then runs the same items through the CURRENT prompt
pointed to by `--new-prompt` and diffs the verdicts.

Does NOT touch Supabase, does NOT run the full pipeline. Pure local
evaluation harness for the content-filter refactor (see
~/.claude/plans/good-please-make-a-cheeky-nebula.md).

Usage:
    cd backend
    python3 scripts/content_filter_shadow_replay.py \
        --dates 2026-04-17 2026-04-16 2026-04-15 2026-04-09 \
        --new-prompt prompts/content_filter_prompt.md

Output: one `content_filter_shadow_{date}.json` per date in backend/output/.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Make the backend package importable regardless of cwd
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_project_env  # noqa: E402

# Load root .env (ANTHROPIC_API_KEY, etc.) before importing config, which
# reads those values at import time.
load_project_env()

import anthropic  # noqa: E402

from config import ANTHROPIC_API_KEY, OUTPUT_DIR  # noqa: E402
from pipeline.orchestrator import run_content_filter_batched  # noqa: E402


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _verdict_decision(verdict: dict) -> str:
    """Collapse old and new verdict shapes onto a single KEEP/DROP axis."""
    decision = verdict.get("decision")
    if decision in ("KEEP", "DROP"):
        return decision
    keep = verdict.get("keep")
    if isinstance(keep, bool):
        return "KEEP" if keep else "DROP"
    legacy = verdict.get("verdict")
    if legacy == "NEWS":
        return "KEEP"
    if legacy == "NOT_NEWS":
        return "DROP"
    return "UNKNOWN"


async def replay_date(
    client: anthropic.AsyncAnthropic,
    date: str,
    new_prompt: str,
) -> dict:
    """Run one date through the new prompt and return a diff summary."""
    raw_path = OUTPUT_DIR / f"scout_output_raw_{date}.json"
    old_verdicts_path = OUTPUT_DIR / f"content_filter_output_{date}.json"

    if not raw_path.exists():
        return {"date": date, "error": f"missing {raw_path.name}"}
    if not old_verdicts_path.exists():
        return {"date": date, "error": f"missing {old_verdicts_path.name}"}

    items = _load_json(raw_path)
    old_payload = _load_json(old_verdicts_path)
    old_verdicts = old_payload.get("verdicts", [])

    print(f"[{date}] replaying {len(items)} items against {new_prompt} ...", flush=True)

    kept_items, drops, new_verdicts, usage, batch_summaries = await run_content_filter_batched(
        client,
        items,
        prompt_filename=new_prompt,
    )

    # Map verdicts by id for side-by-side comparison. The orchestrator's
    # _normalize_content_filter_verdict already rewrites per-batch indices to
    # global ids, so a single dict lookup works for both old and new.
    def index_by_id(verdicts: list[dict]) -> dict[int, dict]:
        out = {}
        for v in verdicts:
            vid = v.get("id")
            if vid is None:
                vid = v.get("index")
            if vid is not None:
                out[int(vid)] = v
        return out

    old_by_id = index_by_id(old_verdicts)
    new_by_id = index_by_id(new_verdicts)

    newly_kept: list[dict] = []       # old DROP -> new KEEP
    newly_dropped: list[dict] = []    # old KEEP -> new DROP
    agreement_count = 0
    old_keep_count = 0
    old_drop_count = 0
    new_keep_count = 0
    new_drop_count = 0
    disagreement_rows: list[dict] = []

    for i, item in enumerate(items):
        old_v = old_by_id.get(i, {})
        new_v = new_by_id.get(i, {})
        old_d = _verdict_decision(old_v) if old_v else "UNKNOWN"
        new_d = _verdict_decision(new_v) if new_v else "UNKNOWN"

        if old_d == "KEEP":
            old_keep_count += 1
        elif old_d == "DROP":
            old_drop_count += 1
        if new_d == "KEEP":
            new_keep_count += 1
        elif new_d == "DROP":
            new_drop_count += 1

        if old_d == new_d and old_d != "UNKNOWN":
            agreement_count += 1
            continue

        diff_row = {
            "id": i,
            "headline": item.get("headline", ""),
            "source": item.get("source"),
            "source_url": item.get("source_url"),
            "old_decision": old_d,
            "old_reason": old_v.get("reason"),
            "new_decision": new_d,
            "new_evaluation": new_v.get("evaluation"),
            "new_reason": new_v.get("reason"),
        }
        disagreement_rows.append(diff_row)

        if old_d == "DROP" and new_d == "KEEP":
            newly_kept.append(diff_row)
        elif old_d == "KEEP" and new_d == "DROP":
            newly_dropped.append(diff_row)

    total = len(items)
    agreement_pct = (agreement_count / total * 100) if total else 0.0

    summary = {
        "date": date,
        "new_prompt": new_prompt,
        "total_items": total,
        "old_kept": old_keep_count,
        "old_dropped": old_drop_count,
        "new_kept": new_keep_count,
        "new_dropped": new_drop_count,
        "agreement": agreement_count,
        "agreement_pct": round(agreement_pct, 1),
        "newly_kept_count": len(newly_kept),
        "newly_dropped_count": len(newly_dropped),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "batches": len(batch_summaries),
    }

    out_path = OUTPUT_DIR / f"content_filter_shadow_{date}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": summary,
                "newly_kept": newly_kept,
                "newly_dropped": newly_dropped,
                "disagreements": disagreement_rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[{date}] done: agreement {agreement_count}/{total} ({agreement_pct:.1f}%), "
        f"newly_kept={len(newly_kept)}, newly_dropped={len(newly_dropped)}, "
        f"old {old_keep_count}K/{old_drop_count}D vs new {new_keep_count}K/{new_drop_count}D",
        flush=True,
    )
    return summary


async def main(dates: list[str], new_prompt: str) -> int:
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set. Check your .env file.", file=sys.stderr)
        return 2

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    all_summaries: list[dict] = []
    for d in dates:
        s = await replay_date(client, d, new_prompt)
        all_summaries.append(s)

    # Cross-date aggregate
    ok = [s for s in all_summaries if "error" not in s]
    if ok:
        total_items = sum(s["total_items"] for s in ok)
        total_agree = sum(s["agreement"] for s in ok)
        total_newly_kept = sum(s["newly_kept_count"] for s in ok)
        total_newly_dropped = sum(s["newly_dropped_count"] for s in ok)
        total_in = sum(s["input_tokens"] for s in ok)
        total_out = sum(s["output_tokens"] for s in ok)
        print()
        print("=" * 72)
        print("AGGREGATE")
        print("=" * 72)
        print(f"  dates              : {', '.join(s['date'] for s in ok)}")
        print(f"  items              : {total_items}")
        print(f"  agreement          : {total_agree} ({100*total_agree/total_items:.1f}%)")
        print(f"  newly_kept         : {total_newly_kept}")
        print(f"  newly_dropped      : {total_newly_dropped}")
        print(f"  input_tokens total : {total_in:,}")
        print(f"  output_tokens total: {total_out:,}")

    errs = [s for s in all_summaries if "error" in s]
    if errs:
        print()
        print("Errors:")
        for s in errs:
            print(f"  {s['date']}: {s['error']}")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dates",
        nargs="+",
        required=True,
        help="Dates to replay (YYYY-MM-DD). Requires scout_output_raw_<date>.json "
        "and content_filter_output_<date>.json under backend/output/.",
    )
    parser.add_argument(
        "--new-prompt",
        default="content_filter_prompt.md",
        help="Prompt filename (relative to prompts/) or absolute path. Defaults "
        "to the production prompt.",
    )
    args = parser.parse_args()

    rc = asyncio.run(main(args.dates, args.new_prompt))
    sys.exit(rc)
