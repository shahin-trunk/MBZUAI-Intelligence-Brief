#!/usr/bin/env python3
"""
Fix missing French V3 audio files.

The V3 learning content pipeline generates audio files with naming like:
    {target_date}/learning/{item_id}_{lang}_p{phrase_idx}_s{script_idx}.mp3

French `learning_fr` data has V3 text content but the audio files on Supabase
storage were never generated with the correct V3 names — only old V2 naming
(e.g., `_fr_context_intro.mp3`). This script reads the existing V3 French
content from `raw_json` in the `briefs` table and generates the missing audio.

Usage:
    python3.11 fix_french_audio.py                          # Fix all missing French audio
    python3.11 fix_french_audio.py --date 2026-05-07        # Single date
    python3.11 fix_french_audio.py --date 2026-05-07 --dry-run  # Preview only
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Load env & paths
# ---------------------------------------------------------------------------
load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fix_french_audio")

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    log.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    sys.exit(1)

sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------------------------
# TTS config
# ---------------------------------------------------------------------------
VOICE_API_KEY = os.getenv("VOICE_API_KEY")
VOICE_BASE_URL = os.getenv("VOICE_BASE_URL", "https://api.elevenlabs.io")
VOICE_MODEL_ID = os.getenv("VOICE_MODEL_ID", "eleven_multilingual_v2")
VOICE_SETTINGS = {
    "stability": 0.35,
    "similarity_boost": 0.75,
    "style": 0.15,
    "use_speaker_boost": True,
}
VOICE_SPEED_EN = 1.05
VOICE_SPEED_FR = 0.95
VOICE_MAX_CHARS = 5000


def _get_voice_config() -> dict:
    """Load voice config from env or fallback to defaults."""
    try:
        voices = json.loads(os.getenv("VOICE_CONFIG", "{}"))
        if voices:
            return voices
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "en": {"voice_id": "21m00Tcm4TlvDq8ikWAM"},
        "fr": {"voice_id": "21m00Tcm4TlvDq8ikWAM"},
        "ar": {"voice_id": "21m00Tcm4TlvDq8ikWAM"},
    }


def _generate_audio(script: str, voice_id: str | None = None, lang: str = "en") -> bytes:
    """Send script to ElevenLabs TTS API, return MP3 bytes."""
    import httpx

    if not VOICE_API_KEY:
        raise RuntimeError("VOICE_API_KEY not set")

    if voice_id is None:
        voice_id = _get_voice_config()["en"]["voice_id"]

    # Split if too long
    words = script.split()
    if len(words) > 1000:
        # Take first 1000 words to stay within limits
        script = " ".join(words[:1000])

    url = f"{VOICE_BASE_URL}/v1/text-to-speech/{voice_id}"
    payload = {
        "text": script,
        "model_id": VOICE_MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
    }
    if lang == "en":
        payload["speed"] = VOICE_SPEED_EN
    elif lang == "fr":
        payload["speed"] = VOICE_SPEED_FR
    else:
        payload["speed"] = 1.0

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": VOICE_API_KEY,
    }

    timeout = httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=60.0)
    with httpx.Client(timeout=timeout) as client:
        log.info("  TTS request for %d chars (%s, lang=%s)...", len(script), lang, lang)
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.content


def _upload_audio(sb: Client, file_path: str, audio_bytes: bytes) -> str | None:
    """Upload MP3 bytes to Supabase storage and return public URL."""
    try:
        sb.storage.from_("audio-briefs").upload(
            file_path,
            audio_bytes,
            file_options={"content-type": "audio/mpeg", "upsert": "true"},
        )
        url = sb.storage.from_("audio-briefs").get_public_url(file_path)
        log.info("  ✓ Uploaded: %s", file_path)
        return url
    except Exception as exc:
        log.warning("  ✗ Upload failed for %s: %s", file_path, exc)
        return None


def _phrase_script_text(phrase: dict, script_idx: int) -> str:
    """Get the text for a given script index (1-4)."""
    return phrase.get(f"script{script_idx}", "").strip()


def _check_audio_exists(sb: Client, file_path: str) -> bool:
    """Check if audio file already exists in storage."""
    try:
        sb.storage.from_("audio-briefs").list(
            str(Path(file_path).parent)
        )
        # Check specific file by trying to get its metadata
        # Supabase doesn't have a direct exists check, so we try to get public URL
        url = sb.storage.from_("audio-briefs").get_public_url(file_path)
        # Attempt a HEAD request
        import httpx
        with httpx.Client() as client:
            resp = client.head(url)
            return resp.status_code == 200
    except Exception:
        return False


def fix_french_audio_for_brief(brief_date: str, dry_run: bool = False) -> int:
    """Fix missing French V3 audio for all items in a brief.
    
    Returns count of audio files generated.
    """
    log.info("Processing brief %s (dry_run=%s)", brief_date, dry_run)
    
    # Fetch the brief
    resp = sb.table("briefs").select("brief_date, raw_json").eq("brief_date", brief_date).execute()
    if not resp.data:
        log.warning("No brief found for %s", brief_date)
        return 0
    
    raw_json = resp.data[0].get("raw_json", {})
    if not raw_json:
        log.warning("No raw_json for %s", brief_date)
        return 0
    
    items = raw_json.get("items", [])
    if not items:
        log.warning("No items in brief %s", brief_date)
        return 0
    
    voice_config = _get_voice_config()
    en_voice = voice_config.get("en", {}).get("voice_id", "21m00Tcm4TlvDq8ikWAM")
    fr_voice = voice_config.get("fr", {}).get("voice_id", "21m00Tcm4TlvDq8ikWAM")
    
    total_generated = 0
    total_skipped = 0
    total_errors = 0
    
    for item in items:
        item_id = item.get("id", "")
        if not item_id:
            continue
        
        learning_fr = item.get("learning_fr")
        if not learning_fr or not isinstance(learning_fr, dict):
            continue
        
        phrases = learning_fr.get("phrases", [])
        if not phrases:
            log.info("  Item %s: no French phrases", item_id)
            continue
        
        log.info("  Item %s: %d phrase(s)", item_id, len(phrases))
        
        item_errors = 0
        item_generated = 0
        
        for p_idx, phrase in enumerate(phrases):
            for s_idx in range(1, 5):
                script_text = _phrase_script_text(phrase, s_idx)
                if not script_text or len(script_text) < 10:
                    log.info("    p%s_s%s: skipped (text too short)", p_idx, s_idx)
                    continue
                
                # Check if audio already exists (based on data)
                existing_url = phrase.get(f"audio_url_{s_idx}")
                if existing_url:
                    log.info("    p%s_s%s: already has URL, skipping", p_idx, s_idx)
                    total_skipped += 1
                    continue
                
                file_path = f"{brief_date}/learning/{item_id}_fr_p{p_idx}_s{s_idx}.mp3"
                
                # Determine voice: script3 is French, others are English
                voice = fr_voice if s_idx == 3 else en_voice
                lang = "fr" if s_idx == 3 else "en"
                
                if dry_run:
                    log.info("    p%s_s%s: would generate (path=%s, lang=%s)", p_idx, s_idx, file_path, lang)
                    continue
                
                try:
                    log.info("    p%s_s%s: generating audio (%d chars, lang=%s)...", p_idx, s_idx, len(script_text), lang)
                    audio_bytes = _generate_audio(script_text, voice, lang=lang)
                    
                    url = _upload_audio(sb, file_path, audio_bytes)
                    if url:
                        # Update the phrase's audio_url in the raw_json
                        phrase[f"audio_url_{s_idx}"] = url
                        item_generated += 1
                        total_generated += 1
                    else:
                        item_errors += 1
                        total_errors += 1
                    
                    # Rate limit: small delay between API calls
                    time.sleep(0.5)
                    
                except Exception as exc:
                    log.warning("    p%s_s%s: ERROR: %s", p_idx, s_idx, exc)
                    item_errors += 1
                    total_errors += 1
        
        log.info("    Item %s done: %d generated, %d errors", item_id, item_generated, item_errors)
    
    # Save updated raw_json back to Supabase
    if not dry_run and total_generated > 0:
        try:
            sb.table("briefs").update({"raw_json": raw_json}).eq("brief_date", brief_date).execute()
            log.info("Saved updated raw_json with %d new audio URLs", total_generated)
        except Exception as exc:
            log.warning("Failed to update raw_json: %s", exc)
    
    log.info("Brief %s complete: %d generated, %d skipped, %d errors", 
              brief_date, total_generated, total_skipped, total_errors)
    return total_generated


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix missing French V3 audio files")
    parser.add_argument("--date", type=str, default=None, help="Brief date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no generation")
    args = parser.parse_args()
    
    if args.date:
        brief_dates = [args.date]
    else:
        # Find all briefs with V3 French content
        log.info("Scanning for briefs with French V3 learning content...")
        # Fetch recent briefs (last 30 days)
        resp = sb.table("briefs").select("brief_date").order("brief_date", desc=True).limit(30).execute()
        brief_dates = []
        for row in resp.data:
            brief_date = row["brief_date"]
            # Check if it has French V3 content
            try:
                brief_resp = sb.table("briefs").select("raw_json").eq("brief_date", brief_date).execute()
                if not brief_resp.data:
                    continue
                rj = brief_resp.data[0].get("raw_json", {})
                items = rj.get("items", [])
                for item in items:
                    lf = item.get("learning_fr")
                    if lf and isinstance(lf, dict) and lf.get("version") == 3:
                        brief_dates.append(brief_date)
                        break
            except Exception:
                continue
    
    if not brief_dates:
        log.info("No briefs with French V3 content found")
        return
    
    log.info("Found %d brief(s) with French V3 content: %s", len(brief_dates), brief_dates)
    
    total = 0
    for bd in brief_dates:
        total += fix_french_audio_for_brief(bd, dry_run=args.dry_run)
    
    log.info("All done! Generated %d audio files total.", total)


if __name__ == "__main__":
    main()
