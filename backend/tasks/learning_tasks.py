"""Celery tasks for language learning content orchestration.

Queue: learning

These tasks orchestrate the V3 phrase-based learning pipeline using
non-blocking Celery chain/chord patterns:
  1. Generate phrases via Claude (llm queue)
  2. Generate TTS audio for all 4 scripts per phrase (audio queue, fan-out via chord)
  3. Merge results and write back to Supabase (learning queue callback)

Optimized: Uses chord() for non-blocking fan-out/fan-in instead of
synchronous .get() calls that block the learning worker.
"""
import logging
import os
import sys
from pathlib import Path
from threading import Lock

from celery_app import celery_app, exponential_backoff_with_jitter
from celery import chain, chord, group

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

# Thread-safe Supabase client singleton per worker process
_supabase_client = None
_supabase_lock = Lock()


def _get_supabase_client():
    """Get or create a singleton Supabase client for this worker process."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    with _supabase_lock:
        if _supabase_client is None:
            from supabase import create_client
            _supabase_client = create_client(
                os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
                os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            )
            log.info("Supabase client initialized (pooled)")
    return _supabase_client


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
    """Orchestrate learning content generation using non-blocking chord pattern.

    Instead of blocking with .get() on phrase generation and audio tasks,
    this submits a Celery chord that:
    1. Fans out phrase generation to LLM queue
    2. On phrase completion, fans out audio generation to Audio queue
    3. On all audio complete, calls merge_learning_results callback

    This allows the learning worker to process other tasks while waiting.

    Returns:
        {"target_date": str, "item_id": str, "status": "chord_submitted"}
    """
    from tasks.llm_tasks import generate_learning_phrases

    log.info(
        "Starting learning content generation (chord pattern) for %s item %s lang %s",
        target_date, item_id, lang,
    )

    try:
        # Submit phrase generation as first step
        phrase_task = generate_learning_phrases.s(
            target_date, item_id, lang, phrase_count
        ).set(queue="llm")

        # Chain: phrases -> prepare_audio_tasks -> chord(audio) -> merge
        # We need an intermediate task to convert phrase results to audio tasks
        workflow = chain(
            phrase_task,
            prepare_audio_tasks.s(target_date, item_id, lang),
        )
        workflow.apply_async()

        return {
            "target_date": target_date,
            "item_id": item_id,
            "lang": lang,
            "status": "chord_submitted",
        }

    except Exception as exc:
        log.warning(
            "Learning content submission failed for %s item %s lang %s: %s",
            target_date, item_id, lang, exc,
        )
        raise self.retry(exc=exc, countdown=exponential_backoff_with_jitter(self.request.retries, base_delay=60))


@celery_app.task(
    queue="learning",
    max_retries=2,
    default_retry_delay=15,
    name="tasks.learning_tasks.prepare_audio_tasks",
)
def prepare_audio_tasks(
    phrases_result: dict,
    target_date: str,
    item_id: str,
    lang: str,
) -> dict:
    """Convert phrase generation results into audio task chord.

    This intermediate task takes phrase results and creates a Celery chord
    that fans out audio generation to the audio queue, then merges results.

    Returns:
        {"status": "audio_chord_submitted"}
    """
    from tasks.audio_tasks import generate_phrase_audio

    if phrases_result.get("error"):
        log.error("Phrase generation failed: %s", phrases_result["error"])
        return {"status": "error", "reason": phrases_result["error"]}

    phrases = phrases_result["phrases"]
    difficulty = phrases_result.get("difficulty", "intermediate")
    lesson_summary = phrases_result.get("lesson_summary", "")

    log.info("Preparing audio chord for %d phrases, item %s", len(phrases), item_id)

    # Build audio tasks for all phrase scripts
    audio_tasks_list = []
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

            audio_tasks_list.append(
                generate_phrase_audio.s(
                    target_date, item_id, lang, p_idx, s_idx, script_text, voice_id,
                )
            )

    if not audio_tasks_list:
        log.warning("No audio tasks to submit for item %s", item_id)
        return {"status": "no_audio_tasks", "item_id": item_id}

    # Submit chord: when all audio tasks complete, call merge callback
    audio_chord = chord(audio_tasks_list)(
        merge_learning_results.s(
            target_date=target_date,
            item_id=item_id,
            lang=lang,
            phrases=phrases,
            difficulty=difficulty,
            lesson_summary=lesson_summary,
        )
    )

    log.info("Audio chord submitted with %d tasks, item %s", len(audio_tasks_list), item_id)
    return {
        "status": "audio_chord_submitted",
        "task_count": len(audio_tasks_list),
        "chord_id": audio_chord.id,
    }


@celery_app.task(
    queue="learning",
    max_retries=2,
    default_retry_delay=15,
    name="tasks.learning_tasks.merge_learning_results",
)
def merge_learning_results(
    audio_results: list,
    target_date: str,
    item_id: str,
    lang: str,
    phrases: list,
    difficulty: str,
    lesson_summary: str = "",
) -> dict:
    """Chord callback: merge audio results and write to Supabase.

    Called automatically by Celery when all audio tasks in the chord complete.

    Args:
        audio_results: List of audio task results from chord
        target_date: Brief date
        item_id: Item identifier
        lang: Target language
        phrases: Original phrase data (updated with audio URLs)
        difficulty: Phrase difficulty level

    Returns:
        {"status": "completed", "phrase_count": int}
    """
    log.info(
        "Merging %d audio results for %s item %s lang %s",
        len(audio_results), target_date, item_id, lang,
    )

    try:
        # Collect audio URLs back into phrases and detect failures
        failed_results = []
        for i, audio_info in enumerate(audio_results):
            if isinstance(audio_info, dict) and "phrase_idx" in audio_info:
                p_idx = audio_info["phrase_idx"]
                s_idx = audio_info["script_idx"]
                if 0 <= p_idx < len(phrases):
                    phrases[p_idx][f"audio_url_{s_idx}"] = audio_info["audio_url"]
            else:
                # This audio task failed (result is not the expected dict)
                failed_results.append(i)

        if failed_results:
            log.warning(
                "Partial audio failure for %s item %s lang %s: %d/%d tasks failed (indices: %s)",
                target_date, item_id, lang, len(failed_results), len(audio_results), failed_results,
            )

        # Calculate durations
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
            "lesson_summary": lesson_summary,
        }

        # Write to Supabase using pooled client
        sb = _get_supabase_client()

        # Read current raw_json
        result = sb.table("briefs").select("raw_json, generation_status").eq("brief_date", target_date).single().execute()
        if not result.data:
            log.error("No brief found for learning update: %s", target_date)
            return {"status": "error", "reason": "brief_not_found"}

        brief_json = result.data.get("raw_json", {})
        gen_status = result.data.get("generation_status", {})

        # Update the item's learning content via O(1) lookup
        items = brief_json.get("items", [])
        item = next((i for i in items if i.get("id") == item_id), None)
        if item:
            item[f"learning_{lang}"] = learning_data

        # Update generation status (partial vs completed)
        lang_key = f"learning_{lang}"
        from datetime import datetime, timezone
        has_failures = len(failed_results) > 0
        gen_status[lang_key] = {
            "status": "partial" if has_failures else "completed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_tasks": len(audio_results),
            "failed_tasks": len(failed_results),
        }

        # Write back
        sb.table("briefs").update({
            "raw_json": brief_json,
            "generation_status": gen_status,
        }).eq("brief_date", target_date).execute()

        log.info(
            "Learning content %s for %s item %s lang %s (%d phrases, %.1fs total, %d failed)",
            "completed (partial)" if has_failures else "completed",
            target_date, item_id, lang, len(phrases), total_duration, len(failed_results),
        )

        return {
            "status": "partial" if has_failures else "completed",
            "target_date": target_date,
            "item_id": item_id,
            "lang": lang,
            "phrase_count": len(phrases),
            "total_duration_seconds": round(total_duration, 1),
            "failed_tasks": len(failed_results),
            "total_tasks": len(audio_results),
        }

    except Exception as exc:
        log.warning(
            "Learning merge failed for %s item %s lang %s: %s",
            target_date, item_id, lang, exc,
        )
        raise merge_learning_results.retry(exc=exc, countdown=exponential_backoff_with_jitter(
            merge_learning_results.request.retries, base_delay=30
        ))


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

    Legacy task kept for backward compatibility. New workflow uses
    merge_learning_results chord callback instead.

    Returns:
        {"status": "updated"}
    """
    log.info("Updating learning content (legacy) for %s item %s lang %s", target_date, item_id, lang)

    try:
        sb = _get_supabase_client()

        # Read current raw_json
        result = sb.table("briefs").select("raw_json, generation_status").eq("brief_date", target_date).single().execute()
        if not result.data:
            log.error("No brief found for learning update: %s", target_date)
            return {"status": "error", "reason": "brief_not_found"}

        brief_json = result.data.get("raw_json", {})
        gen_status = result.data.get("generation_status", {})

        # Update the item's learning content via O(1) lookup
        items = brief_json.get("items", [])
        item = next((i for i in items if i.get("id") == item_id), None)
        if item:
            item[f"learning_{lang}"] = learning_data

        # Update generation status
        lang_key = f"learning_{lang}"
        from datetime import datetime, timezone
        gen_status[lang_key] = {
            "status": "completed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Write back
        sb.table("briefs").update({
            "raw_json": brief_json,
            "generation_status": gen_status,
        }).eq("brief_date", target_date).execute()

        log.info("Learning content updated (legacy) for %s item %s lang %s", target_date, item_id, lang)
        return {"status": "updated", "item_id": item_id, "lang": lang}

    except Exception as exc:
        log.warning("Learning update failed for %s item %s lang %s: %s", target_date, item_id, lang, exc)
        raise self.retry(exc=exc, countdown=exponential_backoff_with_jitter(self.request.retries, base_delay=30))
