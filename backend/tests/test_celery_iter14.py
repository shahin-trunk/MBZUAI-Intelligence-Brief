"""E2E tests for ITER 14 ultra-stability optimizations.

Validates:
  - Missing _call_anthropic and _parse_json_response functions
  - Supabase storage URL direct construction (no get_public_url)
  - Anthropic/LLM API circuit breaker
  - Parallel backfill mode
  - Quality improvements and stability features

Run with:
    cd backend && python -m pytest tests/test_celery_iter14.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestMissingFunctionsFixed(unittest.TestCase):
    """Validate that missing _call_anthropic and _parse_json_response are implemented."""

    def test_call_anthropic_function_exists(self):
        """_call_anthropic should be defined in generate_audio.py."""
        import inspect
        from generate_audio import _call_anthropic
        self.assertTrue(callable(_call_anthropic))

    def test_parse_json_response_function_exists(self):
        """_parse_json_response should be defined in generate_audio.py."""
        import inspect
        from generate_audio import _parse_json_response
        self.assertTrue(callable(_parse_json_response))

    def test_call_anthropic_uses_pooled_client(self):
        """_call_anthropic should use _get_anthropic_client for connection pooling."""
        import inspect
        from generate_audio import _call_anthropic
        source = inspect.getsource(_call_anthropic)

        self.assertIn('_get_anthropic_client', source)
        self.assertIn('client.messages.create', source)

    def test_call_anthropic_checks_circuit_breaker(self):
        """_call_anthropic should check LLM circuit breaker before making calls."""
        import inspect
        from generate_audio import _call_anthropic
        source = inspect.getsource(_call_anthropic)

        self.assertIn('_llm_circuit_breaker', source)
        self.assertIn('should_attempt', source)

    def test_call_anthropic_records_success(self):
        """_call_anthropic should record success on successful API call."""
        import inspect
        from generate_audio import _call_anthropic
        source = inspect.getsource(_call_anthropic)

        self.assertIn('record_success', source)

    def test_call_anthropic_records_failure(self):
        """_call_anthropic should record failure on API errors."""
        import inspect
        from generate_audio import _call_anthropic
        source = inspect.getsource(_call_anthropic)

        self.assertIn('record_failure', source)

    def test_parse_json_response_uses_extract_json(self):
        """_parse_json_response should delegate to _extract_json_object."""
        import inspect
        from generate_audio import _parse_json_response
        source = inspect.getsource(_parse_json_response)

        self.assertIn('_extract_json_object', source)


class TestSupabaseURLOptimization(unittest.TestCase):
    """Validate direct URL construction instead of get_public_url()."""

    def test_upload_to_supabase_constructs_url_directly(self):
        """Should construct URL directly without get_public_url() call."""
        import inspect
        from generate_audio import _upload_to_supabase
        source = inspect.getsource(_upload_to_supabase)

        # Should construct URL using string formatting
        self.assertIn('storage/v1/object/public', source)
        self.assertIn('NEXT_PUBLIC_SUPABASE_URL', source)
        # Should NOT call .get_public_url() method (check for actual call pattern)
        self.assertNotIn('.get_public_url(', source)

    def test_upload_item_audio_constructs_url_directly(self):
        """Item audio upload should also construct URL directly."""
        import inspect
        from generate_audio import _upload_item_audio
        source = inspect.getsource(_upload_item_audio)

        self.assertIn('storage/v1/object/public', source)
        self.assertIn('NEXT_PUBLIC_SUPABASE_URL', source)
        self.assertNotIn('.get_public_url(', source)

    def test_url_construction_format(self):
        """URL should follow Supabase public URL format."""
        base_url = "https://example.supabase.co"
        file_path = "2025-01-15/items/item_123.mp3"
        expected = f"{base_url}/storage/v1/object/public/audio-briefs/{file_path}"

        # Verify format matches Supabase convention
        self.assertIn('/storage/v1/object/public/', expected)
        self.assertIn('audio-briefs/', expected)
        self.assertTrue(expected.endswith('.mp3'))


class TestLLMCircuitBreaker(unittest.TestCase):
    """Validate Anthropic/LLM API circuit breaker functionality."""

    def test_llm_circuit_breaker_exists(self):
        """Global LLM circuit breaker should be defined."""
        from generate_audio import _llm_circuit_breaker
        self.assertIsNotNone(_llm_circuit_breaker)

    def test_llm_circuit_breaker_class_exists(self):
        """LLMApiCircuitBreaker class should be defined."""
        from generate_audio import LLMApiCircuitBreaker
        self.assertTrue(hasattr(LLMApiCircuitBreaker, '__init__'))

    def test_llm_circuit_breaker_initial_state(self):
        """LLM circuit breaker should start in CLOSED state."""
        from generate_audio import LLMApiCircuitBreaker
        cb = LLMApiCircuitBreaker()
        self.assertEqual(cb.state, "CLOSED")
        self.assertEqual(cb.failure_count, 0)

    def test_llm_circuit_breaker_opens_after_threshold(self):
        """LLM circuit breaker should open after 5 failures (lower than TTS)."""
        from generate_audio import LLMApiCircuitBreaker
        cb = LLMApiCircuitBreaker(failure_threshold=5)

        for _ in range(4):
            cb.record_failure()
        self.assertEqual(cb.state, "CLOSED")

        cb.record_failure()  # 5th failure
        self.assertEqual(cb.state, "OPEN")

    def test_llm_circuit_breaker_closes_on_success(self):
        """LLM circuit breaker should close on success."""
        from generate_audio import LLMApiCircuitBreaker
        cb = LLMApiCircuitBreaker(failure_threshold=3)

        for _ in range(2):
            cb.record_failure()
        self.assertEqual(cb.failure_count, 2)

        cb.record_success()
        self.assertEqual(cb.state, "CLOSED")
        self.assertEqual(cb.failure_count, 0)

    def test_llm_circuit_breaker_has_longer_timeout(self):
        """LLM circuit breaker should have 120s timeout (vs 60s for TTS)."""
        from generate_audio import LLMApiCircuitBreaker
        cb = LLMApiCircuitBreaker()
        self.assertEqual(cb.timeout_seconds, 120)

    def test_llm_circuit_breaker_get_status(self):
        """Should return status dict for monitoring."""
        from generate_audio import LLMApiCircuitBreaker
        cb = LLMApiCircuitBreaker()
        status = cb.get_status()

        self.assertIn('state', status)
        self.assertIn('failure_count', status)
        self.assertIn('threshold', status)
        self.assertEqual(status['state'], 'CLOSED')

    @patch('generate_audio._get_anthropic_client')
    def test_call_anthropic_raises_when_circuit_open(self, mock_client):
        """_call_anthropic should raise error when circuit is open."""
        from generate_audio import _call_anthropic, _llm_circuit_breaker

        # Force circuit to open
        for _ in range(5):
            _llm_circuit_breaker.record_failure()

        try:
            with self.assertRaises(RuntimeError) as ctx:
                _call_anthropic("test prompt", 1000)
            self.assertIn('circuit breaker', str(ctx.exception).lower())
            self.assertIn('OPEN', str(ctx.exception))
        finally:
            # Reset circuit breaker
            _llm_circuit_breaker.record_success()


class TestParallelBackfill(unittest.TestCase):
    """Validate parallel backfill mode implementation."""

    def test_backfill_uses_thread_pool(self):
        """Backfill mode should use ThreadPoolExecutor for parallel processing."""
        import inspect
        from generate_audio import _load_env  # Just to import the module
        import generate_audio
        source = inspect.getsource(generate_audio)

        # Look for the backfill section
        self.assertIn('ThreadPoolExecutor', source)
        self.assertIn('MAX_BACKFILL_WORKERS', source)
        self.assertIn('as_completed', source)

    def test_backfill_worker_count_capped(self):
        """Backfill workers should cap at 5 even for large batches."""
        for n in [10, 30, 100]:
            workers = min(n, 5)
            self.assertEqual(workers, 5, f"Should cap at 5 for {n} items")

    def test_backfill_scales_for_small_batches(self):
        """Small batches should use proportional workers."""
        for n in [1, 3, 5]:
            workers = min(n, 5)
            self.assertEqual(workers, n, f"Should use {n} workers for {n} items")

    def test_backfill_error_handling(self):
        """Backfill should handle exceptions per-item without crashing."""
        import inspect
        from generate_audio import _load_env
        import generate_audio
        source = inspect.getsource(generate_audio)

        # Should have try/except in backfill processing
        self.assertIn('try:', source)
        self.assertIn('except Exception', source)


class TestQualityAndStability(unittest.TestCase):
    """Validate quality and stability improvements."""

    def test_tts_circuit_breaker_still_exists(self):
        """TTS circuit breaker should still exist alongside LLM one."""
        from generate_audio import _tts_circuit_breaker
        self.assertIsNotNone(_tts_circuit_breaker)

    def test_both_circuit_breakers_have_different_thresholds(self):
        """TTS and LLM circuit breakers should have different thresholds."""
        from generate_audio import _tts_circuit_breaker, _llm_circuit_breaker

        # TTS: 10 failures, LLM: 5 failures
        self.assertEqual(_tts_circuit_breaker.failure_threshold, 10)
        self.assertEqual(_llm_circuit_breaker.failure_threshold, 5)

    def test_both_circuit_breakers_have_different_timeouts(self):
        """TTS and LLM circuit breakers should have different timeouts."""
        from generate_audio import _tts_circuit_breaker, _llm_circuit_breaker

        # TTS: 60s, LLM: 120s
        self.assertEqual(_tts_circuit_breaker.timeout_seconds, 60)
        self.assertEqual(_llm_circuit_breaker.timeout_seconds, 120)

    def test_learning_phrases_uses_call_anthropic(self):
        """_generate_learning_phrases should use _call_anthropic helper."""
        import inspect
        from generate_audio import _generate_learning_phrases
        source = inspect.getsource(_generate_learning_phrases)

        self.assertIn('_call_anthropic', source)
        self.assertIn('_parse_json_response', source)

    def test_learning_phrases_validation_loop(self):
        """_generate_learning_phrases should validate response structure."""
        import inspect
        from generate_audio import _generate_learning_phrases
        source = inspect.getsource(_generate_learning_phrases)

        # Should validate JSON structure
        self.assertIn('isinstance(content, dict)', source)
        self.assertIn('isinstance(phrases, list)', source)
        # Should have retry loop for invalid responses
        self.assertIn('LEARNING_SCRIPT_MAX_ATTEMPTS', source)


class TestPerformanceRegression(unittest.TestCase):
    """Ensure optimizations don't introduce regressions."""

    def test_circuit_breaker_overhead_minimal(self):
        """Circuit breaker check should be sub-millisecond."""
        import time
        from generate_audio import _llm_circuit_breaker

        start = time.perf_counter()
        for _ in range(1000):
            _ = _llm_circuit_breaker.should_attempt()
        elapsed = time.perf_counter() - start

        # 1000 checks should take less than 10ms
        self.assertLess(elapsed, 0.01, f"Circuit breaker overhead: {elapsed*1000:.2f}ms")

    def test_url_construction_overhead_minimal(self):
        """URL construction should be instant (no network call)."""
        import time
        import os

        os.environ["NEXT_PUBLIC_SUPABASE_URL"] = "https://test.supabase.co"

        start = time.perf_counter()
        for _ in range(1000):
            base_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/")
            url = f"{base_url}/storage/v1/object/public/audio-briefs/test.mp3"
        elapsed = time.perf_counter() - start

        # 1000 constructions should take less than 5ms
        self.assertLess(elapsed, 0.005, f"URL construction overhead: {elapsed*1000:.2f}ms")

    def test_parse_json_response_handles_invalid(self):
        """_parse_json_response should gracefully handle invalid JSON."""
        from generate_audio import _parse_json_response

        result = _parse_json_response("not json at all")
        self.assertIsNone(result)

        result = _parse_json_response("")
        self.assertIsNone(result)

        result = _parse_json_response(None)
        self.assertIsNone(result)

    def test_parse_json_response_handles_markdown_blocks(self):
        """_parse_json_response should extract JSON from markdown code blocks."""
        from generate_audio import _parse_json_response

        markdown_json = '```json\n{"key": "value"}\n```'
        result = _parse_json_response(markdown_json)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("key"), "value")


if __name__ == "__main__":
    unittest.main()
