"""Celery tasks for Argent TTS audio generation.

Queue: audio
"""
import logging
import os
import sys
from pathlib import Path

from celery_app import celery_app

# Ensure backend directory is on the Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from generate_audio import _generate_audio, _get_voice_config

log = logging.getLogger("celery.audio")


@celery_app.task(
    bind=True,
    queue="audio",
    max_retries=3,
    default_retry_delay=10,
    name="tasks.audio_tasks.generate_item_audio",
)
def generate_item_audio(
    self,
    target_date: str,
    item_id: str,
    script: str,
    voice_id: str,
    lang: str = "en",
) -> dict:
    """Generate TTS audio for a single briefing item script.

    Returns:
        {"target_date": str, "item_id": str, "audio_url": str}
    """
    from supabase import create_client

    log.info("Generating item audio for %s (attempt %s)", item_id, self.request.retries + 1)

    try:
        sb = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        )

        audio_bytes = _generate_audio(script, voice_id, lang=lang)
        file_path = f"{target_date}/items/{item_id}.mp3"

        sb.storage.from_("audio-briefs").upload(
            file_path,
            audio_bytes,
            file_options={"content-type": "audio/mpeg", "upsert": "true"},
        )
        public_url = sb.storage.from_("audio-briefs").get_public_url(file_path)

        return {
            "target_date": target_date,
            "item_id": item_id,
            "audio_url": public_url,
        }

    except Exception as exc:
        log.warning("Item audio failed for %s: %s", item_id, exc)
        raise self.retry(exc=exc, countdown=min(30 * (2 ** self.request.retries), 180))


@celery_app.task(
    bind=True,
    queue="audio",
    max_retries=3,
    default_retry_delay=10,
    name="tasks.audio_tasks.generate_phrase_audio",
)
def generate_phrase_audio(
    self,
    target_date: str,
    item_id: str,
    lang: str,
    phrase_idx: int,
    script_idx: int,
    script_text: str,
    voice_id: str,
) -> dict:
    """Generate TTS audio for a single learning phrase script.

    Path: {target_date}/learning/{item_id}_{lang}_p{phrase_idx}_s{script_idx}.mp3

    Returns:
        {"phrase_idx": int, "script_idx": int, "audio_url": str}
    """
    from supabase import create_client

    log.info(
        "Generating phrase audio p%s_s%s for item %s (attempt %s)",
        phrase_idx, script_idx, item_id, self.request.retries + 1,
    )

    try:
        sb = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        )

        audio_bytes = _generate_audio(script_text, voice_id, lang=lang)
        file_path = f"{target_date}/learning/{item_id}_{lang}_p{phrase_idx}_s{script_idx}.mp3"

        sb.storage.from_("audio-briefs").upload(
            file_path,
            audio_bytes,
            file_options={"content-type": "audio/mpeg", "upsert": "true"},
        )
        public_url = sb.storage.from_("audio-briefs").get_public_url(file_path)

        return {
            "phrase_idx": phrase_idx,
            "script_idx": script_idx,
            "audio_url": public_url,
        }

    except Exception as exc:
        log.warning(
            "Phrase audio failed for item %s p%s_s%s (%s): %s",
            item_id, phrase_idx, script_idx, lang, exc,
        )
        raise self.retry(exc=exc, countdown=min(30 * (2 ** self.request.retries), 180))
