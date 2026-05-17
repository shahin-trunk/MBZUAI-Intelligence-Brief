"""Celery application for the MBZUAI Intelligence Brief backend.

Provides async task queues for:
  - llm: Claude/Anthropic script and content generation
  - audio: Argent TTS audio synthesis and upload
  - learning: Language learning content orchestration

Usage:
  celery -A celery_app worker -Q llm -c 5 --loglevel=info
  celery -A celery_app worker -Q audio -c 10 --loglevel=info
  celery -A celery_app worker -Q learning -c 5 --loglevel=info
"""
from celery import Celery
import os

celery_app = Celery(
    "brief",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Dubai",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Queue routing
    task_routes={
        "tasks.llm_tasks.*": {"queue": "llm"},
        "tasks.audio_tasks.*": {"queue": "audio"},
        "tasks.learning_tasks.*": {"queue": "learning"},
    },
    # Retries
    task_max_retries=3,
    task_default_retry_delay=10,
    task_acks_on_failure_or_timeout=False,
    # Result expiry (1 hour)
    result_expires=3600,
)

# Auto-discover tasks from the tasks package
celery_app.autodiscover_tasks(["tasks"])
