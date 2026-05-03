#!/usr/bin/env python3
"""
Remove test brief data from Supabase.

Usage:
    cd backend
    python3.11 tests/cleanup_test_brief.py                   # Clean 2026-12-25
    python3.11 tests/cleanup_test_brief.py --date 2026-12-26  # Clean specific date
    python3.11 tests/cleanup_test_brief.py --all               # Clean all test dates
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_project_env
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cleanup_test_brief")

TEST_DATES = ["2026-12-25", "2026-12-26"]


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


def cleanup(dates: list[str]):
    _load_env()
    sb = _get_client()

    tables = [
        ("brief_items", "brief_date"),
        ("briefs", "brief_date"),
        ("dropped_items", "run_date"),
        ("pipeline_runs", "run_date"),
    ]

    for target_date in dates:
        for table, col in tables:
            try:
                resp = sb.table(table).delete().eq(col, target_date).execute()
                count = len(resp.data) if resp.data else 0
                if count > 0:
                    log.info("Deleted %d rows from %s for %s", count, table, target_date)
            except Exception as e:
                log.warning("Failed to delete from %s for %s: %s", table, target_date, e)

    print(f"\n  Cleaned up test data for: {', '.join(dates)}\n")


def main():
    parser = argparse.ArgumentParser(description="Remove test brief data from Supabase")
    parser.add_argument("--date", help="Specific date to clean (default: 2026-12-25)")
    parser.add_argument("--all", action="store_true", help="Clean all test dates (2026-12-25, 2026-12-26)")
    args = parser.parse_args()

    if args.all:
        cleanup(TEST_DATES)
    elif args.date:
        cleanup([args.date])
    else:
        cleanup(["2026-12-25"])


if __name__ == "__main__":
    main()
