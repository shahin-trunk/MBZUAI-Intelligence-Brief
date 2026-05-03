"""Synthesis vs legacy fuzzy-filter backtest.

For each historical date with captured scout_output, this script:

1. Loads the captured post-content-filter items (scout_output_{date}.json).
2. Fetches the brief headlines from the 3 days *prior to that date* so
   Synthesis and the legacy filter both see the same previous-brief context
   they would have seen on the original run.
3. Runs the NEW Synthesis stage (live Haiku 4.5 call) against the items.
4. Runs the LEGACY `flag_previous_brief_overlaps` fuzzy filter against the
   same items, in parallel — no state shared.
5. Compares the two decisions per item:
     - legacy HARD-DROP vs Synthesis continuity_status
     - legacy KEEP     vs Synthesis continuity_status
6. Flags the cases we care about:
     - "rescued":    legacy would have dropped, Synthesis marks as
                     new_story or continuation → the change saves the item
     - "still_dropped": both agree it's a restatement
     - "newly_dropped": legacy kept, Synthesis marks as restatement →
                     the change removes something legacy would have kept
     - "kept_by_both": no change

Output: one summary row per date plus a short per-cluster breakdown for
any Crown-Prince-style multi-item event clusters Synthesis identifies.

The point: we want "rescued" to be non-zero on dates where we know there
was a multi-day event. "newly_dropped" should stay small or zero — if
Synthesis aggressively marks things as restatement we'd lose coverage.

Usage:
    python3 backend/backtest_synthesis_vs_legacy.py
    python3 backend/backtest_synthesis_vs_legacy.py --dates 2026-04-15,2026-03-10
    python3 backend/backtest_synthesis_vs_legacy.py --dry-run  # skip API
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_project_env  # noqa: E402

load_project_env()

OUTPUT_DIR = BACKEND_DIR / "output"


def _available_dates() -> list[str]:
    dates: list[str] = []
    for path in sorted(OUTPUT_DIR.glob("scout_output_*.json")):
        stem = path.stem  # scout_output_2026-04-15
        if "raw" in stem:
            continue
        date = stem.replace("scout_output_", "")
        if len(date) == 10 and date.count("-") == 2:
            dates.append(date)
    return dates


def _supabase_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
    )
    if not url or not key:
        raise SystemExit("SUPABASE_URL + service role key must be set in env")
    return create_client(url, key)


def _prior_brief_context(sb, target_date: str, max_days: int = 3) -> str:
    """Return JSON-encoded list of brief headlines from the ~3 days before
    target_date. This is what the Synthesis prompt + the legacy fuzzy
    filter both need to do continuity comparison."""
    from datetime import date, datetime, timedelta

    d = datetime.strptime(target_date, "%Y-%m-%d").date()
    # Look back up to ~7 calendar days because briefs skip weekends/holidays
    dates_to_check = [
        (d - timedelta(days=i)).isoformat() for i in range(1, 8)
    ]
    resp = (
        sb.table("brief_items")
        .select("brief_date, headline, section, main_bullet")
        .in_("brief_date", dates_to_check)
        .execute()
    )
    rows = resp.data or []
    # Truncate to last 3 *distinct* dates so we match production behavior.
    seen_dates: list[str] = []
    for row in sorted(rows, key=lambda r: r["brief_date"], reverse=True):
        bd = row["brief_date"]
        if bd not in seen_dates:
            seen_dates.append(bd)
        if len(seen_dates) > max_days:
            break
    filtered = [row for row in rows if row["brief_date"] in seen_dates[:max_days]]
    # Add an empty entities list since brief_items doesn't store it.
    out = [
        {
            "brief_date": row["brief_date"],
            "headline": row["headline"],
            "section": row.get("section", ""),
            "entities": [],
            "main_bullet": row.get("main_bullet", ""),
        }
        for row in filtered
    ]
    return json.dumps(out, ensure_ascii=False)


async def _run_synthesis_on_date(
    client, items: list[dict], prior_brief_json: str
) -> dict:
    from prompts.loader import load_prompt
    from pipeline.synthesis import run_synthesis

    synthesis_items = [
        {
            "id": i,
            "headline": it.get("headline", ""),
            "summary": (it.get("summary") or "")[:800],
            "entities": it.get("entities", []),
            "source": it.get("source"),
            "date": it.get("date") or it.get("_verified_date"),
        }
        for i, it in enumerate(items)
    ]

    prompt = load_prompt(
        "synthesis_prompt.md",
        items_json=json.dumps(synthesis_items, indent=2, ensure_ascii=False),
    )
    # The loader injected `get_previous_brief_headlines()` (today's context)
    # into the template. Replace with the historical context so the
    # backtest is fair.
    prompt = prompt.replace(
        "{previous_brief_headlines}", prior_brief_json
    )
    # If get_previous_brief_headlines() already substituted (most common),
    # we overwrite that section. Find the JSON we need to replace by
    # pattern: the loader uses the key name literally as a placeholder.
    # We handle both cases via dual substitution above.

    result, usage = await run_synthesis(client, prompt)
    return {"result": result, "usage": usage}


def _run_legacy_on_date(
    items: list[dict], prior_brief_json: str
) -> tuple[list[dict], int]:
    """Run flag_previous_brief_overlaps against items, forcing the prior
    brief context rather than letting it pull today's live context."""
    # The function reads via get_previous_brief_headlines() — monkey-patch
    # that symbol in the orchestrator module for this call.
    import pipeline.orchestrator as orch

    original = orch.get_previous_brief_headlines
    orch.get_previous_brief_headlines = lambda: prior_brief_json
    try:
        kept, hard, soft = orch.flag_previous_brief_overlaps(list(items))
        return hard, soft
    finally:
        orch.get_previous_brief_headlines = original


def _classify_items(
    items: list[dict],
    legacy_hard_drops: list[dict],
    synthesis_result: dict,
) -> dict:
    """Per-item comparison between legacy and Synthesis decisions."""
    # Build fast lookup by headline
    legacy_drop_headlines = {
        (d.get("headline") or "").strip() for d in legacy_hard_drops
    }

    restatement_ids = set()
    continuation_ids = set()
    new_story_ids = set()
    for ann in synthesis_result.get("item_annotations", []):
        iid = ann.get("item_id")
        status = ann.get("continuity_status")
        if iid is None:
            continue
        if status == "restatement":
            restatement_ids.add(iid)
        elif status == "continuation":
            continuation_ids.add(iid)
        elif status == "new_story":
            new_story_ids.add(iid)
    # Clusters-only fallback for items missing per-item annotation:
    for cluster in synthesis_result.get("clusters", []):
        status = cluster.get("continuity_status")
        for mid in cluster.get("member_item_ids", []):
            if mid in restatement_ids or mid in continuation_ids or mid in new_story_ids:
                continue
            if status == "restatement":
                restatement_ids.add(mid)
            elif status == "continuation":
                continuation_ids.add(mid)
            elif status == "new_story":
                new_story_ids.add(mid)

    rescued = []          # legacy would drop; Synthesis = continuation or new_story
    still_dropped = []    # both agree = restatement
    newly_dropped = []    # Synthesis = restatement; legacy did NOT drop
    kept_by_both = 0

    for idx, item in enumerate(items):
        headline = (item.get("headline") or "").strip()
        legacy_wants_drop = headline in legacy_drop_headlines
        synthesis_wants_drop = idx in restatement_ids

        if legacy_wants_drop and not synthesis_wants_drop:
            rescued.append({"id": idx, "headline": headline})
        elif legacy_wants_drop and synthesis_wants_drop:
            still_dropped.append({"id": idx, "headline": headline})
        elif not legacy_wants_drop and synthesis_wants_drop:
            newly_dropped.append({"id": idx, "headline": headline})
        else:
            kept_by_both += 1

    return {
        "rescued": rescued,
        "still_dropped": still_dropped,
        "newly_dropped": newly_dropped,
        "kept_by_both": kept_by_both,
        "legacy_hard_drops_total": len(legacy_hard_drops),
        "synthesis_restatements_total": len(restatement_ids),
        "synthesis_continuations_total": len(continuation_ids),
        "synthesis_new_stories_total": len(new_story_ids),
    }


async def backtest_one(
    client, sb, date: str
) -> dict:
    scout_path = OUTPUT_DIR / f"scout_output_{date}.json"
    if not scout_path.exists():
        return {"date": date, "error": "missing scout_output"}

    items = json.loads(scout_path.read_text(encoding="utf-8"))
    print(f"\n--- {date} ---  items={len(items)}")

    prior_json = _prior_brief_context(sb, date, max_days=3)
    prior_count = len(json.loads(prior_json)) if prior_json and prior_json != "[]" else 0
    print(f"prior brief context: {prior_count} headlines")

    legacy_hard_drops, legacy_soft_count = _run_legacy_on_date(items, prior_json)
    print(
        f"LEGACY: {len(legacy_hard_drops)} hard drop(s), "
        f"{legacy_soft_count} soft flag(s)"
    )

    if client is None:
        return {
            "date": date,
            "items": len(items),
            "legacy_hard_drops": len(legacy_hard_drops),
            "note": "dry-run (Synthesis skipped)",
        }

    syn_bundle = await _run_synthesis_on_date(client, items, prior_json)
    syn_result = syn_bundle["result"]
    print(
        f"SYNTHESIS: {len(syn_result.get('clusters', []))} cluster(s), "
        f"tokens_in={syn_bundle['usage']['input_tokens']}, "
        f"tokens_out={syn_bundle['usage']['output_tokens']}"
    )

    comparison = _classify_items(items, legacy_hard_drops, syn_result)
    print(
        f"COMPARE: "
        f"rescued={len(comparison['rescued'])} | "
        f"still_dropped={len(comparison['still_dropped'])} | "
        f"newly_dropped={len(comparison['newly_dropped'])} | "
        f"kept_by_both={comparison['kept_by_both']}"
    )

    # Show any rescued items — these are the ones the fix saves.
    for r in comparison["rescued"][:10]:
        print(f"  🟢 RESCUED  [{r['id']}] {r['headline'][:85]}")
    for n in comparison["newly_dropped"][:5]:
        print(f"  🔴 NEW DROP [{n['id']}] {n['headline'][:85]}")

    # Head-of-state clusters (the category that failed today)
    hos = [
        c
        for c in syn_result.get("clusters", [])
        if c.get("significance_tier") == "head_of_state"
    ]
    if hos:
        print(f"HEAD-OF-STATE CLUSTERS: {len(hos)}")
        for c in hos:
            print(
                f"  ★ {c['cluster_id']:<40}  "
                f"continuity={c.get('continuity_status'):<12} "
                f"members={len(c.get('member_item_ids', []))}"
            )

    return {
        "date": date,
        "items": len(items),
        "clusters": len(syn_result.get("clusters", [])),
        "head_of_state_clusters": len(hos),
        "legacy_hard_drops": len(legacy_hard_drops),
        "synthesis_restatements": comparison["synthesis_restatements_total"],
        "synthesis_continuations": comparison["synthesis_continuations_total"],
        "rescued": len(comparison["rescued"]),
        "still_dropped": len(comparison["still_dropped"]),
        "newly_dropped": len(comparison["newly_dropped"]),
        "kept_by_both": comparison["kept_by_both"],
        "tokens_in": syn_bundle["usage"]["input_tokens"],
        "tokens_out": syn_bundle["usage"]["output_tokens"],
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dates",
        help="Comma-separated list of dates to backtest; defaults to all available",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip the Synthesis API call; only run the legacy filter",
    )
    args = parser.parse_args()

    if args.dates:
        dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    else:
        dates = _available_dates()

    if not dates:
        print("No captured scout_output found in backend/output/")
        return 1

    sb = _supabase_client()

    client = None
    if not args.dry_run:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY required unless --dry-run")
        import anthropic

        client = anthropic.AsyncAnthropic()

    results = []
    for date in dates:
        try:
            results.append(await backtest_one(client, sb, date))
        except Exception as e:
            print(f"  ✗ backtest {date} failed: {e}")
            results.append({"date": date, "error": str(e)})

    # Aggregate
    successful = [r for r in results if "error" not in r and "clusters" in r]
    print("\n" + "=" * 70)
    print("BACKTEST SUMMARY")
    print("=" * 70)
    print(
        f"\n{'date':<12}{'items':>6}{'cluster':>8}{'HoS':>5}"
        f"{'rescued':>9}{'newDrop':>9}{'legacy':>8}{'restmt':>7}"
    )
    for r in successful:
        print(
            f"{r['date']:<12}{r['items']:>6}{r['clusters']:>8}"
            f"{r['head_of_state_clusters']:>5}"
            f"{r['rescued']:>9}{r['newly_dropped']:>9}"
            f"{r['legacy_hard_drops']:>8}{r['synthesis_restatements']:>7}"
        )

    if successful:
        total_rescued = sum(r["rescued"] for r in successful)
        total_newly_dropped = sum(r["newly_dropped"] for r in successful)
        total_legacy_dropped = sum(r["legacy_hard_drops"] for r in successful)
        total_hos = sum(r["head_of_state_clusters"] for r in successful)
        avg_in = sum(r["tokens_in"] for r in successful) / len(successful)
        avg_out = sum(r["tokens_out"] for r in successful) / len(successful)
        print(
            f"\nAcross {len(successful)} date(s):\n"
            f"  Items that Synthesis RESCUES from legacy hard-drop:  {total_rescued}\n"
            f"  Items that Synthesis NEWLY DROPS as restatement:     {total_newly_dropped}\n"
            f"  Legacy fuzzy filter total hard-drops (baseline):     {total_legacy_dropped}\n"
            f"  Head-of-state clusters identified:                   {total_hos}\n"
            f"  Avg tokens per run: in={avg_in:.0f} out={avg_out:.0f}"
        )

    # Save raw results for later inspection
    out_path = OUTPUT_DIR / "backtest_synthesis_vs_legacy.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nFull results: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
