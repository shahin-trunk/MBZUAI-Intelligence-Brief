"""E2E tests for ITER 11 Celery performance optimizations.

Validates:
  - Supabase connection pooling (singleton per worker)
  - httpx connection pooling in TTS
  - Concurrent chunk processing for ElevenLabs TTS
  - Reduced TTS timeout configuration
  - Task module singleton patterns
  - Audio quality and stability metrics

Run with:
    cd backend && python -m pytest tests/test_celery_iter11.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestSupabaseConnectionPooling(unittest.TestCase):
    """Validate Supabase connection pooling in task modules."""

    def test_llm_tasks_has_singleton(self):
        """LLM tasks should use singleton Supabase client."""
        from tasks import llm_tasks
        self.assertTrue(hasattr(llm_tasks, '_get_supabase_client'))
        self.assertTrue(hasattr(llm_tasks, '_supabase_client'))
        self.assertTrue(hasattr(llm_tasks, '_supabase_lock'))

    def test_audio_tasks_has_singleton(self):
        """Audio tasks should use singleton Supabase client."""
        from tasks import audio_tasks
        self.assertTrue(hasattr(audio_tasks, '_get_supabase_client'))
        self.assertTrue(hasattr(audio_tasks, '_supabase_client'))
        self.assertTrue(hasattr(audio_tasks, '_supabase_lock'))

    def test_learning_tasks_has_singleton(self):
        """Learning tasks should use singleton Supabase client."""
        from tasks import learning_tasks
        self.assertTrue(hasattr(learning_tasks, '_get_supabase_client'))
        self.assertTrue(hasattr(learning_tasks, '_supabase_client'))
        self.assertTrue(hasattr(learning_tasks, '_supabase_lock'))

    def test_singleton_returns_same_instance(self):
        """Singleton should return the same client instance."""
        from tasks import llm_tasks

        # Reset singleton for test
        llm_tasks._supabase_client = None

        with patch('supabase.create_client') as mock_create:
            mock_client = MagicMock()
            mock_create.return_value = mock_client

            # First call should create client
            client1 = llm_tasks._get_supabase_client()
            # Second call should return same instance
            client2 = llm_tasks._get_supabase_client()

            self.assertIs(client1, client2)
            mock_create.assert_called_once()

    def test_singleton_thread_safe(self):
        """Singleton should be thread-safe with lock."""
        from tasks import audio_tasks
        import threading

        audio_tasks._supabase_client = None
        created_count = 0

        def mock_create_client(*args, **kwargs):
            nonlocal created_count
            created_count += 1
            return MagicMock()

        with patch('supabase.create_client', side_effect=mock_create_client):
            # Simulate concurrent access
            threads = []
            results = []
            for _ in range(10):
                t = threading.Thread(target=lambda: results.append(audio_tasks._get_supabase_client()))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

            # All threads should get the same instance
            self.assertEqual(len(set(id(r) for r in results)), 1)
            # Client should be created only once
            self.assertEqual(created_count, 1)


class TestTTSConnectionPooling(unittest.TestCase):
    """Validate httpx connection pooling in TTS generation."""

    def test_generate_audio_uses_httpx_client(self):
        """_generate_audio should use httpx.Client for connection pooling."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        # Should use httpx.Client, not httpx.post
        self.assertIn('httpx.Client', source)
        self.assertIn('timeout=timeout', source)
        self.assertIn('limits=limits', source)

    def test_tts_timeout_configuration(self):
        """TTS timeout should be optimized (60s read vs old 180s)."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        # Should have optimized timeout configuration
        self.assertIn('read=60.0', source)
        self.assertIn('connect=10.0', source)

    def test_tts_connection_limits(self):
        """TTS should have explicit connection limits."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('max_connections', source)
        self.assertIn('max_keepalive_connections', source)


class TestConcurrentChunkProcessing(unittest.TestCase):
    """Validate concurrent chunk processing for TTS."""

    def test_uses_thread_pool_executor(self):
        """ElevenLabs TTS should use ThreadPoolExecutor for concurrent chunks."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('ThreadPoolExecutor', source)
        self.assertIn('as_completed', source)

    def test_argent_sequential_processing(self):
        """Argent TTS should process chunks sequentially (server cooldown)."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        # Should have conditional for Argent sequential processing
        self.assertIn('using_argent', source)
        # Sequential path should exist
        self.assertIn('Sequential', source)

    def test_elevenlabs_concurrent_processing(self):
        """ElevenLabs TTS should process chunks concurrently."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        # Should have conditional for ElevenLabs concurrent processing
        self.assertIn('Concurrent', source)

    def test_chunk_ordering_preserved(self):
        """Audio chunks should be sorted by original index after concurrent processing."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('sort(key=lambda x: x[0])', source)


class TestTaskRetryOptimization(unittest.TestCase):
    """Validate task retry optimization with exponential backoff."""

    def test_llm_tasks_use_shared_backoff(self):
        """LLM tasks should use shared exponential backoff function."""
        from tasks.llm_tasks import exponential_backoff_with_jitter
        from celery_app import exponential_backoff_with_jitter as shared_backoff
        self.assertIs(exponential_backoff_with_jitter, shared_backoff)

    def test_audio_tasks_use_shared_backoff(self):
        """Audio tasks should use shared exponential backoff function."""
        from tasks.audio_tasks import exponential_backoff_with_jitter
        from celery_app import exponential_backoff_with_jitter as shared_backoff
        self.assertIs(exponential_backoff_with_jitter, shared_backoff)

    def test_learning_tasks_use_shared_backoff(self):
        """Learning tasks should use shared exponential backoff function."""
        from tasks.learning_tasks import exponential_backoff_with_jitter
        from celery_app import exponential_backoff_with_jitter as shared_backoff
        self.assertIs(exponential_backoff_with_jitter, shared_backoff)


class TestAudioQualityStability(unittest.TestCase):
    """Validate audio quality and stability configurations."""

    def test_audio_bitrate_preserved(self):
        """Audio export should maintain 128k bitrate for quality."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('bitrate="128k"', source)

    def test_mp3_export_format(self):
        """Audio should be exported as MP3 format."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('format="mp3"', source)

    def test_argent_opus_handling(self):
        """Argent Opus audio should be handled correctly."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('Ogg Opus', source)
        self.assertIn('from_file(buf)', source)

    def test_base64_decoding_for_argent(self):
        """Argent audio response should be base64 decoded."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('base64.b64decode', source)


class TestPerformanceRegression(unittest.TestCase):
    """Performance regression tests to ensure optimizations don't degrade."""

    def test_singleton_overhead_minimal(self):
        """Singleton get operation should be fast (< 1ms)."""
        import time
        from tasks import llm_tasks

        llm_tasks._supabase_client = MagicMock()  # Pre-initialized

        start = time.perf_counter()
        for _ in range(100):
            llm_tasks._get_supabase_client()
        elapsed = time.perf_counter() - start

        # 100 calls should take less than 10ms (0.1ms per call)
        self.assertLess(elapsed, 0.01)

    def test_backoff_calculation_fast(self):
        """Exponential backoff calculation should be fast."""
        import time
        from celery_app import exponential_backoff_with_jitter

        start = time.perf_counter()
        for i in range(1000):
            exponential_backoff_with_jitter(i % 5, base_delay=10)
        elapsed = time.perf_counter() - start

        # 1000 calculations should take less than 10ms
        self.assertLess(elapsed, 0.01)


if __name__ == "__main__":
    unittest.main()
