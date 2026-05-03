#!/usr/bin/env python3.11
"""Gatekeeper consistency eval.

Re-runs the gatekeeper on historical scout outputs and compares against the
original selections. Measures selection stability across identical inputs.

Usage:
    cd backend && python -m evals.eval_gatekeeper_consistency
    cd backend && python -m evals.eval_gatekeeper_consistency --dates 2026-03-10,2026-03-09
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

import anthropic

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import OUTPUT_DIR, DELIVERY_FORMAT, USER_PROFILE, PROMPTS_DIR  # noqa: E402
from pipeline.gatekeeper import run_gatekeeper  # noqa: E402
from pipeline.orchestrator import BRIEF_SECTIONS, normalize_section_name  # noqa: E402
from prompts.loader import extract_prompt_from_md  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EVAL_MODEL = "claude-sonnet-4-6"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test gatekeeper consistency by re-running on identical inputs.",
    )
    parser.add_argument(
        "--dates",
        default=None,
        help="Comma-separated YYYY-MM-DD dates. Default: 3 most recent with artifacts.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="How many re-runs per date (default: 1).",
    )
    return parser.parse_args()


def find_recent_dates(n: int = 3) -> list[str]:
    """Find the N most recent dates that have both scout and gatekeeper artifacts."""
    scout_files = sorted(OUTPUT_DIR.glob("scout_output_*.json"), reverse=True)
    dates: list[str] = []
    for sf in scout_files:
        d = sf.stem.replace("scout_output_", "")
        gk = OUTPUT_DIR / f"gatekeeper_output_{d}.json"
        if gk.exists():
            dates.append(d)
        if len(dates) >= n:
            break
    return dates


def normalize_headline(text: str) -> str:
    return " ".join((text or "").lower().split())


def item_key(item: dict) -> str:
    """Return a stable key for an item: prefer source_url, fallback to headline."""
    url = (item.get("source_url") or "").strip()
    if url:
        return url
    return normalize_headline(item.get("headline", ""))


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)


def section_distribution(items: list[dict], field: str = "section") -> dict[str, int]:
    counts: dict[str, int] = {s: 0 for s in BRIEF_SECTIONS}
    for item in items:
        sec = normalize_section_name(item.get(field))
        if sec:
            counts[sec] = counts.get(sec, 0) + 1
    return counts


def score_correlation(original_items: list[dict], replay_items: list[dict]) -> dict:
    """Compare relevance_score for items present in both runs."""
    orig_scores: dict[str, float] = {}
    for item in original_items:
        k = item_key(item)
        score = item.get("relevance_score") or item.get("score")
        if k and score is not None:
            orig_scores[k] = float(score)

    replay_scores: dict[str, float] = {}
    for item in replay_items:
        k = item_key(item)
        score = item.get("relevance_score") or item.get("score")
        if k and score is not None:
            replay_scores[k] = float(score)

    shared_keys = set(orig_scores) & set(replay_scores)
    if not shared_keys:
        return {"shared_items": 0, "mean_abs_diff": None, "max_diff": None}

    diffs = [abs(orig_scores[k] - replay_scores[k]) for k in shared_keys]
    return {
        "shared_items": len(shared_keys),
        "mean_abs_diff": round(sum(diffs) / len(diffs), 3),
        "max_diff": round(max(diffs), 3),
    }


# ---------------------------------------------------------------------------
# Prompt building (mirrors replay_gatekeeper_shadow.py logic)
# ---------------------------------------------------------------------------

def _historical_date_variable(target_date_str: str) -> str:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    GST = ZoneInfo("Asia/Dubai")
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    if target_date.weekday() == 0:
        cutoff_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=GST).replace(hour=6) - timedelta(days=3)
    else:
        cutoff_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=GST).replace(hour=6) - timedelta(days=1)
    return cutoff_dt.strftime("%Y-%m-%d") + " 6:00am GST"


def _historical_lookback_cutoff(target_date_str: str) -> str:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    GST = ZoneInfo("Asia/Dubai")
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    if target_date.weekday() == 0:
        days_back = 3
    else:
        days_back = 1
    cutoff_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=GST).replace(hour=6) - timedelta(days=days_back)
    return str(cutoff_dt.date())


def _historical_previous_brief_headlines(target_date_str: str, max_days: int = 3) -> str:
    all_headlines: list[dict] = []
    days_found = 0
    files = sorted(OUTPUT_DIR.glob("brief_*.json"), reverse=True)
    for path in files:
        if days_found >= max_days:
            break
        brief_date = path.stem.replace("brief_", "")
        if brief_date >= target_date_str:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("items", []):
            if item.get("is_placeholder"):
                continue
            all_headlines.append({
                "brief_date": brief_date,
                "headline": item.get("headline", ""),
                "section": item.get("section", ""),
                "entities": item.get("entities", []),
                "main_bullet": item.get("main_bullet", ""),
            })
        days_found += 1
    if not all_headlines:
        return "No previous brief available. This is the first run."
    return json.dumps(all_headlines, indent=2, ensure_ascii=False)


def _historical_previous_brief(target_date_str: str) -> str:
    files = sorted(OUTPUT_DIR.glob("brief_*.json"), reverse=True)
    for path in files:
        if path.stem.replace("brief_", "") < target_date_str:
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                continue
    return "No previous brief available. This is the first run."


def build_gatekeeper_prompt(target_date_str: str, scout_output_json: str) -> str:
    raw_md = (PROMPTS_DIR / "gatekeeper_prompt.md").read_text(encoding="utf-8")
    prompt_text = extract_prompt_from_md(raw_md)

    replacements = {
        "{date_variable}": _historical_date_variable(target_date_str),
        "{lookback_cutoff}": _historical_lookback_cutoff(target_date_str),
        "{previous_brief_headlines}": _historical_previous_brief_headlines(target_date_str),
        "{scout_output}": scout_output_json,
        "{gatekeeper_output}": "",
        "{ghostwriter_output}": "",
        "{items_json}": "",
        "{user_profile}": USER_PROFILE,
        "{delivery_format}": DELIVERY_FORMAT,
        "{date}": target_date_str,
        "{previous_brief}": _historical_previous_brief(target_date_str),
    }

    for placeholder, value in replacements.items():
        prompt_text = prompt_text.replace(placeholder, value)
    return prompt_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def evaluate_date(
    client: anthropic.AsyncAnthropic,
    date_str: str,
    num_runs: int,
) -> dict:
    """Run gatekeeper on a single date and compare to original."""
    scout_path = OUTPUT_DIR / f"scout_output_{date_str}.json"
    gk_path = OUTPUT_DIR / f"gatekeeper_output_{date_str}.json"

    scout_data = json.loads(scout_path.read_text(encoding="utf-8"))
    original_gk = json.loads(gk_path.read_text(encoding="utf-8"))

    # Extract original selected items
    original_items = original_gk.get("selected", original_gk.get("items", []))
    original_keys = {item_key(it) for it in original_items}

    # Build the prompt the same way the pipeline does
    scout_json_str = json.dumps(scout_data, ensure_ascii=False)
    prompt_text = build_gatekeeper_prompt(date_str, scout_json_str)

    runs: list[dict] = []
    for run_idx in range(num_runs):
        print(f"  Run {run_idx + 1}/{num_runs} for {date_str}...")
        try:
            replay_result, usage = await run_gatekeeper(client, prompt_text)
        except Exception as e:
            print(f"    ERROR: {e}")
            runs.append({"error": str(e)})
            continue

        replay_items = replay_result.get("selected", replay_result.get("items", []))
        replay_keys = {item_key(it) for it in replay_items}

        overlap = original_keys & replay_keys
        j = jaccard(original_keys, replay_keys)
        scores = score_correlation(original_items, replay_items)
        orig_sections = section_distribution(original_items)
        replay_sections = section_distribution(replay_items)

        run_report = {
            "original_count": len(original_items),
            "replay_count": len(replay_items),
            "overlap_count": len(overlap),
            "jaccard_similarity": round(j, 3),
            "score_correlation": scores,
            "original_sections": orig_sections,
            "replay_sections": replay_sections,
            "only_in_original": sorted(original_keys - replay_keys),
            "only_in_replay": sorted(replay_keys - original_keys),
            "usage": usage,
        }
        runs.append(run_report)

    # Aggregate across runs
    valid_runs = [r for r in runs if "error" not in r]
    avg_jaccard = (
        round(sum(r["jaccard_similarity"] for r in valid_runs) / len(valid_runs), 3)
        if valid_runs else None
    )

    return {
        "date": date_str,
        "num_runs": num_runs,
        "successful_runs": len(valid_runs),
        "avg_jaccard": avg_jaccard,
        "high_instability": avg_jaccard is not None and avg_jaccard < 0.70,
        "runs": runs,
    }


async def main() -> None:
    args = parse_args()

    if args.dates:
        dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    else:
        dates = find_recent_dates(3)

    if not dates:
        print("No dates found with both scout_output and gatekeeper_output artifacts.")
        sys.exit(1)

    print(f"Gatekeeper consistency eval")
    print(f"Dates: {', '.join(dates)}")
    print(f"Runs per date: {args.runs}")
    print("-" * 60)

    client = anthropic.AsyncAnthropic()

    results: list[dict] = []
    for date_str in dates:
        print(f"\nEvaluating {date_str}...")
        result = await evaluate_date(client, date_str, args.runs)
        results.append(result)

    # Print report
    print("\n" + "=" * 60)
    print("GATEKEEPER CONSISTENCY REPORT")
    print("=" * 60)

    unstable_dates: list[str] = []
    for r in results:
        print(f"\n--- {r['date']} ---")
        if r["avg_jaccard"] is None:
            print("  All runs failed.")
            continue
        print(f"  Avg Jaccard similarity: {r['avg_jaccard']}")
        print(f"  Successful runs: {r['successful_runs']}/{r['num_runs']}")
        if r["high_instability"]:
            print("  *** HIGH INSTABILITY (< 70% overlap) ***")
            unstable_dates.append(r["date"])

        for i, run in enumerate(r["runs"]):
            if "error" in run:
                print(f"  Run {i+1}: ERROR - {run['error']}")
                continue
            print(f"  Run {i+1}: overlap={run['overlap_count']}/{run['original_count']} "
                  f"jaccard={run['jaccard_similarity']} "
                  f"score_mean_diff={run['score_correlation'].get('mean_abs_diff', 'N/A')}")
            print(f"    Original sections: {run['original_sections']}")
            print(f"    Replay sections:   {run['replay_sections']}")
            if run["only_in_original"]:
                print(f"    Only in original ({len(run['only_in_original'])}): "
                      f"{run['only_in_original'][:5]}{'...' if len(run['only_in_original']) > 5 else ''}")
            if run["only_in_replay"]:
                print(f"    Only in replay ({len(run['only_in_replay'])}): "
                      f"{run['only_in_replay'][:5]}{'...' if len(run['only_in_replay']) > 5 else ''}")

    # Summary
    valid = [r for r in results if r["avg_jaccard"] is not None]
    if valid:
        overall_jaccard = round(sum(r["avg_jaccard"] for r in valid) / len(valid), 3)
        print(f"\n{'=' * 60}")
        print(f"SUMMARY")
        print(f"  Dates evaluated: {len(results)}")
        print(f"  Overall avg Jaccard: {overall_jaccard}")
        print(f"  Unstable dates (< 70%): {unstable_dates if unstable_dates else 'none'}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
