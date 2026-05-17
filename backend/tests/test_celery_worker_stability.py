"""E2E tests for Celery worker stability and quality.

Validates:
  - Worker configuration correctness (concurrency, prefetch, time limits)
  - Exponential backoff with jitter behavior
  - Task rate limiting annotations
  - Redis broker configuration
  - Task routing and queue assignment
  - Memory and resource limit settings

Run with:
    cd backend && python -m pytest tests/test_celery_worker_stability.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestCeleryConfiguration(unittest.TestCase):
    """Validate Celery app configuration for optimal performance."""

    @classmethod
    def setUpClass(cls):
        from celery_app import celery_app
        cls.app = celery_app
        cls.conf = celery_app.conf

    def test_broker_connection_pooling(self):
        """Broker should have connection pool for high throughput."""
        self.assertGreaterEqual(self.conf.broker_pool_limit, 40)

    def test_result_compression(self):
        """Results should be compressed to reduce Redis memory usage."""
        self.assertEqual(self.conf.result_compression, "gzip")

    def test_task_acks_late(self):
        """Tasks should be acknowledged late for reliability."""
        self.assertTrue(self.conf.task_acks_late)

    def test_task_reject_on_worker_lost(self):
        """Tasks should be requeued on worker loss."""
        self.assertTrue(self.conf.task_reject_on_worker_lost)

    def test_task_time_limits(self):
        """Tasks should have hard and soft time limits."""
        self.assertEqual(self.conf.task_time_limit, 600)
        self.assertEqual(self.conf.task_soft_time_limit, 540)

    def test_task_routes(self):
        """All task types should have explicit queue routing."""
        routes = self.conf.task_routes
        self.assertIn("tasks.llm_tasks.*", routes)
        self.assertIn("tasks.audio_tasks.*", routes)
        self.assertIn("tasks.learning_tasks.*", routes)
        self.assertEqual(routes["tasks.llm_tasks.*"]["queue"], "llm")
        self.assertEqual(routes["tasks.audio_tasks.*"]["queue"], "audio")
        self.assertEqual(routes["tasks.learning_tasks.*"]["queue"], "learning")

    def test_priority_queues(self):
        """Priority queues should be enabled."""
        self.assertEqual(self.conf.task_queue_max_priority, 10)
        self.assertEqual(self.conf.task_default_priority, 5)

    def test_result_expires(self):
        """Results should expire after 1 hour."""
        self.assertEqual(self.conf.result_expires, 3600)

    def test_max_retries(self):
        """Tasks should have retry limits."""
        self.assertEqual(self.conf.task_max_retries, 3)


class TestRateLimiting(unittest.TestCase):
    """Validate task rate limiting to protect external APIs."""

    @classmethod
    def setUpClass(cls):
        from celery_app import celery_app
        cls.annotations = celery_app.conf.task_annotations

    def test_llm_task_rate_limits(self):
        """LLM tasks should have conservative rate limits."""
        self.assertIn("tasks.llm_tasks.generate_brief_script", self.annotations)
        self.assertEqual(
            self.annotations["tasks.llm_tasks.generate_brief_script"]["rate_limit"],
            "10/m"
        )

    def test_learning_task_rate_limits(self):
        """Learning tasks should have moderate rate limits."""
        self.assertIn("tasks.llm_tasks.generate_learning_phrases", self.annotations)
        self.assertEqual(
            self.annotations["tasks.llm_tasks.generate_learning_phrases"]["rate_limit"],
            "20/m"
        )

    def test_audio_task_rate_limits(self):
        """Audio tasks should have higher rate limits for I/O throughput."""
        self.assertIn("tasks.audio_tasks.generate_item_audio", self.annotations)
        self.assertIn("tasks.audio_tasks.generate_phrase_audio", self.annotations)


class TestExponentialBackoff(unittest.TestCase):
    """Validate exponential backoff with jitter function."""

    def setUp(self):
        from celery_app import exponential_backoff_with_jitter
        self.backoff = exponential_backoff_with_jitter

    def test_base_delay_retry_0(self):
        """First retry should be close to base delay."""
        delay = self.backoff(0, base_delay=10)
        # With +/- 25% jitter on 10s: range [7.5, 12.5]
        self.assertGreaterEqual(delay, 7)
        self.assertLessEqual(delay, 13)

    def test_exponential_growth(self):
        """Delay should grow exponentially with retry count."""
        delay_0 = self.backoff(0, base_delay=10)
        delay_1 = self.backoff(1, base_delay=10)
        delay_2 = self.backoff(2, base_delay=10)
        delay_3 = self.backoff(3, base_delay=10)

        # Each retry should roughly double (allowing for jitter)
        self.assertGreater(delay_1, delay_0 * 1.3)
        self.assertGreater(delay_2, delay_1 * 1.3)
        self.assertGreater(delay_3, delay_2 * 1.3)

    def test_max_delay_cap(self):
        """Delay should never exceed max_delay."""
        for retry_count in range(10):
            delay = self.backoff(retry_count, base_delay=10, max_delay=300)
            self.assertLessEqual(delay, 300)

    def test_minimum_delay(self):
        """Delay should never be less than 1 second."""
        for retry_count in range(5):
            delay = self.backoff(retry_count, base_delay=1)
            self.assertGreaterEqual(delay, 1)

    def test_jitter_variability(self):
        """Multiple calls should produce different delays due to jitter."""
        delays = set()
        for _ in range(20):
            delays.add(self.backoff(2, base_delay=30))
        # Should see at least 2 different values
        self.assertGreater(len(delays), 1)


class TestTaskImports(unittest.TestCase):
    """Validate that task modules import correctly and use shared backoff."""

    def test_llm_tasks_import(self):
        """LLM tasks module should import without errors."""
        from tasks import llm_tasks
        self.assertTrue(hasattr(llm_tasks, "generate_brief_script"))
        self.assertTrue(hasattr(llm_tasks, "generate_learning_phrases"))

    def test_audio_tasks_import(self):
        """Audio tasks module should import without errors."""
        from tasks import audio_tasks
        self.assertTrue(hasattr(audio_tasks, "generate_item_audio"))
        self.assertTrue(hasattr(audio_tasks, "generate_phrase_audio"))

    def test_learning_tasks_import(self):
        """Learning tasks module should import without errors."""
        from tasks import learning_tasks
        self.assertTrue(hasattr(learning_tasks, "generate_learning_content"))
        self.assertTrue(hasattr(learning_tasks, "update_item_learning"))

    def test_tasks_use_shared_backoff(self):
        """Task modules should import the shared backoff function."""
        from tasks import llm_tasks
        from tasks import audio_tasks
        from tasks import learning_tasks
        from celery_app import exponential_backoff_with_jitter

        # Verify the import exists in each module's namespace
        self.assertIs(llm_tasks.exponential_backoff_with_jitter, exponential_backoff_with_jitter)
        self.assertIs(audio_tasks.exponential_backoff_with_jitter, exponential_backoff_with_jitter)
        self.assertIs(learning_tasks.exponential_backoff_with_jitter, exponential_backoff_with_jitter)


class TestWorkerConfiguration(unittest.TestCase):
    """Validate docker-compose worker configurations."""

    def setUp(self):
        import yaml
        compose_path = BACKEND_DIR.parent / "docker-compose.yml"
        with open(compose_path) as f:
            self.compose = yaml.safe_load(f)

    def test_llm_worker_concurrency(self):
        """LLM worker should have sufficient concurrency for CPU-bound tasks."""
        command = self.compose["services"]["celery-worker-llm"]["command"]
        self.assertIn("-c 8", command)
        self.assertIn("--prefetch-multiplier=2", command)
        self.assertIn("--max-tasks-per-child=500", command)

    def test_audio_worker_concurrency(self):
        """Audio worker should have high concurrency for I/O-bound tasks."""
        command = self.compose["services"]["celery-worker-audio"]["command"]
        self.assertIn("-c 20", command)
        self.assertIn("--prefetch-multiplier=4", command)
        self.assertIn("--max-tasks-per-child=1000", command)

    def test_learning_worker_concurrency(self):
        """Learning worker should have balanced concurrency."""
        command = self.compose["services"]["celery-worker-learning"]["command"]
        self.assertIn("-c 10", command)
        self.assertIn("--prefetch-multiplier=2", command)
        self.assertIn("--max-tasks-per-child=750", command)

    def test_llm_worker_resources(self):
        """LLM worker should have adequate CPU and memory."""
        resources = self.compose["services"]["celery-worker-llm"]["deploy"]["resources"]
        self.assertEqual(resources["limits"]["memory"], "4G")
        self.assertEqual(resources["limits"]["cpus"], "4.0")

    def test_audio_worker_resources(self):
        """Audio worker should have high memory for I/O buffering."""
        resources = self.compose["services"]["celery-worker-audio"]["deploy"]["resources"]
        self.assertEqual(resources["limits"]["memory"], "8G")
        self.assertEqual(resources["limits"]["cpus"], "8.0")

    def test_redis_maxmemory(self):
        """Redis should have sufficient memory for high throughput."""
        command = self.compose["services"]["redis"]["command"]
        self.assertIn("--maxmemory 512mb", command)


class TestMonitoringSignals(unittest.TestCase):
    """Validate that monitoring signals are defined and functional."""

    def test_worker_ready_signal_defined(self):
        """Worker ready signal handler should be defined."""
        from celery_app import on_worker_ready
        self.assertTrue(callable(on_worker_ready))

    def test_task_success_signal_defined(self):
        """Task success signal handler should be defined."""
        from celery_app import on_task_success
        self.assertTrue(callable(on_task_success))

    def test_task_failure_signal_defined(self):
        """Task failure signal handler should be defined."""
        from celery_app import on_task_failure
        self.assertTrue(callable(on_task_failure))

    def test_signal_handlers_logged(self):
        """Signal handlers should log appropriately."""
        import logging
        from unittest.mock import patch, MagicMock
        from celery_app import on_worker_ready, on_task_success, on_task_failure

        # Test on_worker_ready logs
        with patch.object(logging.Logger, 'info') as mock_info:
            on_worker_ready(sender="test_worker")
            mock_info.assert_called_once()

        # Test on_task_success logs
        with patch.object(logging.Logger, 'info') as mock_info:
            sender = MagicMock(name="tasks.llm_tasks.generate_brief_script")
            on_task_success(sender=sender, runtime=5.2)
            mock_info.assert_called_once()

        # Test on_task_failure logs
        with patch.object(logging.Logger, 'error') as mock_error:
            sender = MagicMock(name="tasks.audio_tasks.generate_phrase_audio")
            on_task_failure(sender=sender, exception=ValueError("test"))
            mock_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
