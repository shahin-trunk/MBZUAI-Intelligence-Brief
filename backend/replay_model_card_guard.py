"""
Replay model-card classification against a saved brief in Supabase.

Example:
  python3.11 backend/replay_model_card_guard.py --date 2026-03-27

The script fetches the saved brief JSON, re-runs the current backend
model-release decision logic for any saved model-release items (or
headline-filtered items), and prints whether each item would still be
classified as model-card eligible.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

from config import ANTHROPIC_API_KEY
from pipeline.enricher import _finalize_model_release_flag


def load_env() -> None:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env", override=True)
    load_dotenv(root / "frontend" / ".env.local", override=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay model-card eligibility for a saved brief.")
    parser.add_argument("--date", required=True, help="Brief date in YYYY-MM-DD format.")
    parser.add_argument(
        "--headline-substring",
        action="append",
        default=[],
        help="Optional case-insensitive headline substring filter. Repeatable.",
    )
    return parser.parse_args()


def fetch_brief_items(brief_date: str) -> list[dict]:
    url = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, key)
    rows = (
        client.table("briefs")
        .select("raw_json")
        .eq("brief_date", brief_date)
        .execute()
        .data
    )
    if not rows:
        raise ValueError(f"No brief found for {brief_date}")
    raw_json = rows[0]["raw_json"] or {}
    return list(raw_json.get("items") or [])


def select_items(items: list[dict], substrings: list[str]) -> list[dict]:
    if substrings:
        needles = [needle.lower() for needle in substrings]
        return [
            item
            for item in items
            if any(needle in str(item.get("headline", "")).lower() for needle in needles)
        ]
    return [item for item in items if item.get("is_model_release")]


async def replay(items: list[dict]) -> int:
    client = None
    if ANTHROPIC_API_KEY:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    print(json.dumps({"checked_items": len(items)}, indent=2))
    for item in items:
        replay_item = copy.deepcopy(item)
        result = await _finalize_model_release_flag(replay_item, client)
        classifier_meta = replay_item.get("_model_release_classifier", {})
        print("\n---")
        print(f"headline: {item.get('headline')}")
        print(f"saved_is_model_release: {bool(item.get('is_model_release'))}")
        print(f"replayed_is_model_release: {result}")
        print(f"heuristic_decision: {classifier_meta.get('heuristic_decision')}")
        print(f"decision_source: {classifier_meta.get('decision_source', 'heuristic')}")
        if classifier_meta.get("reason"):
            print(f"reason: {classifier_meta.get('reason')}")
    return 0


def main() -> int:
    load_env()
    args = parse_args()
    items = fetch_brief_items(args.date)
    selected = select_items(items, args.headline_substring)
    if not selected:
        print("No matching items found.")
        return 1
    return asyncio.run(replay(selected))


if __name__ == "__main__":
    raise SystemExit(main())
