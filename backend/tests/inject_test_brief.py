#!/usr/bin/env python3
"""
Inject a rich test brief fixture into Supabase for visual verification.

Usage:
    cd backend
    python3.11 tests/inject_test_brief.py                  # Inject 2026-12-25 fixture
    python3.11 tests/inject_test_brief.py --date 2026-12-26  # Inject with custom date
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure backend root is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_project_env
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("inject_test_brief")

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DEFAULT_DATE = "2026-12-25"


def _load_env():
    for path in load_project_env():
        log.info("Loaded env from %s", path)


def _get_client():
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    return create_client(url, key)


def _normalize_url(url):
    return url if url else None


def _build_brief_row(fixture: dict) -> dict:
    """Build briefs table row directly (no pipeline file dependencies)."""
    meta = fixture["brief_metadata"]
    return {
        "brief_date": meta["date"],
        "generated_at": meta["generated_at"],
        "item_count": meta["total_items"],
        "sources_consulted": 0,
        "items_reviewed": 0,
        "pipeline_cost_usd": 0,
        "raw_json": fixture,
        "executive_summary": None,
        "metadata": {
            "lead_story_id": meta.get("lead_story_id"),
            "section_counts": meta.get("section_counts", {}),
        },
    }


def _build_item_rows(fixture: dict) -> list[dict]:
    """Build brief_items table rows (same logic as ingest_brief.py)."""
    brief_date = fixture["brief_metadata"]["date"]
    items = fixture.get("items", [])
    items = [i for i in items if not i.get("is_placeholder") and i.get("depth") != "placeholder"]
    items.sort(key=lambda x: x.get("rank", 999))

    section_counters: dict[str, int] = {}
    rows = []
    for item in items:
        section = item.get("section", "Unknown")
        section_counters[section] = section_counters.get(section, 0) + 1

        # Shape matches the narrow post-018 brief_items schema. Content
        # columns (key_bullets/analysis/exhibits/primary_entity) and
        # always-null placeholders (topic_relevance/news_significance/
        # geo_*) were dropped — see migration 018. raw_content is still
        # on the table for historical audit but not written here.
        rows.append({
            "brief_date": brief_date,
            "item_id": item["id"],
            "section": section,
            "section_order": section_counters[section],
            "headline": item.get("headline", ""),
            "main_bullet": item.get("main_bullet", ""),
            "context": item.get("context"),
            "implication": item.get("implication"),
            "source_name": item.get("source_name"),
            "source_url": _normalize_url(item.get("source_url")),
            "significance": item.get("significance_level"),
            "composite_score": item.get("composite_score", 0),
            "is_continuity": item.get("continuity") is not None,
            "continuity_days": 1 if item.get("continuity") is not None else 0,
        })
    return rows


def inject(target_date: str):
    _load_env()
    sb = _get_client()

    fixture_path = FIXTURES_DIR / f"brief_{target_date}.json"
    if not fixture_path.exists():
        log.error("Fixture not found: %s", fixture_path)
        sys.exit(1)

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Ensure the fixture date matches the target date
    fixture["brief_metadata"]["date"] = target_date
    for item in fixture.get("items", []):
        item["id"] = item["id"].replace(DEFAULT_DATE, target_date)

    # Upsert brief row
    brief_row = _build_brief_row(fixture)
    sb.table("briefs").upsert(brief_row, on_conflict="brief_date").execute()
    log.info("Upserted brief for %s", target_date)

    # Replace item rows
    sb.table("brief_items").delete().eq("brief_date", target_date).execute()
    item_rows = _build_item_rows(fixture)
    if item_rows:
        sb.table("brief_items").insert(item_rows).execute()
    log.info("Inserted %d brief_items for %s", len(item_rows), target_date)

    print(f"\n  Injected {len(item_rows)} items for {target_date}")
    print(f"  Visit: http://localhost:3000/brief/{target_date}\n")


def main():
    parser = argparse.ArgumentParser(description="Inject test brief fixture into Supabase")
    parser.add_argument("--date", default=DEFAULT_DATE, help="Target brief date (default: 2026-12-25)")
    args = parser.parse_args()
    inject(args.date)


if __name__ == "__main__":
    main()
