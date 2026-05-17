"""Celery tasks for LLM/Claude script generation.

Queue: llm
"""
import logging
import os
import sys
from pathlib import Path
from threading import Lock

from celery_app import celery_app, exponential_backoff_with_jitter

# Ensure backend directory is on the Python path so generate_audio imports work
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from generate_audio import (
    _generate_and_prepare_script,
    _build_shared_outline,
    ANTHROPIC_MODEL,
)

log = logging.getLogger("celery.llm")

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


@celery_app.task(
    bind=True,
    queue="llm",
    max_retries=3,
    default_retry_delay=30,
    name="tasks.llm_tasks.generate_brief_script",
)
def generate_brief_script(self, target_date: str) -> dict:
    """Generate the English narrative script for a brief.

    Returns:
        {"target_date": str, "script_en": str, "outline": list}
    """
    log.info("Generating brief script for %s (attempt %s)", target_date, self.request.retries + 1)

    try:
        sb = _get_supabase_client()

        result = sb.table("briefs").select("raw_json").eq("brief_date", target_date).single().execute()
        brief_json = result.data.get("raw_json") if result.data else None
        if not brief_json:
            log.error("No brief found in DB for %s", target_date)
            return {"target_date": target_date, "error": "brief_not_found"}

        shared_outline, outline_items = _build_shared_outline(brief_json)

        script_en = _generate_and_prepare_script(
            brief_json,
            shared_outline=shared_outline,
            outline_items=outline_items,
            lang="en",
        )

        return {
            "target_date": target_date,
            "script_en": script_en,
            "outline_items": outline_items,
        }

    except Exception as exc:
        log.warning("Brief script generation failed for %s: %s", target_date, exc)
        raise self.retry(exc=exc, countdown=exponential_backoff_with_jitter(self.request.retries))


@celery_app.task(
    bind=True,
    queue="llm",
    max_retries=3,
    default_retry_delay=30,
    name="tasks.llm_tasks.generate_learning_phrases",
)
def generate_learning_phrases(self, target_date: str, item_id: str, lang: str, phrase_count: int = 3) -> dict:
    """Generate learning phrases with 4 scripts per phrase for a single item.

    Returns:
        {"target_date": str, "item_id": str, "lang": str, "phrases": list, "difficulty": str}
    """
    from generate_audio import (
        _generate_learning_phrases,
        _build_rich_item_summary,
    )

    log.info(
        "Generating learning phrases for %s item %s lang %s (attempt %s)",
        target_date, item_id, lang, self.request.retries + 1,
    )

    try:
        sb = _get_supabase_client()

        result = sb.table("briefs").select("raw_json").eq("brief_date", target_date).single().execute()
        brief_json = result.data.get("raw_json") if result.data else None
        if not brief_json:
            return {"target_date": target_date, "item_id": item_id, "lang": lang, "error": "brief_not_found"}

        # Find the item via O(1) dictionary lookup
        items = brief_json.get("items", [])
        item = next((i for i in items if i.get("id") == item_id), None)

        if not item:
            return {"target_date": target_date, "item_id": item_id, "lang": lang, "error": "item_not_found"}

        phrases_data = _generate_learning_phrases(item, lang, phrase_count)
        if not phrases_data:
            return {"target_date": target_date, "item_id": item_id, "lang": lang, "error": "phrase_generation_failed"}

        return {
            "target_date": target_date,
            "item_id": item_id,
            "lang": lang,
            "phrases": phrases_data.get("phrases", []),
            "difficulty": phrases_data.get("difficulty", "intermediate"),
        }

    except Exception as exc:
        log.warning(
            "Learning phrase generation failed for %s item %s lang %s: %s",
            target_date, item_id, lang, exc,
        )
        raise self.retry(exc=exc, countdown=exponential_backoff_with_jitter(self.request.retries, base_delay=60))
