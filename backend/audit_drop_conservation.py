"""Silent-drop conservation audit.

Phase 1 (drop visibility) was supposed to close the gap between:

    items_collected → items_in_final_brief

such that EVERY item that disappeared along the way is accounted for in
either `dropped_items` (one of the stages: triage, date_filter, content_filter,
previous_brief_overlap, gatekeeper, gatekeeper_implicit, post_gatekeeper_overlap)
OR `pending_items` (proposed / pool).

Before Phase 1, triage drops + pre-Gatekeeper overlap drops + Gatekeeper
implicit drops + post-Gatekeeper overlap drops were silently lost. This
audit script counts them per day and reports the "unexplained gap" — the
difference between what the pipeline says it processed and what we can
actually account for in the database.

A gap of 0 means the audit trail is complete. A large gap means at least
one drop path is still silent and needs to be wired up.

Usage:
    python3 backend/audit_drop_conservation.py             # last 14 days
    python3 backend/audit_drop_conservation.py --date 2026-04-15
    python3 backend/audit_drop_conservation.py --days 30

The script talks to Supabase directly — requires SUPABASE_URL +
SUPABASE_SERVICE_ROLE_KEY (or equivalent) in the env.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_project_env  # noqa: E402

load_project_env()

# These stages are the ones that should collectively sum up to the number
# of items that left the pipeline between collection and the final brief.
# If a stage is missing from this list, items it drops look like an
# "unexplained gap" — which is exactly the signal we want.
KNOWN_STAGES = [
    "triage",
    "date_filter",
    "content_filter",
    "previous_brief_overlap",
    "gatekeeper",
    "gatekeeper_implicit",
    "post_gatekeeper_overlap",
]


def _supabase_client():
    """Build a service-role Supabase client (admin privileges)."""
    try:
        from supabase import create_client
    except ImportError as e:
        raise SystemExit(
            "supabase-py is not installed; install `supabase` in the backend "
            "virtualenv"
        ) from e

    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
    )
    if not url or not key:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the env"
        )
    return create_client(url, key)


def _fetch_pipeline_runs(sb, date: str | None, days: int) -> list[dict]:
    q = sb.table("pipeline_runs").select("*")
    if date:
        q = q.eq("run_date", date)
    q = q.order("run_date", desc=True)
    resp = q.execute()
    rows = resp.data or []
    if not date:
        rows = rows[:days]
    return rows


def _fetch_drop_counts(sb, run_date: str) -> dict[str, int]:
    resp = (
        sb.table("dropped_items")
        .select("dropped_at_stage", count="exact")
        .eq("run_date", run_date)
        .execute()
    )
    rows = resp.data or []
    counts: dict[str, int] = {}
    for row in rows:
        stage = row.get("dropped_at_stage") or "unknown"
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def _fetch_pending_items_count(sb, brief_date: str) -> int:
    """Count pending_items for the brief_date (joined via pending_briefs)."""
    # pending_briefs.brief_date == pipeline_runs.run_date in normal operation.
    brief_resp = (
        sb.table("pending_briefs")
        .select("id")
        .eq("brief_date", brief_date)
        .execute()
    )
    brief_rows = brief_resp.data or []
    if not brief_rows:
        return 0
    ids = [row["id"] for row in brief_rows]
    total = 0
    for pb_id in ids:
        resp = (
            sb.table("pending_items")
            .select("id", count="exact")
            .eq("pending_brief_id", pb_id)
            .execute()
        )
        total += len(resp.data or [])
    return total


def audit(sb, run_row: dict) -> dict:
    """Compute conservation for one pipeline run."""
    run_date = run_row["run_date"]
    items_collected = run_row.get("items_collected") or 0
    items_in_brief = run_row.get("items_in_final_brief") or 0
    items_after_dedup = run_row.get("items_after_dedup") or run_row.get(
        "items_after_triage"
    ) or 0

    drop_counts = _fetch_drop_counts(sb, run_date)
    pending_total = _fetch_pending_items_count(sb, run_date)

    total_dropped = sum(drop_counts.values())

    # Dedup merges are expected to account for (items_after_triage -
    # items_after_dedup). We don't have a dedicated drop row per merge, but
    # we know items_after_triage and items_after_dedup from pipeline_runs.
    dedup_merges = max(
        (run_row.get("items_after_triage") or 0)
        - (run_row.get("items_after_dedup") or 0),
        0,
    )

    # Account for every item that entered the pipeline:
    #   collected = (final_brief items) + (pool/proposed items still in pending)
    #             + (drops persisted at any stage) + (dedup-merged items)
    # Where items_in_brief and pending items may overlap (a selected pending
    # item IS a brief item), so we use items_in_brief as authoritative and
    # count "pool" items (non-selected pending) separately if possible.
    # For now, treat pending_total as the upper bound — pending_items
    # typically has selected + proposed + pool rows — so we compare against
    # max(items_in_brief, pending_total).
    accounted_for = items_in_brief + total_dropped + dedup_merges
    gap = items_collected - accounted_for

    return {
        "run_date": run_date,
        "items_collected": items_collected,
        "items_in_brief": items_in_brief,
        "pending_total": pending_total,
        "dedup_merges_est": dedup_merges,
        "drops_total": total_dropped,
        "drop_counts": drop_counts,
        "accounted_for": accounted_for,
        "gap": gap,
        "phase1_silent_stages_populated": sum(
            1
            for stage in [
                "triage",
                "previous_brief_overlap",
                "gatekeeper_implicit",
                "post_gatekeeper_overlap",
            ]
            if drop_counts.get(stage, 0) > 0
        ),
    }


def _fmt_row(r: dict) -> str:
    stages = ", ".join(
        f"{name}={r['drop_counts'].get(name, 0)}" for name in KNOWN_STAGES
    )
    status = "✓" if abs(r["gap"]) <= 5 else "✗"
    return (
        f"  {r['run_date']}  "
        f"coll={r['items_collected']:>4}  "
        f"brief={r['items_in_brief']:>4}  "
        f"drops={r['drops_total']:>4}  "
        f"dedup={r['dedup_merges_est']:>3}  "
        f"gap={r['gap']:>+5}  {status}  "
        f"[phase1={r['phase1_silent_stages_populated']}/4]\n"
        f"    stages: {stages}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Single run_date to audit")
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of recent days to audit (ignored if --date is set)",
    )
    args = parser.parse_args()

    sb = _supabase_client()
    runs = _fetch_pipeline_runs(sb, args.date, args.days)

    if not runs:
        print("No pipeline runs found.")
        return 0

    print(
        "Silent-drop conservation audit. Gap ≈ 0 means every item is "
        "accounted for; large gaps flag silent drops.\n"
    )
    results = [audit(sb, r) for r in runs]

    header = (
        "  run_date   coll  brief  drops  dedup  gap   status  [phase1 stages]\n"
    )
    print(header)
    for r in results:
        print(_fmt_row(r))

    # Summary stats
    total_gap = sum(r["gap"] for r in results)
    avg_gap = total_gap / len(results) if results else 0
    max_gap = max(abs(r["gap"]) for r in results)
    phase1_populated_runs = sum(
        1 for r in results if r["phase1_silent_stages_populated"] > 0
    )
    print(
        f"\nSummary across {len(results)} run(s):\n"
        f"  total gap:        {total_gap}\n"
        f"  avg gap:          {avg_gap:+.1f}\n"
        f"  max |gap|:        {max_gap}\n"
        f"  phase1 stages populated on: {phase1_populated_runs}/{len(results)} runs"
    )

    # Non-zero exit if worst gap is large — this can wire into CI alerts.
    return 0 if max_gap <= 10 else 1


if __name__ == "__main__":
    sys.exit(main())
