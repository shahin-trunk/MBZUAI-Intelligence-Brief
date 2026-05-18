#!/usr/bin/env python3
"""
Targeted French audio regeneration for specific items with missing audio.

Scans the brief for items where French audio URLs are missing/null,
and regenerates ONLY the missing audio files without touching existing ones.

Usage:
    python backend/scripts/regenerate_missing_french_audio.py --date 2026-05-07
    python backend/scripts/regenerate_missing_french_audio.py --date 2026-05-07 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent.parent                # backend/
PROJECT_ROOT = SCRIPT_DIR.parent

load_dotenv(SCRIPT_DIR / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ARGENT_API_KEY = os.getenv("ARGENT_API_KEY")

# Import functions from generate_audio.py
sys.path.insert(0, str(SCRIPT_DIR))
from generate_audio import (
    _generate_phrase_audio,
    _get_voice_config,
)


def get_supabase_client() -> Client:
    """Create Supabase client with service role key."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def find_items_with_missing_french_audio(target_date: str) -> list[dict]:
    """Find items that have French learning content but missing audio URLs.
    
    Returns list of dicts with:
    - item_id: str
    - phrases: list of phrase dicts that have missing audio
    """
    sb = get_supabase_client()
    
    result = sb.table("briefs").select("raw_json").eq("brief_date", target_date).single().execute()
    brief_json = result.data.get("raw_json", {})
    items = brief_json.get("items", [])
    
    missing_items = []
    
    for item in items:
        learning_fr = item.get("learning_fr")
        if not learning_fr:
            continue
            
        phrases = learning_fr.get("phrases", [])
        if not phrases:
            continue
        
        # Check if ALL phrases have missing audio
        phrases_with_missing_audio = []
        for p_idx, phrase in enumerate(phrases):
            has_any_audio = any(
                phrase.get(f"audio_url_{s_idx}")
                for s_idx in range(1, 4)
            )
            if not has_any_audio:
                phrases_with_missing_audio.append({
                    "phrase_idx": p_idx,
                    "phrase": phrase,
                })
        
        if phrases_with_missing_audio:
            missing_items.append({
                "item_id": item.get("id"),
                "phrases": phrases_with_missing_audio,
                "item": item,  # full item for context
            })
    
    return missing_items


def regenerate_audio_for_item(
    sb: Client,
    target_date: str,
    item_data: dict,
    voice_config: dict,
    dry_run: bool = False,
) -> dict:
    """Regenerate missing French audio for a single item.
    
    Returns stats dict with success/fail counts.
    """
    item_id = item_data["item_id"]
    phrases = item_data["phrases"]
    
    en_voice = voice_config.get("en", {}).get("voice_id", "")
    fr_voice = voice_config.get("fr", {}).get("voice_id", "")
    
    stats = {"success": 0, "failed": 0, "skipped": 0}
    
    log.info("Processing item %s: %d phrases with missing audio", item_id, len(phrases))
    
    for phrase_data in phrases:
        p_idx = phrase_data["phrase_idx"]
        phrase = phrase_data["phrase"]
        
        # Scripts 1, 2 use English voice; Script 3 uses French voice
        scripts_to_generate = [
            (1, phrase.get("script1", ""), en_voice, "en"),
            (2, phrase.get("script2", ""), en_voice, "en"),
            (3, phrase.get("script3", ""), fr_voice, "fr"),
        ]
        
        for s_idx, script_text, voice, lang in scripts_to_generate:
            if not script_text or len(script_text) < 10:
                log.info("  Skipping p%d_s%d: script too short", p_idx, s_idx)
                stats["skipped"] += 1
                continue
            
            if dry_run:
                log.info("  [DRY RUN] Would generate: p%d_s%d (%s voice)", p_idx, s_idx, lang)
                stats["success"] += 1
                continue
            
            log.info("  Generating audio for p%d_s%d (%s)...", p_idx, s_idx, lang)
            try:
                audio_url = _generate_phrase_audio(
                    sb, script_text, voice, target_date,
                    item_id, "fr", p_idx, s_idx,
                )
                if audio_url:
                    # Update the phrase in the item data
                    item_data["item"]["learning_fr"]["phrases"][p_idx][f"audio_url_{s_idx}"] = audio_url
                    stats["success"] += 1
                    log.info("  ✓ Generated: %s", audio_url)
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                else:
                    stats["failed"] += 1
                    log.error("  ✗ Failed: p%d_s%d returned None", p_idx, s_idx)
            except Exception as exc:
                stats["failed"] += 1
                log.error("  ✗ Failed: p%d_s%d - %s", p_idx, s_idx, exc)
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Regenerate missing French audio for specific items")
    parser.add_argument("--date", required=True, help="Brief date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without creating audio")
    args = parser.parse_args()
    
    target_date = args.date
    dry_run = args.dry_run
    
    log.info("=" * 60)
    log.info("Targeted French Audio Regeneration")
    log.info("Date: %s", target_date)
    log.info("Dry run: %s", dry_run)
    log.info("=" * 60)
    
    # Find items with missing audio
    log.info("Scanning for items with missing French audio...")
    missing_items = find_items_with_missing_french_audio(target_date)
    
    if not missing_items:
        log.info("✓ All items have complete French audio! Nothing to regenerate.")
        return
    
    log.info("Found %d items with missing French audio:", len(missing_items))
    for item in missing_items:
        log.info("  - %s (%d phrases missing audio)", item["item_id"], len(item["phrases"]))
    
    if dry_run:
        log.info("\n[DRY RUN] Would regenerate audio for the above items.")
        log.info("Remove --dry-run to actually generate audio files.")
        return
    
    # Get voice config
    voice_config = _get_voice_config()
    sb = get_supabase_client()
    
    # Regenerate audio for each item
    total_stats = {"success": 0, "failed": 0, "skipped": 0}
    
    log.info("\nStarting audio regeneration...")
    for item_data in missing_items:
        item_stats = regenerate_audio_for_item(sb, target_date, item_data, voice_config, dry_run=False)
        for key in total_stats:
            total_stats[key] += item_stats[key]
        
        log.info("  Item %s: %d succeeded, %d failed, %d skipped",
                item_data["item_id"],
                item_stats["success"],
                item_stats["failed"],
                item_stats["skipped"])
    
    # Save updated raw_json
    if total_stats["success"] > 0:
        log.info("\nSaving updated learning content to database...")
        result = sb.table("briefs").select("raw_json").eq("brief_date", target_date).single().execute()
        brief_json = result.data.get("raw_json", {})
        
        # Update the items in brief_json
        updated_items = {item["item_id"]: item["item"] for item in missing_items}
        for i, item in enumerate(brief_json.get("items", [])):
            if item.get("id") in updated_items:
                brief_json["items"][i] = updated_items[item["id"]]
        
        sb.table("briefs").update({"raw_json": brief_json}).eq("brief_date", target_date).execute()
        log.info("✓ Database updated with new audio URLs")
    
    # Summary
    log.info("\n" + "=" * 60)
    log.info("SUMMARY")
    log.info("=" * 60)
    log.info("Total audio files generated: %d", total_stats["success"])
    log.info("Total failed: %d", total_stats["failed"])
    log.info("Total skipped: %d", total_stats["skipped"])
    
    if total_stats["failed"] > 0:
        log.warning("\n⚠ Some audio generation failed. Check logs for details.")
        sys.exit(1)
    else:
        log.info("\n✓ All missing French audio regenerated successfully!")


if __name__ == "__main__":
    main()
