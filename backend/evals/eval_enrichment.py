#!/usr/bin/env python3.11
"""Enrichment quality eval.

Measures whether the enrichment stage improves brief item quality by comparing
final brief items that were enriched (raw_content < 80 words, went through the
enrichment chain) against those that had sufficient raw_content and skipped it.

Purely analytical -- no API calls. Reads saved pipeline artifacts only.

Usage:
    cd backend && python -m evals.eval_enrichment
    cd backend && python -m evals.eval_enrichment --dates 2026-03-10,2026-03-09
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import OUTPUT_DIR  # noqa: E402

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate whether enrichment improves brief item quality.",
    )
    parser.add_argument(
        "--dates",
        default=None,
        help="Comma-separated YYYY-MM-DD dates. Default: last 5 available with brief artifacts.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def find_recent_dates(n: int = 5) -> list[str]:
    """Find the N most recent dates that have both brief and gatekeeper artifacts."""
    brief_files = sorted(OUTPUT_DIR.glob("brief_*.json"), reverse=True)
    dates: list[str] = []
    for bf in brief_files:
        date_str = bf.stem.replace("brief_", "")
        # Need either enriched_gatekeeper_output or plain gatekeeper_output
        has_gk = (
            (OUTPUT_DIR / f"enriched_gatekeeper_output_{date_str}.json").exists()
            or (OUTPUT_DIR / f"gatekeeper_output_{date_str}.json").exists()
        )
        if has_gk:
            dates.append(date_str)
        if len(dates) >= n:
            break
    return dates


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Build enrichment index from gatekeeper artifacts
# ---------------------------------------------------------------------------


def build_enrichment_index(date_str: str) -> dict[str, dict]:
    """Return a dict mapping item id -> enrichment metadata.

    Checks enriched_gatekeeper_output first (has _enrichment on all items),
    then falls back to plain gatekeeper_output (no _enrichment means the
    enrichment stage had not been introduced yet for that date).

    Returns:
        {item_id: {"was_enriched": bool, "meta": {...} or None}}
    """
    enriched_path = OUTPUT_DIR / f"enriched_gatekeeper_output_{date_str}.json"
    plain_path = OUTPUT_DIR / f"gatekeeper_output_{date_str}.json"

    gk_data = load_json(enriched_path)
    source = "enriched"
    if gk_data is None:
        gk_data = load_json(plain_path)
        source = "plain"
    if gk_data is None:
        return {}

    items = gk_data.get("selected", [])
    index: dict[str, dict] = {}
    for item in items:
        item_id = item.get("id", "")
        enrichment = item.get("_enrichment")
        if enrichment and enrichment.get("was_thin"):
            index[item_id] = {"was_enriched": True, "meta": enrichment}
        else:
            # Item existed in gatekeeper output but was not thin / not enriched
            index[item_id] = {"was_enriched": False, "meta": enrichment}

    return index


# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------


def word_count(text: str | None) -> int:
    if not text:
        return 0
    return len(text.split())


def compute_item_metrics(item: dict) -> dict:
    """Compute quality metrics for a single brief item."""
    main_wc = word_count(item.get("main_bullet"))
    context_wc = word_count(item.get("context"))
    implication_wc = word_count(item.get("implication"))
    total_wc = main_wc + context_wc + implication_wc

    additional_sources = item.get("additional_sources") or []
    source_count = len(additional_sources)

    depth = item.get("depth", "unknown")
    composite = item.get("composite_score") or 0.0

    return {
        "total_word_count": total_wc,
        "main_bullet_wc": main_wc,
        "context_wc": context_wc,
        "implication_wc": implication_wc,
        "composite_score": composite,
        "source_count": source_count,
        "depth": depth,
    }


# ---------------------------------------------------------------------------
# Per-date analysis
# ---------------------------------------------------------------------------


def analyse_date(date_str: str) -> dict | None:
    """Analyse enriched vs non-enriched items for a single date.

    Returns None if artifacts are missing or no items can be classified.
    """
    brief_data = load_json(OUTPUT_DIR / f"brief_{date_str}.json")
    if brief_data is None:
        print(f"  [skip] No brief found for {date_str}")
        return None

    enrichment_index = build_enrichment_index(date_str)
    if not enrichment_index:
        print(f"  [skip] No gatekeeper artifacts for {date_str}")
        return None

    brief_items = brief_data.get("items", [])

    enriched_metrics: list[dict] = []
    non_enriched_metrics: list[dict] = []
    unmatched = 0

    for item in brief_items:
        item_id = item.get("id", "")
        entry = enrichment_index.get(item_id)
        if entry is None:
            unmatched += 1
            continue

        metrics = compute_item_metrics(item)
        if entry["was_enriched"]:
            enriched_metrics.append(metrics)
        else:
            non_enriched_metrics.append(metrics)

    if not enriched_metrics and not non_enriched_metrics:
        print(f"  [skip] No classifiable items for {date_str}")
        return None

    return {
        "date": date_str,
        "enriched": enriched_metrics,
        "non_enriched": non_enriched_metrics,
        "unmatched": unmatched,
        "total_brief_items": len(brief_items),
    }


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def avg(values: list[float | int]) -> float:
    return sum(values) / len(values) if values else 0.0


def depth_distribution(metrics_list: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for m in metrics_list:
        counts[m["depth"]] += 1
    return dict(counts)


def group_summary(label: str, metrics_list: list[dict]) -> dict:
    if not metrics_list:
        return {"label": label, "count": 0}
    return {
        "label": label,
        "count": len(metrics_list),
        "avg_word_count": avg([m["total_word_count"] for m in metrics_list]),
        "avg_main_bullet_wc": avg([m["main_bullet_wc"] for m in metrics_list]),
        "avg_context_wc": avg([m["context_wc"] for m in metrics_list]),
        "avg_implication_wc": avg([m["implication_wc"] for m in metrics_list]),
        "avg_composite_score": avg([m["composite_score"] for m in metrics_list]),
        "avg_source_count": avg([m["source_count"] for m in metrics_list]),
        "depth_distribution": depth_distribution(metrics_list),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_group(summary: dict, indent: int = 4) -> None:
    pad = " " * indent
    if summary["count"] == 0:
        print(f"{pad}{summary['label']}: (no items)")
        return
    print(f"{pad}{summary['label']} ({summary['count']} items):")
    print(f"{pad}  Avg word count (total):    {summary['avg_word_count']:.1f}")
    print(f"{pad}    main_bullet:             {summary['avg_main_bullet_wc']:.1f}")
    print(f"{pad}    context:                 {summary['avg_context_wc']:.1f}")
    print(f"{pad}    implication:             {summary['avg_implication_wc']:.1f}")
    print(f"{pad}  Avg composite score:       {summary['avg_composite_score']:.2f}")
    print(f"{pad}  Avg additional sources:    {summary['avg_source_count']:.1f}")
    dd = summary["depth_distribution"]
    parts = ", ".join(f"{k}={v}" for k, v in sorted(dd.items()))
    print(f"{pad}  Depth distribution:        {parts}")


def print_report(results: list[dict]) -> None:
    all_enriched: list[dict] = []
    all_non_enriched: list[dict] = []

    print()
    print("=" * 72)
    print("ENRICHMENT QUALITY EVAL")
    print("=" * 72)

    for r in results:
        print()
        print(f"--- {r['date']} ({r['total_brief_items']} brief items, "
              f"{r['unmatched']} unmatched) ---")
        e_summary = group_summary("Enriched", r["enriched"])
        n_summary = group_summary("Non-enriched", r["non_enriched"])
        print_group(e_summary)
        print_group(n_summary)
        all_enriched.extend(r["enriched"])
        all_non_enriched.extend(r["non_enriched"])

    # Overall summary
    print()
    print("=" * 72)
    print("OVERALL SUMMARY")
    print("=" * 72)

    e_overall = group_summary("Enriched (all dates)", all_enriched)
    n_overall = group_summary("Non-enriched (all dates)", all_non_enriched)
    print_group(e_overall)
    print_group(n_overall)

    # Delta comparison
    print()
    if e_overall["count"] > 0 and n_overall["count"] > 0:
        wc_delta = e_overall["avg_word_count"] - n_overall["avg_word_count"]
        cs_delta = e_overall["avg_composite_score"] - n_overall["avg_composite_score"]
        src_delta = e_overall["avg_source_count"] - n_overall["avg_source_count"]
        print(f"  Word count delta (enriched - non-enriched):   {wc_delta:+.1f}")
        print(f"  Composite score delta:                        {cs_delta:+.2f}")
        print(f"  Source count delta:                           {src_delta:+.1f}")
        print()
        # Verdict
        comparable = abs(wc_delta) < 30 and abs(cs_delta) < 0.5
        if comparable:
            print("  Verdict: Enrichment produces items of COMPARABLE quality.")
        elif wc_delta > 0 and cs_delta >= 0:
            print("  Verdict: Enrichment produces HIGHER quality items (more detail, equal or better scores).")
        elif wc_delta < -30:
            print("  Verdict: Enriched items are SHORTER -- enrichment may be under-performing.")
        else:
            print("  Verdict: Mixed results -- enrichment effect is not clearly directional.")
    elif e_overall["count"] == 0:
        print("  No enriched items found across selected dates.")
        print("  (Enrichment may not have been active for these dates, or all items had sufficient raw_content.)")
    elif n_overall["count"] == 0:
        print("  No non-enriched items found across selected dates.")
        print("  (All items required enrichment -- no baseline for comparison.)")

    print()
    print(f"  Dates analysed: {len(results)}")
    print(f"  Total enriched items:     {e_overall['count']}")
    print(f"  Total non-enriched items: {n_overall['count']}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    if args.dates:
        dates = [d.strip() for d in args.dates.split(",")]
    else:
        dates = find_recent_dates(5)

    if not dates:
        print("No dates with brief + gatekeeper artifacts found in output/")
        sys.exit(1)

    print(f"Evaluating enrichment quality for dates: {', '.join(dates)}")

    results: list[dict] = []
    for date_str in dates:
        result = analyse_date(date_str)
        if result is not None:
            results.append(result)

    if not results:
        print("No analysable dates found.")
        sys.exit(1)

    print_report(results)


if __name__ == "__main__":
    main()
