"""Celery tasks for language learning content orchestration.

Queue: learning

These tasks orchestrate the V3 phrase-based learning pipeline:
  1. Generate phrases via Claude (llm queue, called from llm_tasks)
  2. Generate TTS audio for all 4 scripts per phrase (audio queue, fan-out)
  3. Collect URLs and write back to Supabase
"""
import logging
import os
import sys
from pathlib import Path

from celery_app import celery_app
from celery import group

# Ensure backend directory is on the Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from generate_audio import (
    _estimate_duration_seconds,
    _get_voice_config,
    _is_bilingual_script,
)

log = logging.getLogger("celery.learning")


def _get_voice_for_script(lang: str, script_idx: int) -> tuple[str, str]:
    """Get the correct voice ID and speed lang for a given script index.

    Scripts 1, 2, 4 -> English voice
    Script 3 -> Target language voice
    """
    voice_config = _get_voice_config()
    if script_idx == 3:
        # Target language voice for the phrase itself
        return voice_config.get(lang, {}).get("voice_id", ""), lang
    # English voice for explanation and transition scripts
    return voice_config.get("en", {}).get("voice_id", ""), "en"


@celery_app.task(
    bind=True,
    queue="learning",
    max_retries=2,
    default_retry_delay=30,
    name="tasks.learning_tasks.generate_learning_content",
)
def generate_learning_content(
    self,
    target_date: str,
    item_id: str,
    lang: str,
    phrase_count: int = 3,
) -> dict:
    """Orchestrate learning content generation for a single item.

    This task calls generate_learning_phrases, then fans out to parallel
    audio generation tasks for all 4 scripts per phrase.

    Returns:
        {"phrases": [...], "task_ids": [...]}
    """
    from tasks.llm_tasks import generate_learning_phrases

    log.info(
        "Starting learning content generation for %s item %s lang %s",
        target_date, item_id, lang,
    )

    try:
        # Step 1: Generate phrases (this is a synchronous call in the same task
        # to keep the chain simple, or we could chain it separately)
        result = generate_learning_phrases.apply_async(
            args=[target_date, item_id, lang, phrase_count],
            queue="llm",
        )
        phrases_result = result.get(timeout=120)

        if phrases_result.get("error"):
            log.error("Phrase generation failed: %s", phrases_result["error"])
            raise RuntimeError(f"Phrase generation failed: {phrases_result['error']}")

        phrases = phrases_result["phrases"]
        difficulty = phrases_result.get("difficulty", "intermediate")

        # Step 2: Fan out audio generation for all phrases
        audio_tasks = []
        for p_idx, phrase in enumerate(phrases):
            for s_idx in range(1, 5):  # scripts 1-4
                script_text = phrase.get(f"script{s_idx}", "")
                if not script_text or len(script_text) < 10:
                    log.warning("Skipping empty script p%s_s%s for item %s", p_idx, s_idx, item_id)
                    continue

                voice_id, script_lang = _get_voice_for_script(lang, s_idx)
                if not voice_id:
                    log.warning("No voice configured for script p%s_s%s lang %s", p_idx, s_idx, script_lang)
                    continue

                audio_tasks.append(
                    generate_phrase_audio.s(
                        target_date, item_id, lang, p_idx, s_idx, script_text, voice_id,
                    )
                )

        if audio_tasks:
            audio_group = group(audio_tasks)
            audio_result = audio_group.apply_async(queue="audio")
            audio_results = audio_result.get(timeout=300)

            # Step 3: Collect audio URLs back into phrases
            for audio_info in audio_results:
                p_idx = audio_info["phrase_idx"]
                s_idx = audio_info["script_idx"]
                phrases[p_idx][f"audio_url_{s_idx}"] = audio_info["audio_url"]

        # Step 4: Calculate durations
        for phrase in phrases:
            dur = sum(
                _estimate_duration_seconds(phrase.get(f"script{s}", ""), lang)
                for s in range(1, 4)  # scripts 1-3 only (script4 is on-demand)
            )
            phrase["estimated_duration_seconds"] = round(dur, 1)

        total_duration = sum(p.get("estimated_duration_seconds", 0) for p in phrases)

        learning_data = {
            "version": 3,
            "phrases": phrases,
            "difficulty": difficulty,
            "total_duration_seconds": round(total_duration, 1),
        }

        # Step 5: Write back to Supabase
        update_item_learning.apply_async(
            args=[target_date, item_id, lang, learning_data],
            queue="learning",
        )

        return {
            "target_date": target_date,
            "item_id": item_id,
            "lang": lang,
            "status": "submitted",
            "phrase_count": len(phrases),
        }

    except Exception as exc:
        log.warning(
            "Learning content orchestration failed for %s item %s lang %s: %s",
            target_date, item_id, lang, exc,
        )
        raise self.retry(exc=exc, countdown=min(60 * (2 ** self.request.retries), 300))


@celery_app.task(
    queue="learning",
    max_retries=2,
    default_retry_delay=15,
    name="tasks.learning_tasks.update_item_learning",
)
def update_item_learning(
    target_date: str,
    item_id: str,
    lang: str,
    learning_data: dict,
) -> dict:
    """Write completed learning content back to Supabase raw_json.

    Updates the generation_status column to track completion.

    Returns:
        {"status": "updated"}
    """
    from supabase import create_client

    log.info("Updating learning content for %s item %s lang %s", target_date, item_id, lang)

    try:
        sb = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        )

        # Read current raw_json
        result = sb.table("briefs").select("raw_json, generation_status").eq("brief_date", target_date).single().execute()
        if not result.data:
            log.error("No brief found for learning update: %s", target_date)
            return {"status": "error", "reason": "brief_not_found"}

        brief_json = result.data.get("raw_json", {})
        gen_status = result.data.get("generation_status", {})

        # Update the item's learning content
        items = brief_json.get("items", [])
        for item in items:
            if item.get("id") == item_id:
                item[f"learning_{lang}"] = learning_data
                break

        # Update generation status
        lang_key = f"learning_{lang}"
        gen_status[lang_key] = {
            "status": "completed",
            "updated_at": _now_iso(),
        }

        # Write back
        sb.table("briefs").update({
            "raw_json": brief_json,
            "generation_status": gen_status,
        }).eq("brief_date", target_date).execute()

        log.info("Learning content updated for %s item %s lang %s", target_date, item_id, lang)
        return {"status": "updated", "item_id": item_id, "lang": lang}

    except Exception as exc:
        log.warning("Learning update failed for %s item %s lang %s: %s", target_date, item_id, lang, exc)
        raise self.retry(exc=exc, countdown=min(30 * (2 ** self.request.retries), 180))


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
