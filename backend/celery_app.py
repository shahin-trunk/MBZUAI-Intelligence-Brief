"""Celery application for the MBZUAI Intelligence Brief backend.

Provides async task queues for:
  - llm: Claude/Anthropic script and content generation
  - audio: Argent TTS audio synthesis and upload
  - learning: Language learning content orchestration

Optimized for maximum parallel processing and stability:
  - Connection pooling for Redis broker
  - Task rate limiting to protect external APIs
  - Exponential backoff with jitter for retries
  - Worker monitoring via signals
  - Task time limits to prevent stuck tasks
  - Priority queues for critical tasks
  - Result compression to reduce memory usage
  - Auto-restart workers to prevent memory leaks

Usage:
  celery -A celery_app worker -Q llm -c 8 --loglevel=info --prefetch-multiplier=2 --max-tasks-per-child=500
  celery -A celery_app worker -Q audio -c 20 --loglevel=info --prefetch-multiplier=4 --max-tasks-per-child=1000
  celery -A celery_app worker -Q learning -c 10 --loglevel=info --prefetch-multiplier=2 --max-tasks-per-child=750
"""
from celery import Celery
from celery.signals import worker_ready, task_success, task_failure, worker_shutdown
import logging
import random
import time
import os

logger = logging.getLogger(__name__)

celery_app = Celery(
    "brief",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Dubai",
    enable_utc=True,

    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # overridden per-worker via CLI

    # Queue routing
    task_routes={
        "tasks.llm_tasks.*": {"queue": "llm"},
        "tasks.audio_tasks.*": {"queue": "audio"},
        "tasks.learning_tasks.*": {"queue": "learning"},
    },

    # Retries with exponential backoff (enhanced in task decorators)
    task_max_retries=3,
    task_default_retry_delay=10,
    task_acks_on_failure_or_timeout=False,

    # Result settings
    result_expires=3600,
    result_compression="gzip",  # compress results to reduce Redis memory

    # Task execution time limits
    task_time_limit=600,  # 10 min hard limit
    task_soft_time_limit=540,  # 9 min soft limit (triggers SoftTimeLimitExceeded)

    # Broker connection pooling
    broker_pool_limit=50,
    broker_connection_timeout=30,
    broker_connection_retry=True,
    broker_connection_max_retries=10,

    # Result backend connection
    redis_backend_retry_on_timeout=True,
    redis_max_connections=50,

    # Priority queues
    task_queue_max_priority=10,
    task_default_priority=5,

    # Worker stability - auto-restart to prevent memory leaks
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=2097152,  # 2GB

    # Task rate limits to protect external APIs
    task_annotations={
        "tasks.llm_tasks.generate_brief_script": {"rate_limit": "10/m"},
        "tasks.llm_tasks.generate_learning_phrases": {"rate_limit": "20/m"},
        "tasks.audio_tasks.generate_item_audio": {"rate_limit": "30/m"},
        "tasks.audio_tasks.generate_phrase_audio": {"rate_limit": "60/m"},
    },
)


def exponential_backoff_with_jitter(retry_count: int, base_delay: int = 10, max_delay: int = 300) -> int:
    """Calculate retry delay with exponential backoff and jitter.

    Prevents thundering herd problem when multiple tasks fail simultaneously.
    Jitter adds randomization +/- 25% to spread out retries.

    Args:
        retry_count: Current retry attempt (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds

    Returns:
        Delay in seconds (1 to max_delay)
    """
    exponential_delay = base_delay * (2 ** retry_count)
    jitter = random.uniform(-0.25, 0.25) * exponential_delay
    delay = exponential_delay + jitter
    return int(min(max(delay, 1), max_delay))


# Worker monitoring signals

@worker_ready.connect
def on_worker_ready(sender=None, **kwargs):
    """Log when a worker starts and is ready to accept tasks."""
    logger.info(f"[CELERY_METRICS] Worker ready: {sender}")

@worker_shutdown.connect
def on_worker_shutdown(sender=None, **kwargs):
    """Log when a worker is shutting down."""
    logger.info(f"[CELERY_METRICS] Worker shutting down: {sender}")

@task_success.connect
def on_task_success(sender=None, result=None, runtime=None, **kwargs):
    """Log successful task completion with runtime metrics."""
    task_name = sender.name if sender else "unknown"
    logger.info(
        f"[CELERY_METRICS] Task succeeded: {task_name}, "
        f"runtime={runtime:.2f}s"
    )

@task_failure.connect
def on_task_failure(sender=None, exception=None, traceback=None,
                    einfo=None, args=None, kwargs=None, **kw):
    """Log task failures with error details for debugging."""
    task_name = sender.name if sender else "unknown"
    logger.error(
        f"[CELERY_METRICS] Task failed: {task_name}, "
        f"exception={type(exception).__name__}: {exception}"
    )


# Auto-discover tasks from the tasks package
celery_app.autodiscover_tasks(["tasks"])
