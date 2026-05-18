"""Dead Letter Queue (DLQ) for Celery task failures.

When Celery tasks exhaust their retry budget, failures are captured here
so operators can inspect, diagnose, and retry them later.

Usage:
    # In a failing task's except block (before final retry):
    push_to_dlq(
        task_name="generate_phrase_audio",
        task_id=self.request.id,
        target_date=target_date,
        item_id=item_id,
        lang=lang,
        phrase_idx=phrase_idx,
        script_idx=script_idx,
        error_type=type(exc).__name__,
        error_message=str(exc)[:2000],
        task_args={"target_date": target_date, ...},
    )
"""
import logging
import traceback as _traceback
from datetime import datetime, timezone
from threading import Lock

log = logging.getLogger("celery.dlq")

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
            import os
            from supabase import create_client
            _supabase_client = create_client(
                os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
                os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            )
            log.info("Supabase client initialized for DLQ")
    return _supabase_client


def push_to_dlq(
    task_name: str,
    task_id: str | None,
    error_type: str,
    error_message: str,
    target_date: str | None = None,
    item_id: str | None = None,
    lang: str | None = None,
    phrase_idx: int | None = None,
    script_idx: int | None = None,
    traceback: str | None = None,
    task_args: dict | None = None,
) -> str | None:
    """Push a task failure to the DLQ.

    This function must never raise — it catches all Supabase errors
    and logs them. The DLQ is auxiliary infrastructure; failure to
    write to it must not crash the primary task.

    Returns the new entry ID on success, None on failure.
    """
    try:
        sb = _get_supabase_client()
        result = sb.table("dlq_entries").insert({
            "task_name": task_name,
            "task_id": task_id,
            "target_date": target_date,
            "item_id": item_id,
            "lang": lang,
            "phrase_idx": phrase_idx,
            "script_idx": script_idx,
            "error_type": error_type,
            "error_message": error_message[:2000],
            "traceback": traceback[:5000] if traceback else None,
            "task_args": task_args,
        }).execute()

        entry_id = result.data[0].get("id") if result.data else None
        log.info(
            "[DLQ] Pushed entry %s: %s for item %s (error: %s)",
            entry_id, task_name, item_id, error_type,
        )
        return entry_id

    except Exception as exc:
        log.warning(
            "[DLQ] Failed to push entry for %s/%s: %s",
            task_name, item_id, exc,
        )
        return None


def get_dlq_entries(resolved: bool = False, limit: int = 50, offset: int = 0) -> list[dict]:
    """Query DLQ entries filtered by resolved status.

    Returns list of dicts ordered by created_at DESC.
    """
    try:
        sb = _get_supabase_client()
        result = (
            sb.table("dlq_entries")
            .select("*")
            .eq("resolved", resolved)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        log.warning("[DLQ] Failed to query entries: %s", exc)
        return []


def get_dlq_entry(entry_id: str) -> dict | None:
    """Fetch a single DLQ entry by ID."""
    try:
        sb = _get_supabase_client()
        result = (
            sb.table("dlq_entries")
            .select("*")
            .eq("id", entry_id)
            .single()
            .execute()
        )
        return result.data if result.data else None
    except Exception as exc:
        log.warning("[DLQ] Failed to fetch entry %s: %s", entry_id, exc)
        return None


def retry_dlq_entry(entry_id: str) -> str | None:
    """Retry a DLQ entry by re-submitting the original Celery task.

    Returns the new Celery task ID on success, None on failure.
    """
    entry = get_dlq_entry(entry_id)
    if not entry:
        log.warning("[DLQ] Entry %s not found", entry_id)
        return None

    task_args = entry.get("task_args")
    if not task_args:
        log.warning("[DLQ] Entry %s has no task_args", entry_id)
        return None

    try:
        # Lazy import to avoid circular imports
        task_name = entry["task_name"]
        if task_name == "generate_phrase_audio":
            from tasks.audio_tasks import generate_phrase_audio
            task = generate_phrase_audio.apply_async(args=[
                task_args["target_date"],
                task_args["item_id"],
                task_args["lang"],
                task_args["phrase_idx"],
                task_args["script_idx"],
                task_args["script_text"],
                task_args["voice_id"],
            ])
        elif task_name == "generate_item_audio":
            from tasks.audio_tasks import generate_item_audio
            task = generate_item_audio.apply_async(args=[
                task_args["target_date"],
                task_args["item_id"],
                task_args["script"],
                task_args["voice_id"],
                task_args.get("lang", "en"),
            ])
        else:
            log.warning("[DLQ] Unknown task name: %s", task_name)
            return None

        # Mark as retried
        sb = _get_supabase_client()
        sb.table("dlq_entries").update({
            "retried_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": entry.get("retry_count", 0) + 1,
            "resolved": True,
        }).eq("id", entry_id).execute()

        log.info("[DLQ] Retried entry %s -> task %s", entry_id, task.id)
        return task.id

    except Exception as exc:
        log.warning("[DLQ] Failed to retry entry %s: %s", entry_id, exc)
        return None


def resolve_dlq_entry(entry_id: str) -> bool:
    """Dismiss a DLQ entry without retrying."""
    try:
        sb = _get_supabase_client()
        sb.table("dlq_entries").update({
            "resolved": True,
        }).eq("id", entry_id).execute()

        log.info("[DLQ] Resolved entry %s", entry_id)
        return True
    except Exception as exc:
        log.warning("[DLQ] Failed to resolve entry %s: %s", entry_id, exc)
        return False


def get_dlq_stats() -> dict:
    """Return aggregate DLQ counts."""
    try:
        sb = _get_supabase_client()

        total = sb.table("dlq_entries").select("id", count="exact").execute()
        unresolved = sb.table("dlq_entries").select("id", count="exact").eq("resolved", False).execute()
        resolved = sb.table("dlq_entries").select("id", count="exact").eq("resolved", True).execute()

        return {
            "total": total.count if total.count is not None else 0,
            "unresolved": unresolved.count if unresolved.count is not None else 0,
            "resolved": resolved.count if resolved.count is not None else 0,
        }
    except Exception as exc:
        log.warning("[DLQ] Failed to get stats: %s", exc)
        return {"total": 0, "unresolved": 0, "resolved": 0}
