#!/usr/bin/env python3
"""
Ingest daily brief JSON files into Supabase.

Usage:
    python3.11 ingest_brief.py                    # Ingest today's brief
    python3.11 ingest_brief.py --date 2026-03-04  # Ingest a specific date
    python3.11 ingest_brief.py --backfill         # Ingest all briefs in output/
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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent            # backend/
PROJECT_ROOT = SCRIPT_DIR.parent                        # Intelligence Dashboard/
FRONTEND_DIR = PROJECT_ROOT / "frontend"
OUTPUT_DIR = SCRIPT_DIR / "output"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ingest_brief")
DUBAI_TZ = ZoneInfo("Asia/Dubai")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """Load environment variables using the shared project precedence."""
    for env_path in load_project_env():
        log.info("Loaded env from %s", env_path)


def _site_url() -> str:
    """Resolve the frontend base URL after environment loading."""
    return (
        os.getenv("SITE_URL")
        or os.getenv("NEXT_PUBLIC_SITE_URL")
        or "https://mbzuai-intel.com"
    ).rstrip("/")


def _require_python_310_plus() -> None:
    """Fail fast when the runtime is too old for the type syntax used below."""
    if sys.version_info < (3, 10):
        log.error("ingest_brief.py requires Python 3.10+.")
        sys.exit(1)


def _get_supabase_client() -> Client:
    """Create and return a Supabase client using the service role key."""
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        log.error(
            "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. "
            "Ensure they are set in frontend/.env.local or project-root .env"
        )
        sys.exit(1)

    return create_client(url, key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_url(url: str | None) -> str | None:
    """Return None for empty or missing URLs."""
    if not url:
        return None
    return url


def _today_in_dubai() -> date:
    """Return today's date in Asia/Dubai to match pipeline naming."""
    return datetime.now(DUBAI_TZ).date()


def _revalidate_frontend(target_date: str) -> None:
    """Trigger on-demand ISR revalidation so the latest brief appears immediately."""
    import httpx

    secret = os.getenv("REVALIDATION_SECRET")
    if not secret:
        log.warning("REVALIDATION_SECRET not set — skipping frontend cache revalidation")
        return

    headers = {"x-revalidate-secret": secret, "Content-Type": "application/json"}
    paths = ["/brief/today", f"/brief/{target_date}"]

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            for path in paths:
                try:
                    resp = client.post(
                        f"{_site_url()}/api/revalidate",
                        json={"path": path},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        log.info("Revalidated %s via %s", path, str(resp.request.url))
                    else:
                        log.warning(
                            "Revalidation failed for %s: %d %s",
                            path,
                            resp.status_code,
                            resp.text[:200],
                        )
                except Exception as exc:
                    log.warning("Revalidation request failed for %s: %s", path, exc)
    except Exception as exc:
        log.warning("Failed to initialize revalidation client for %s: %s", _site_url(), exc)


def _read_json_file(path: Path) -> dict | list | None:
    """Read a JSON file and return parsed data, or None if not found."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to read %s: %s", path.name, exc)
        return None


def _replace_rows_for_date(
    sb: Client,
    table_name: str,
    date_column: str,
    target_date: str,
    new_rows: list[dict],
) -> bool:
    """Replace rows for a run date, restoring the previous state on failure.

    Supabase table operations here are not transactional. To avoid leaving a
    brief date empty after a failed insert, take a backup of existing rows and
    restore them if the replacement insert fails.
    """
    try:
        existing_resp = (
            sb.table(table_name)
            .select("*")
            .eq(date_column, target_date)
            .execute()
        )
        existing_rows = existing_resp.data or []
    except Exception as exc:
        log.error("Failed to read existing %s rows for %s: %s", table_name, target_date, exc)
        return False

    try:
        sb.table(table_name).delete().eq(date_column, target_date).execute()
        log.info("Deleted existing %s rows for %s", table_name, target_date)
    except Exception as exc:
        log.error("Failed to delete existing %s rows for %s: %s", table_name, target_date, exc)
        return False

    if not new_rows:
        return True

    try:
        sb.table(table_name).insert(new_rows).execute()
        log.info("Inserted %d %s rows for %s", len(new_rows), table_name, target_date)
        return True
    except Exception as exc:
        log.error("Failed to insert %s rows for %s: %s", table_name, target_date, exc)

        if not existing_rows:
            return False

        try:
            # Clear any partially restored state before attempting rollback.
            sb.table(table_name).delete().eq(date_column, target_date).execute()
        except Exception as cleanup_exc:
            log.warning(
                "Failed to clean up partial %s rows for %s before restore: %s",
                table_name,
                target_date,
                cleanup_exc,
            )

        try:
            sb.table(table_name).insert(existing_rows).execute()
            log.warning(
                "Restored %d previous %s rows for %s after failed replacement",
                len(existing_rows),
                table_name,
                target_date,
            )
        except Exception as restore_exc:
            log.critical(
                "ROLLBACK FAILED — %s table for %s is now EMPTY. "
                "Had %d rows before delete, insert of %d new rows failed, "
                "restore of %d original rows also failed: %s",
                table_name,
                target_date,
                len(existing_rows),
                len(new_rows),
                len(existing_rows),
                restore_exc,
            )
        return False


def _read_pipeline_stats(target_date: str) -> dict | None:
    """Read pipeline_stats_{date}.json if present."""
    path = OUTPUT_DIR / f"pipeline_stats_{target_date}.json"
    data = _read_json_file(path)
    return data if isinstance(data, dict) else None


def _output_mtimes(target_date: str) -> list[datetime]:
    """Return mtimes for pipeline artifacts that exist for the given date."""
    filenames = [
        f"collection_log_{target_date}.json",
        f"scout_output_raw_{target_date}.json",
        f"scout_output_{target_date}.json",
        f"content_filter_output_{target_date}.json",
        f"gatekeeper_output_{target_date}.json",
        f"ghostwriter_output_{target_date}.json",
        f"editor_output_{target_date}.json",
        f"brief_{target_date}.json",
    ]
    mtimes: list[datetime] = []
    for filename in filenames:
        path = OUTPUT_DIR / filename
        if path.exists():
            mtimes.append(datetime.fromtimestamp(path.stat().st_mtime, tz=DUBAI_TZ))
    return mtimes


def _count_raw_items(target_date: str) -> int | None:
    """Count items entering the content filter from scout_output_raw_{date}.json."""
    path = OUTPUT_DIR / f"scout_output_raw_{target_date}.json"
    data = _read_json_file(path)
    if isinstance(data, list):
        return len(data)
    return None


def _count_final_brief_items(brief: dict) -> int:
    """Count non-placeholder items emitted in the final brief payload."""
    items = brief.get("items", [])
    if not isinstance(items, list):
        return 0
    return sum(
        1
        for item in items
        if not item.get("is_placeholder", False)
        and item.get("depth") != "placeholder"
    )


def _build_brief_row(brief: dict) -> dict:
    """Build the row dict for the `briefs` table."""
    meta = brief["brief_metadata"]
    brief_date = meta["date"]
    collection = _parse_collection_log(brief_date)
    stats = _read_pipeline_stats(brief_date)

    items_reviewed = _count_raw_items(brief_date)
    if items_reviewed is None and collection:
        items_reviewed = collection["items_collected"]

    return {
        "brief_date": brief_date,
        "generated_at": meta["generated_at"],
        "item_count": meta["total_items"],
        "sources_consulted": len(collection["items_per_source"]) if collection else 0,
        "items_reviewed": items_reviewed or 0,
        "pipeline_cost_usd": (
            float(stats.get("total_cost_usd", 0))
            if stats and stats.get("total_cost_usd") is not None
            else 0
        ),
        "raw_json": brief,
        "executive_summary": None,
        "metadata": {
            "lead_story_id": meta.get("lead_story_id"),
            "section_counts": meta.get("section_counts", {}),
            "rejected_unknown_sections": meta.get("rejected_unknown_sections", 0),
        },
    }


def _build_item_rows(brief: dict) -> list[dict]:
    """Build a list of row dicts for the `brief_items` table.

    - Skips placeholders.
    - Computes section_order within each section (1-based, by rank).
    - Normalises empty source_url to None.
    """
    brief_date = brief["brief_metadata"]["date"]
    items = brief.get("items", [])

    # Filter out placeholders
    items = [
        item for item in items
        if not item.get("is_placeholder", False) and item.get("depth") != "placeholder"
    ]

    # Sort by rank to ensure deterministic section_order
    items.sort(key=lambda x: x.get("rank", 999))

    # Deduplicate by item_id (keep first occurrence, i.e. lowest rank)
    seen_ids: set[str] = set()
    unique_items: list[dict] = []
    for item in items:
        item_id = item.get("id", "")
        if item_id not in seen_ids:
            seen_ids.add(item_id)
            unique_items.append(item)
    items = unique_items

    # Compute section_order: within each section, enumerate by rank order
    section_counters: dict[str, int] = {}
    rows: list[dict] = []

    for item in items:
        section = item.get("section", "Unknown")
        section_counters[section] = section_counters.get(section, 0) + 1
        section_order = section_counters[section]

        continuity = item.get("continuity")

        # brief_items is a narrow cross-date index. Full item content lives
        # in briefs.raw_json (source of truth for the reader). Columns for
        # key_bullets/analysis/exhibits/primary_entity* and the always-null
        # geo/topic_relevance/news_significance placeholders were dropped
        # in migration 018; raw_content is retained on brief_items for
        # historical audit of pre-v2 briefs but not written by this path.
        row = {
            "brief_date": brief_date,
            "item_id": item["id"],
            "section": section,
            "section_order": section_order,
            "headline": item.get("headline", ""),
            "main_bullet": item.get("main_bullet", ""),
            "context": item.get("context"),
            "implication": item.get("implication"),
            "source_name": item.get("source_name"),
            "source_url": _normalize_url(item.get("source_url")),
            "significance": item.get("significance_level"),
            "composite_score": item.get("composite_score", 0),
            "is_continuity": continuity is not None,
            "continuity_days": 1 if continuity is not None else 0,
        }
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Pipeline data parsing
# ---------------------------------------------------------------------------

def _parse_collection_log(target_date: str) -> dict | None:
    """Parse collection_log_{date}.json for source-level data."""
    path = OUTPUT_DIR / f"collection_log_{target_date}.json"
    data = _read_json_file(path)
    if data is None or not isinstance(data, dict):
        return None

    sources = data.get("sources", [])
    items_per_source: dict[str, int] = {}
    source_errors: dict[str, str] = {}
    total_items = 0

    for src in sources:
        name = src.get("name", "unknown")
        articles = src.get("articles", 0)
        status = src.get("status", "unknown")
        items_per_source[name] = articles
        total_items += articles
        if status != "success":
            source_errors[name] = f"Status: {status}"

    return {
        "items_collected": total_items,
        "items_per_source": items_per_source,
        "source_errors": source_errors,
        "duration_seconds": int(data.get("total_seconds", 0)),
        "collection_log": data,
    }


def _count_scout_items(target_date: str) -> int | None:
    """Count items in scout_output_{date}.json (plain array)."""
    path = OUTPUT_DIR / f"scout_output_{target_date}.json"
    data = _read_json_file(path)
    if data is None:
        return None
    if isinstance(data, list):
        return len(data)
    return None


def _count_scout_raw_items(target_date: str) -> int | None:
    """Count items in scout_output_raw_{date}.json (post-dedup, pre-content-filter)."""
    path = OUTPUT_DIR / f"scout_output_raw_{target_date}.json"
    data = _read_json_file(path)
    if data is None:
        return None
    if isinstance(data, list):
        return len(data)
    return None


def _count_triage_items(target_date: str) -> int | None:
    """Count items after triage from triage_output_{date}.json."""
    path = OUTPUT_DIR / f"triage_output_{target_date}.json"
    data = _read_json_file(path)
    if data is None:
        return None
    if isinstance(data, dict):
        kept = data.get("kept")
        return kept if isinstance(kept, int) else None
    return None


def _count_triage_input_items(target_date: str) -> int | None:
    """Count items entering triage from triage_output_{date}.json."""
    path = OUTPUT_DIR / f"triage_output_{target_date}.json"
    data = _read_json_file(path)
    if data is None:
        return None
    if isinstance(data, dict):
        total_input = data.get("total_input")
        return total_input if isinstance(total_input, int) else None
    return None


def _count_content_filter_items(target_date: str) -> int | None:
    """Count items kept by content filter from content_filter_output_{date}.json.

    Handles both verdict shapes — the new prompt (post-refactor 2026-04-22)
    emits `decision: "KEEP"/"DROP"`, the legacy prompt emitted `keep: bool`
    (or a `verdict: "NEWS"/"NOT_NEWS"` older still). An item counts as kept
    if any of the three signals says so.
    """
    path = OUTPUT_DIR / f"content_filter_output_{target_date}.json"
    data = _read_json_file(path)
    if data is None:
        return None
    if isinstance(data, dict):
        verdicts = data.get("verdicts", [])
        kept = 0
        for v in verdicts:
            decision = v.get("decision")
            if decision == "KEEP":
                kept += 1
            elif decision == "DROP":
                continue
            elif v.get("keep") is True:
                kept += 1
            elif v.get("verdict") == "NEWS":
                kept += 1
        return kept
    return None


def _count_dropped_by_date(target_date: str) -> int | None:
    """Count items dropped by the date filter."""
    path = OUTPUT_DIR / f"dropped_by_date_{target_date}.json"
    data = _read_json_file(path)
    if data is None:
        return None
    if isinstance(data, dict):
        dropped_count = data.get("dropped_count")
        if isinstance(dropped_count, int):
            return dropped_count
        dropped = data.get("dropped", [])
        if isinstance(dropped, list):
            return len(dropped)
    return None


def _count_gatekeeper_items(target_date: str) -> int | None:
    """Count items selected by gatekeeper from gatekeeper_output_{date}.json."""
    path = OUTPUT_DIR / f"gatekeeper_output_{target_date}.json"
    data = _read_json_file(path)
    if data is None:
        return None
    if isinstance(data, dict):
        selected = data.get("selected", [])
        return len(selected)
    return None


def _parse_dropped_items(target_date: str) -> list[dict]:
    """Parse all dropped_by_* files for a date.

    Returns a list of dicts for the dropped_items table.
    """
    rows: list[dict] = []

    # 1. Dropped by date filter
    path = OUTPUT_DIR / f"dropped_by_date_{target_date}.json"
    data = _read_json_file(path)
    if data and isinstance(data, dict):
        for item in data.get("dropped", []):
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "date_filter",
                "drop_reason": item.get("drop_reason"),
                "composite_score": None,
                "raw_content": item,
            })

    # 2. Dropped by content filter
    path = OUTPUT_DIR / f"dropped_by_content_filter_{target_date}.json"
    data = _read_json_file(path)
    if data and isinstance(data, dict):
        for item in data.get("dropped", []):
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "content_filter",
                "drop_reason": item.get("drop_reason"),
                "composite_score": None,
                "raw_content": item,
            })

    # 3. Dropped by gatekeeper (model decision)
    path = OUTPUT_DIR / f"dropped_by_gatekeeper_{target_date}.json"
    data = _read_json_file(path)
    if data and isinstance(data, dict):
        for item in data.get("gatekeeper_model_dropped", []):
            score = item.get("composite_score")
            # PHASE 1 (drop visibility): post-Gatekeeper overlap drops carry a
            # _stage tag set upstream. Reclassify them so the admin Drops view
            # distinguishes overlap drops from model drops.
            stage = item.get("_stage") or "gatekeeper"
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source") or item.get("source_name"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": stage,
                "drop_reason": item.get("drop_reason"),
                "composite_score": float(score) if score is not None else None,
                "raw_content": item,
            })

        # 3b. Gatekeeper implicit drops — items that entered the Gatekeeper but
        # were returned in neither selected nor dropped. Previously lost
        # entirely; now surfaced as their own stage.
        for item in data.get("implicit_dropped", []):
            score = item.get("composite_score")
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source") or item.get("source_name"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "gatekeeper_implicit",
                "drop_reason": item.get("drop_reason")
                    or "Gatekeeper implicit (not returned in selected or dropped)",
                "composite_score": float(score) if score is not None else None,
                "raw_content": item,
            })

        # 3c. Post-Gatekeeper overlap drops written only into final_dropped
        # (not gatekeeper_model_dropped). Reclassify via the _stage tag.
        seen_post_gk_headlines = {
            r["headline"] for r in rows
            if r.get("dropped_at_stage") == "post_gatekeeper_overlap"
        }
        for item in data.get("final_dropped", []):
            if item.get("_stage") != "post_gatekeeper_overlap":
                continue
            headline = item.get("headline", "Unknown")
            if headline in seen_post_gk_headlines:
                continue
            score = item.get("composite_score")
            rows.append({
                "run_date": target_date,
                "headline": headline,
                "source_name": item.get("source") or item.get("source_name"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "post_gatekeeper_overlap",
                "drop_reason": item.get("drop_reason"),
                "composite_score": float(score) if score is not None else None,
                "raw_content": item,
            })
            seen_post_gk_headlines.add(headline)

    # PHASE 1 (drop visibility): NEW stages that were previously silent.

    # 4. Dropped by triage (Haiku relevance filter)
    path = OUTPUT_DIR / f"dropped_by_triage_{target_date}.json"
    data = _read_json_file(path)
    if data and isinstance(data, dict):
        for item in data.get("dropped", []):
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source") or item.get("source_name"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "triage",
                "drop_reason": item.get("drop_reason")
                    or "Triage: not relevant to MBZUAI brief",
                "composite_score": None,
                "raw_content": item,
            })

    # 5. Dropped by pre-Gatekeeper previous-brief overlap
    path = OUTPUT_DIR / f"dropped_by_previous_brief_overlap_{target_date}.json"
    data = _read_json_file(path)
    if data and isinstance(data, dict):
        for item in data.get("dropped", []):
            score = item.get("composite_score")
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source") or item.get("source_name"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "previous_brief_overlap",
                "drop_reason": item.get("drop_reason"),
                "composite_score": float(score) if score is not None else None,
                "raw_content": item,
            })

    # 6. Dropped by two-stage dedup (fuzzy + semantic). Previously silent —
    # surfaced as of the 2026-04-15 UAE-curation audit so the admin Drops
    # view can show per-source attrition at this stage too.
    path = OUTPUT_DIR / f"dropped_by_dedup_{target_date}.json"
    data = _read_json_file(path)
    if data and isinstance(data, dict):
        for item in data.get("dropped", []):
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source") or item.get("source_name"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "dedup",
                "drop_reason": item.get("drop_reason")
                    or "Dedup: merged into a richer duplicate",
                "composite_score": None,
                "raw_content": item,
            })

    # 7. Dropped by History Dedup (semantic repeat check against recent
    # published + pending briefs; runs after the deterministic
    # previous_brief_overlap tier). Added with PR #32.
    path = OUTPUT_DIR / f"dropped_by_history_dedup_{target_date}.json"
    data = _read_json_file(path)
    if data and isinstance(data, dict):
        for item in data.get("dropped", []):
            score = item.get("composite_score")
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source") or item.get("source_name"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "history_dedup",
                "drop_reason": item.get("drop_reason")
                    or "History dedup (semantic): flagged as repeat",
                "composite_score": float(score) if score is not None else None,
                "raw_content": item,
            })

    # 8. Dropped by web-search date verification. Newsletter-origin items
    # without verifiable dates get a Serper search; items whose median
    # result date precedes the cutoff are dropped as stale (e.g. a newsletter
    # re-surfacing weeks-old model-release coverage).
    path = OUTPUT_DIR / f"dropped_by_web_search_{target_date}.json"
    data = _read_json_file(path)
    if data and isinstance(data, dict):
        for item in data.get("dropped", []):
            median = item.get("web_search_median_date")
            cutoff = item.get("cutoff_date")
            default_reason = (
                f"Web search verify: median result date {median} "
                f"before cutoff {cutoff}"
                if median and cutoff
                else "Web search verify: stale newsletter item"
            )
            rows.append({
                "run_date": target_date,
                "headline": item.get("headline", "Unknown"),
                "source_name": item.get("source") or item.get("source_name"),
                "source_url": _normalize_url(item.get("source_url")),
                "dropped_at_stage": "web_search_verify",
                "drop_reason": item.get("drop_reason") or default_reason,
                "composite_score": None,
                "raw_content": item,
            })

    return rows


def _build_pipeline_run_row(target_date: str, brief: dict) -> dict:
    """Assemble the pipeline_runs row from intermediate output files."""
    meta = brief.get("brief_metadata", {})
    stats = _read_pipeline_stats(target_date)

    # Collection data
    collection = _parse_collection_log(target_date)

    # Stage counts
    triage_input_count = _count_triage_input_items(target_date)
    raw_item_count = _count_raw_items(target_date)
    items_collected = triage_input_count
    if items_collected is None:
        if collection:
            items_collected = collection["items_collected"]
    if items_collected is None:
        items_collected = raw_item_count
    if items_collected is None:
        scout_count = _count_scout_items(target_date)
        if scout_count is not None:
            items_collected = scout_count

    items_after_triage = _count_triage_items(target_date)
    items_after_dedup = _count_scout_raw_items(target_date)
    dropped_by_date_count = _count_dropped_by_date(target_date)
    items_after_date_filter = None
    if items_after_triage is not None and dropped_by_date_count is not None:
        items_after_date_filter = max(items_after_triage - dropped_by_date_count, 0)
    items_after_content_filter = _count_content_filter_items(target_date)
    items_after_gatekeeper = _count_gatekeeper_items(target_date)
    items_in_final_brief = _count_final_brief_items(brief)
    if items_in_final_brief == 0:
        items_in_final_brief = meta.get("total_items", 0)

    # Determine status
    status = "success"
    if collection and collection["source_errors"]:
        status = "partial"

    # Gatekeeper log — prefer enriched version (superset with _enrichment metadata)
    enriched_gatekeeper_path = OUTPUT_DIR / f"enriched_gatekeeper_output_{target_date}.json"
    gatekeeper_path = OUTPUT_DIR / f"gatekeeper_output_{target_date}.json"
    gatekeeper_log = _read_json_file(enriched_gatekeeper_path) or _read_json_file(gatekeeper_path)

    mtimes = _output_mtimes(target_date)
    started_at = None
    completed_at = meta.get("generated_at")
    duration_seconds = None
    if stats:
        started_at = stats.get("started_at")
        completed_at = stats.get("completed_at") or completed_at
        duration_seconds = stats.get("duration_seconds")
    elif mtimes:
        started_at = min(mtimes).isoformat(timespec="seconds")
        if not completed_at:
            completed_at = max(mtimes).isoformat(timespec="seconds")
        duration_seconds = int(round((max(mtimes) - min(mtimes)).total_seconds()))

    total_cost_usd = None
    if stats:
        total_cost_usd = stats.get("total_cost_usd")

    cost_breakdown = {}

    # Enrichment summary (lightweight, for historical charts)
    if isinstance(gatekeeper_log, dict):
        selected = gatekeeper_log.get("selected", [])
        enrichment_items = [
            item for item in selected
            if isinstance(item, dict) and isinstance(item.get("_enrichment"), dict)
        ]
        if enrichment_items:
            thin = [i for i in enrichment_items if i["_enrichment"].get("was_thin")]
            ok = [i for i in thin if i["_enrichment"].get("final_source", "none") != "none"]
            tok_in = sum(i["_enrichment"].get("tokens", {}).get("input", 0) for i in thin)
            tok_out = sum(i["_enrichment"].get("tokens", {}).get("output", 0) for i in thin)
            elapsed = sum(i["_enrichment"].get("elapsed_seconds", 0) for i in thin)
            orig_wc = sum(i["_enrichment"].get("original_word_count", 0) for i in thin)
            enr_wc = sum(i["_enrichment"].get("enriched_word_count", 0) for i in thin)
            n = len(thin) or 1
            fs_breakdown: dict[str, int] = {}
            stage_entered: dict[str, int] = {}
            stage_resolved: dict[str, int] = {}
            research_count = 0
            for i in enrichment_items:
                meta = i["_enrichment"]
                fs_val = meta.get("final_source", "none") or "none"
                fs_breakdown[fs_val] = fs_breakdown.get(fs_val, 0) + 1
                for stage in ["url_fetch", "web_search", "research_agent"]:
                    if stage in meta.get("steps_taken", []):
                        stage_entered[stage] = stage_entered.get(stage, 0) + 1
                if fs_val in ("url_fetch", "web_search", "research_agent"):
                    stage_resolved[fs_val] = stage_resolved.get(fs_val, 0) + 1
                if fs_val == "research_agent":
                    research_count += 1
            cost_breakdown["enrichment"] = {
                "total_items": len(enrichment_items),
                "thin_items": len(thin),
                "enriched_successfully": len(ok),
                "total_tokens_input": tok_in,
                "total_tokens_output": tok_out,
                "total_elapsed_seconds": round(elapsed, 1),
                "final_source_breakdown": fs_breakdown,
                "avg_original_word_count": round(orig_wc / n),
                "avg_enriched_word_count": round(enr_wc / n),
                "research_agent_count": research_count,
                "stage_entered": stage_entered,
                "stage_resolved": stage_resolved,
            }

    # Rationalization summary (lightweight, for admin dashboard)
    rationalization_path = OUTPUT_DIR / f"brief_rationalization_{target_date}.json"
    rationalization_data = _read_json_file(rationalization_path)
    if isinstance(rationalization_data, dict) and rationalization_data.get("swaps") is not None:
        cost_breakdown["rationalization"] = {
            "swaps": rationalization_data.get("swaps", 0),
            "demoted_count": len(rationalization_data.get("demoted", [])),
            "promoted_count": len(rationalization_data.get("promoted", [])),
            "demoted": rationalization_data.get("demoted", []),
            "promoted": rationalization_data.get("promoted", []),
            "editorial_note": rationalization_data.get("editorial_note", ""),
            "selected_count_before": rationalization_data.get("selected_count_before"),
            "selected_count_after": rationalization_data.get("selected_count_after"),
            "promotion_pool_size": rationalization_data.get("promotion_pool_size"),
            "input_tokens": rationalization_data.get("input_tokens", 0),
            "output_tokens": rationalization_data.get("output_tokens", 0),
        }

    return {
        "run_date": target_date,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": duration_seconds,
        "items_collected": items_collected,
        "items_after_triage": items_after_triage,
        "items_after_date_filter": items_after_date_filter,
        "items_after_dedup": items_after_dedup,
        "items_after_content_filter": items_after_content_filter,
        "items_after_gatekeeper": items_after_gatekeeper,
        "items_in_final_brief": items_in_final_brief,
        "items_per_source": collection["items_per_source"] if collection else {},
        "sources_count": (
            len(collection["items_per_source"])
            if collection
            else 0
        ),
        "source_errors": collection["source_errors"] if collection else {},
        "total_cost_usd": total_cost_usd,
        "cost_breakdown": cost_breakdown,
        "collection_log": collection["collection_log"] if collection else None,
        "gatekeeper_log": gatekeeper_log,
    }


# ---------------------------------------------------------------------------
# Ingest logic
# ---------------------------------------------------------------------------

def ingest_brief(sb: Client, brief_path: Path) -> bool:
    """Ingest a single brief JSON file into Supabase.

    Returns True on success, False on failure.
    """
    log.info("Ingesting %s", brief_path.name)

    try:
        with open(brief_path, "r", encoding="utf-8") as f:
            brief = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to read %s: %s", brief_path, exc)
        return False

    brief_date = brief.get("brief_metadata", {}).get("date")
    if not brief_date:
        log.error("No brief_metadata.date found in %s", brief_path.name)
        return False

    # --- Upsert into briefs table ---
    brief_row = _build_brief_row(brief)
    try:
        sb.table("briefs").upsert(
            brief_row,
            on_conflict="brief_date",
        ).execute()
        log.info("Upserted brief for %s", brief_date)
    except Exception as exc:
        log.error("Failed to upsert brief %s: %s", brief_date, exc)
        return False

    # --- Delete existing items for this date, then insert new ones ---
    item_rows = _build_item_rows(brief)

    if not _replace_rows_for_date(sb, "brief_items", "brief_date", brief_date, item_rows):
        return False

    # --- Pipeline run data ---
    pipeline_row = _build_pipeline_run_row(brief_date, brief)
    try:
        sb.table("pipeline_runs").upsert(
            pipeline_row,
            on_conflict="run_date",
        ).execute()
        log.info("Upserted pipeline_run for %s", brief_date)
    except Exception as exc:
        log.error("Failed to upsert pipeline_run %s: %s", brief_date, exc)
        return False

    # --- Dropped items ---
    dropped_rows = _parse_dropped_items(brief_date)
    if not _replace_rows_for_date(sb, "dropped_items", "run_date", brief_date, dropped_rows):
        return False

    # --- Summary ---
    log.info(
        "SUCCESS  date=%s  items=%d  dropped=%d  file=%s",
        brief_date,
        len(item_rows),
        len(dropped_rows),
        brief_path.name,
    )
    _revalidate_frontend(brief_date)
    return True


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def _find_brief_file(target_date: date) -> Path | None:
    """Return the path to a brief file for the given date, or None."""
    filename = f"brief_{target_date.isoformat()}.json"
    path = OUTPUT_DIR / filename
    return path if path.exists() else None


def _find_all_brief_files() -> list[Path]:
    """Return all brief_*.json files in the output directory, sorted by name."""
    if not OUTPUT_DIR.exists():
        return []
    return sorted(OUTPUT_DIR.glob("brief_*.json"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    _require_python_310_plus()

    parser = argparse.ArgumentParser(
        description="Ingest daily brief JSON files into Supabase."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Ingest a specific date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Ingest all brief files found in the output directory.",
    )
    args = parser.parse_args()

    _load_env()
    sb = _get_supabase_client()

    files_to_ingest: list[Path] = []

    if args.backfill:
        files_to_ingest = _find_all_brief_files()
        if not files_to_ingest:
            log.warning("No brief files found in %s", OUTPUT_DIR)
            sys.exit(0)
        log.info("Backfill mode: found %d brief files", len(files_to_ingest))
    else:
        if args.date:
            try:
                target = date.fromisoformat(args.date)
            except ValueError:
                log.error("Invalid date format: %s (expected YYYY-MM-DD)", args.date)
                sys.exit(1)
        else:
            target = _today_in_dubai()

        path = _find_brief_file(target)
        if path is None:
            log.error("No brief file found for %s (expected %s)", target, OUTPUT_DIR / f"brief_{target}.json")
            sys.exit(1)
        files_to_ingest = [path]

    # Process each file
    success_count = 0
    fail_count = 0

    for brief_path in files_to_ingest:
        ok = ingest_brief(sb, brief_path)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    # Final summary
    log.info("=" * 60)
    log.info(
        "Ingestion complete: %d succeeded, %d failed, %d total",
        success_count,
        fail_count,
        success_count + fail_count,
    )
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
