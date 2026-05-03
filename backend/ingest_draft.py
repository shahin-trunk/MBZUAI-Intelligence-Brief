#!/usr/bin/env python3
"""
Ingest pipeline output as a draft slate for analyst curation.

Instead of writing directly to briefs/brief_items (which publishes immediately),
this writes to pending_briefs/pending_items for human review.

Usage:
    python3.11 ingest_draft.py                    # Ingest today's draft
    python3.11 ingest_draft.py --date 2026-04-08  # Ingest a specific date
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from supabase import create_client, Client

from env_loader import load_project_env
from ingest_brief import (
    _build_pipeline_run_row,
    _parse_dropped_items,
    _replace_rows_for_date,
)

# ---------------------------------------------------------------------------
# Paths & Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
DUBAI_TZ = ZoneInfo("Asia/Dubai")

BRIEF_SECTIONS = [
    "UAE",
    "Regional Research & Academic Events",
    "International Politics & Policy",
    "International Business & Technology",
    "Model Releases & Technical Developments",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ingest_draft")

# ---------------------------------------------------------------------------
# Environment & Supabase
# ---------------------------------------------------------------------------

def _load_env() -> None:
    for env_path in load_project_env():
        log.info("Loaded env from %s", env_path)


def _get_supabase_client() -> Client:
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.")
        sys.exit(1)
    return create_client(url, key)


def _today_in_dubai() -> date:
    return datetime.now(DUBAI_TZ).date()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_section(section: str) -> str:
    """Map a section name to canonical form."""
    lower = section.lower().strip()
    for canonical in BRIEF_SECTIONS:
        if canonical.lower() == lower:
            return canonical
    return section


def _assign_significance(score: float) -> str:
    if score >= 8.0:
        return "high"
    if score >= 6.0:
        return "medium"
    return "low"


def _infer_section_from_content(item: dict) -> str:
    """Infer brief section from item content when no section is assigned."""
    headline = (item.get("headline") or "").lower()
    source = (item.get("source") or item.get("source_name") or "").lower()
    text = f"{headline} {source}"

    uae_kw = ["uae", "abu dhabi", "dubai", "emirates", "mbzuai", "g42", "tii",
              "adnoc", "mubadala", "presight", "khazna"]
    model_kw = ["model", "release", "open-source", "parameter", "llm", "gpt",
                "gemma", "llama", "claude", "benchmark", "weights"]
    politics_kw = ["trump", "biden", "sanctions", "export control", "regulation",
                   "policy", "iran", "china", "tariff", "congress", "white house"]
    research_kw = ["university", "kaust", "research", "academic", "conference",
                   "arxiv", "faculty", "professor", "scholarship"]

    if any(k in text for k in model_kw):
        return "Model Releases & Technical Developments"
    if any(k in text for k in uae_kw):
        return "UAE"
    if any(k in text for k in politics_kw):
        return "International Politics & Policy"
    if any(k in text for k in research_kw):
        return "Regional Research & Academic Events"
    return "International Business & Technology"


# ---------------------------------------------------------------------------
# Draft Slate Builder
# ---------------------------------------------------------------------------

def _build_pending_brief_row(
    target_date: str,
    pipeline_stats: dict | None,
    gatekeeper_result: dict | None,
    source_metadata_lookup: dict | None,
    shadow_brief: dict | None,
) -> dict:
    """Build the row for the pending_briefs table."""
    return {
        "brief_date": target_date,
        "status": "pending",
        "shadow_recommendation": shadow_brief,
        "gatekeeper_output": (
            {
                "selected_count": len(gatekeeper_result.get("selected", [])),
                "dropped_count": len(gatekeeper_result.get("dropped", [])),
                "brief_summary": gatekeeper_result.get("brief_summary"),
            }
            if gatekeeper_result
            else None
        ),
        "source_metadata_lookup": source_metadata_lookup,
        "pipeline_stats": pipeline_stats,
    }


def _build_pending_item_row(
    pending_brief_id: str,
    item: dict,
    tier: str,
    rank: int,
) -> dict:
    """Build one pending_items row from a ghostwriter/gatekeeper item."""
    section = _normalize_section(
        item.get("section")
        or item.get("brief_section")
        or _infer_section_from_content(item)
    )
    score = float(item.get("composite_score") or 0)

    # v2 fields (ghostwriter now produces key_bullets + analysis)
    key_bullets = item.get("key_bullets") or []
    analysis = item.get("analysis") or ""

    # Compose legacy fields from v2 format when empty
    main_bullet = item.get("main_bullet") or ""
    if not main_bullet and key_bullets:
        main_bullet = " ".join(key_bullets)

    context = item.get("context") or ""
    implication = item.get("implication") or ""
    if not context and not implication and analysis:
        context = analysis

    return {
        "pending_brief_id": pending_brief_id,
        "item_id": item.get("id", ""),
        "tier": tier,
        "section": section,
        "headline": item.get("headline", ""),
        "main_bullet": main_bullet,
        "context": context,
        "implication": implication,
        "key_bullets": key_bullets if key_bullets else None,
        "analysis": analysis if analysis else None,
        "primary_entity": item.get("primary_entity"),
        "primary_entity_category": item.get("primary_entity_category"),
        "exhibits": item.get("exhibits"),
        "source_name": item.get("source_name") or item.get("source"),
        "source_url": item.get("source_url"),
        "composite_score": score,
        "significance_level": _assign_significance(score),
        "rank": rank,
        "depth": item.get("depth"),
        "is_model_release": bool(item.get("is_model_release")),
        "model_release_data": item.get("model_release_data"),
        "selected": False,
        "curation_order": None,
        "raw_item": item,
    }


# ---------------------------------------------------------------------------
# Main Ingest
# ---------------------------------------------------------------------------

def ingest_draft(
    sb: Client,
    target_date: str,
    ghostwriter_items: list[dict],
    pool_items: list[dict] | None = None,
    pipeline_stats: dict | None = None,
    gatekeeper_result: dict | None = None,
    source_metadata_lookup: dict | None = None,
    shadow_brief: dict | None = None,
) -> bool:
    """Write the draft slate to pending_briefs + pending_items.

    Args:
        ghostwriter_items: Items with full ghostwriter prose. Phase 2
            (curation rewrite): all items land here as tier="proposed".
            The Gatekeeper per-section cap ensures the whole slate
            (up to 15 × 5 sections = 75 items) is author-ready.
        pool_items: Deprecated. Phase 1 legacy parameter kept for
            callers that may still pass it; ignored if passed.
        pipeline_stats: Cost/timing metadata
        gatekeeper_result: Full gatekeeper output for calibration
        source_metadata_lookup: Source metadata for approval-time brief composition
        shadow_brief: What the Editor would have published (for calibration)
    """
    if pool_items:
        log.warning(
            "ingest_draft: pool_items parameter is deprecated in Phase 2; "
            "ignoring %d legacy pool item(s)",
            len(pool_items),
        )
    log.info("Ingesting draft slate for %s", target_date)

    # Phase 5 safeguard (2026-04-17): if an analyst has claimed the brief
    # for this date (status='in_review'), skip the re-ingest entirely.
    # The previous behavior was to upsert pending_briefs + wipe pending_items,
    # which destroys in-progress curator edits (attached exhibits, selections,
    # curation_order, text edits). Refuse to clobber in-progress work — the
    # analyst can finish and publish, or explicitly unclaim, before a new
    # pipeline run updates the draft.
    try:
        existing_resp = (
            sb.table("pending_briefs")
            .select("id, status, claimed_by")
            .eq("brief_date", target_date)
            .maybe_single()
            .execute()
        )
        # supabase-py returns None from .execute() when the row doesn't
        # exist; when it does, execute() returns a response object with
        # .data. Normalize both to a single `existing` dict-or-None.
        existing = existing_resp.data if existing_resp else None
    except Exception as e:
        log.warning("ingest_draft: could not check existing pending_briefs status (%s); continuing", e)
        existing = None
    if existing and existing.get("status") == "in_review":
        log.error(
            "ingest_draft: refusing to overwrite in-review brief for %s "
            "(claimed_by=%s, pending_brief_id=%s). Analyst must finish or "
            "unclaim before a new pipeline run can update pending_items.",
            target_date, existing.get("claimed_by"), existing.get("id"),
        )
        return False

    # 1. Create pending_briefs row
    brief_row = _build_pending_brief_row(
        target_date, pipeline_stats, gatekeeper_result,
        source_metadata_lookup, shadow_brief,
    )

    try:
        result = (
            sb.table("pending_briefs")
            .upsert(brief_row, on_conflict="brief_date")
            .execute()
        )
        pending_brief_id = result.data[0]["id"]
        log.info("Created pending_briefs row: %s", pending_brief_id)
    except Exception as e:
        log.error("Failed to create pending_briefs row: %s", e)
        return False

    # 2. Delete existing pending_items for this brief (re-run safety).
    # Guarded by the in-review check above, so this only wipes when the
    # brief is in status='pending' and no analyst has claimed it.
    try:
        sb.table("pending_items").delete().eq(
            "pending_brief_id", pending_brief_id
        ).execute()
    except Exception:
        pass  # Fine if none exist

    # 3. Build and insert pending_items (all tier="proposed" — Phase 2).
    item_rows: list[dict] = []
    for rank, item in enumerate(ghostwriter_items, start=1):
        item_rows.append(_build_pending_item_row(
            pending_brief_id, item, "proposed", rank,
        ))

    if item_rows:
        try:
            sb.table("pending_items").insert(item_rows).execute()
            section_counts: dict[str, int] = {}
            for row in item_rows:
                sec = row.get("section") or "?"
                section_counts[sec] = section_counts.get(sec, 0) + 1
            section_summary = ", ".join(
                f"{s}: {n}" for s, n in sorted(section_counts.items())
            )
            log.info(
                "Inserted %d pending_items (%s)", len(item_rows), section_summary
            )
        except Exception as e:
            log.error("Failed to insert pending_items: %s", e)
            return False

    # 4. Write pipeline_runs + dropped_items (audit trail, same as ingest_brief.py)
    try:
        brief_for_stats = {
            "brief_metadata": {"date": target_date},
            "items": ghostwriter_items,
        }
        pipeline_run_row = _build_pipeline_run_row(target_date, brief_for_stats)
        sb.table("pipeline_runs").upsert(
            pipeline_run_row, on_conflict="run_date"
        ).execute()
        log.info("Updated pipeline_runs for %s", target_date)
    except Exception as e:
        log.warning("Failed to update pipeline_runs (non-fatal): %s", e)

    try:
        dropped_rows = _parse_dropped_items(target_date)
        if dropped_rows:
            _replace_rows_for_date(
                sb, "dropped_items", "run_date", target_date, dropped_rows
            )
            log.info("Updated dropped_items: %d rows", len(dropped_rows))
    except Exception as e:
        log.warning("Failed to update dropped_items (non-fatal): %s", e)

    log.info(
        "Draft slate ingested for %s: %d proposed items (pool tier removed in Phase 2)",
        target_date,
        len(ghostwriter_items),
    )
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    _load_env()
    _require_python_310_plus()

    parser = argparse.ArgumentParser(description="Ingest pipeline draft slate")
    parser.add_argument("--date", help="Brief date (YYYY-MM-DD)")
    args = parser.parse_args()

    target_date = args.date or str(_today_in_dubai())
    sb = _get_supabase_client()

    # Load ghostwriter output
    gw_path = OUTPUT_DIR / f"ghostwriter_output_{target_date}.json"
    if not gw_path.exists():
        log.error("No ghostwriter output found at %s", gw_path)
        sys.exit(1)

    gw_result = json.loads(gw_path.read_text(encoding="utf-8"))
    ghostwriter_items = gw_result.get("items", [])

    # Load gatekeeper output for calibration metadata (not for pool —
    # Phase 2 removed the pool tier; every ghostwritten item lands as
    # tier="proposed").
    gk_path = OUTPUT_DIR / f"enriched_gatekeeper_output_{target_date}.json"
    if not gk_path.exists():
        gk_path = OUTPUT_DIR / f"gatekeeper_output_{target_date}.json"

    gatekeeper_result: dict | None = None
    if gk_path.exists():
        gatekeeper_result = json.loads(gk_path.read_text(encoding="utf-8"))

    # Load pipeline stats
    stats_path = OUTPUT_DIR / f"pipeline_stats_{target_date}.json"
    pipeline_stats = (
        json.loads(stats_path.read_text(encoding="utf-8"))
        if stats_path.exists()
        else None
    )

    # Load shadow brief (Editor output) if available
    shadow_path = OUTPUT_DIR / f"brief_{target_date}.json"
    shadow_brief = (
        json.loads(shadow_path.read_text(encoding="utf-8"))
        if shadow_path.exists()
        else None
    )

    ok = ingest_draft(
        sb,
        target_date,
        ghostwriter_items=ghostwriter_items,
        pipeline_stats=pipeline_stats,
        gatekeeper_result=gatekeeper_result,
        shadow_brief=shadow_brief,
    )

    if not ok:
        log.error("Draft ingest failed for %s", target_date)
        sys.exit(1)

    log.info("Draft ingest complete for %s", target_date)


def _require_python_310_plus() -> None:
    if sys.version_info < (3, 10):
        log.error("ingest_draft.py requires Python 3.10+.")
        sys.exit(1)


if __name__ == "__main__":
    main()
