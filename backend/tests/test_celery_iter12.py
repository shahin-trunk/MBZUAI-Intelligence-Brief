"""E2E tests for ITER 12 ultra-efficiency optimizations.

Validates:
  - Celery chain/chord non-blocking orchestration
  - TTS circuit breaker functionality
  - Audio normalization and loudness leveling
  - Anthropic client pooling
  - Learning task workflow (prepare_audio_tasks, merge_learning_results)

Run with:
    cd backend && python -m pytest tests/test_celery_iter12.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestTaskChaining(unittest.TestCase):
    """Validate Celery chain/chord orchestration in learning tasks."""

    def test_learning_tasks_imports_chain_chord(self):
        """Learning tasks should import chain and chord from Celery."""
        import inspect
        from tasks import learning_tasks
        source = inspect.getsource(learning_tasks)

        self.assertIn('from celery import chain, chord, group', source)

    def test_prepare_audio_tasks_exists(self):
        """Should have prepare_audio_tasks intermediate task."""
        from tasks import learning_tasks
        self.assertTrue(hasattr(learning_tasks, 'prepare_audio_tasks'))

    def test_merge_learning_results_exists(self):
        """Should have merge_learning_results chord callback."""
        from tasks import learning_tasks
        self.assertTrue(hasattr(learning_tasks, 'merge_learning_results'))

    def test_generate_learning_content_uses_chain(self):
        """Main task should use chain pattern instead of .get()."""
        import inspect
        from tasks import learning_tasks
        source = inspect.getsource(learning_tasks.generate_learning_content)

        # Should use chain, not .get()
        self.assertIn('chain(', source)
        # Old blocking pattern should not be present
        self.assertNotIn('.get(timeout=', source)

    def test_prepare_audio_tasks_uses_chord(self):
        """Intermediate task should use chord for fan-out."""
        import inspect
        from tasks import learning_tasks
        source = inspect.getsource(learning_tasks.prepare_audio_tasks)

        self.assertIn('chord(', source)


class TestTTSCircuitBreaker(unittest.TestCase):
    """Validate TTS circuit breaker functionality."""

    def setUp(self):
        from generate_audio import TTSCircuitBreaker
        self.breaker = TTSCircuitBreaker(failure_threshold=3, timeout_seconds=1)

    def test_initial_state_closed(self):
        """Circuit should start in CLOSED state."""
        self.assertEqual(self.breaker.state, "CLOSED")
        self.assertTrue(self.breaker.should_attempt())

    def test_opens_after_threshold(self):
        """Circuit should open after failure_threshold failures."""
        for _ in range(3):
            self.breaker.record_failure()
        self.assertEqual(self.breaker.state, "OPEN")
        self.assertFalse(self.breaker.should_attempt())

    def test_half_open_after_timeout(self):
        """Circuit should transition to HALF_OPEN after timeout."""
        import time
        # Trigger open state
        for _ in range(3):
            self.breaker.record_failure()
        self.assertEqual(self.breaker.state, "OPEN")

        # Wait for timeout
        time.sleep(1.1)
        self.assertTrue(self.breaker.should_attempt())
        self.assertEqual(self.breaker.state, "HALF_OPEN")

    def test_closes_on_success(self):
        """Circuit should close on successful request in HALF_OPEN."""
        # Get to half-open
        for _ in range(3):
            self.breaker.record_failure()
        import time
        time.sleep(1.1)
        self.breaker.should_attempt()  # Transitions to HALF_OPEN

        # Record success
        self.breaker.record_success()
        self.assertEqual(self.breaker.state, "CLOSED")
        self.assertTrue(self.breaker.should_attempt())

    def test_global_circuit_breaker_exists(self):
        """Global circuit breaker instance should be initialized."""
        from generate_audio import _tts_circuit_breaker
        self.assertIsNotNone(_tts_circuit_breaker)
        self.assertIsInstance(_tts_circuit_breaker, object)

    def test_get_status(self):
        """Should return status dict for monitoring."""
        status = self.breaker.get_status()
        self.assertIn("state", status)
        self.assertIn("failure_count", status)
        self.assertIn("threshold", status)


class TestAudioNormalization(unittest.TestCase):
    """Validate audio normalization implementation."""

    def test_normalization_code_exists(self):
        """_generate_audio should include loudness normalization."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('target_loudness', source)
        self.assertIn('dBFS', source)
        self.assertIn('apply_gain', source)

    def test_limiter_applied(self):
        """Should apply final limiter to prevent clipping."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('max_dBFS', source)
        self.assertIn('limiter', source.lower())

    def test_gain_limiting(self):
        """Gain adjustment should be limited to +/- 6 dB."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('-6.0', source)
        self.assertIn('6.0', source)


class TestAnthropicClientPooling(unittest.TestCase):
    """Validate Anthropic client pooling."""

    def test_pooled_client_function_exists(self):
        """Should have _get_anthropic_client function."""
        from generate_audio import _get_anthropic_client
        self.assertTrue(callable(_get_anthropic_client))

    def test_uses_pooled_client_in_functions(self):
        """All Anthropic calls should use pooled client."""
        import inspect
        from generate_audio import (
            _audit_script_coverage,
            _generate_script,
            _compress_script,
        )

        for func in [_audit_script_coverage, _generate_script, _compress_script]:
            source = inspect.getsource(func)
            self.assertIn('_get_anthropic_client()', source,
                         f"{func.__name__} should use pooled client")

    def test_no_direct_client_creation(self):
        """No function should create anthropic.Anthropic() directly."""
        import inspect
        from generate_audio import (
            _audit_script_coverage,
            _generate_script,
            _compress_script,
        )

        for func in [_audit_script_coverage, _generate_script, _compress_script]:
            source = inspect.getsource(func)
            self.assertNotIn('anthropic.Anthropic(api_key=', source,
                           f"{func.__name__} should not create client directly")

    def test_singleton_returns_same_instance(self):
        """Pooled client should return same instance."""
        from generate_audio import _get_anthropic_client
        import generate_audio
        import os

        # Reset for test and set fake API key
        original = generate_audio._anthropic_client
        original_key = os.environ.get("ANTHROPIC_API_KEY")
        generate_audio._anthropic_client = None
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        try:
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = MagicMock()
                mock_anthropic.return_value = mock_client

                # First call creates client
                client1 = _get_anthropic_client()
                # Second call returns same instance
                client2 = _get_anthropic_client()

                self.assertIs(client1, client2)
                mock_anthropic.assert_called_once()
        finally:
            generate_audio._anthropic_client = original
            if original_key:
                os.environ["ANTHROPIC_API_KEY"] = original_key
            elif "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]


class TestCircuitBreakerIntegration(unittest.TestCase):
    """Test circuit breaker integration with _generate_audio."""

    def test_generate_audio_checks_circuit_breaker(self):
        """_generate_audio should check circuit breaker before attempting."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('_tts_circuit_breaker.should_attempt()', source)

    def test_generate_audio_records_failures(self):
        """_generate_audio should record failures in circuit breaker."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('_tts_circuit_breaker.record_failure()', source)

    def test_generate_audio_records_success(self):
        """_generate_audio should record success in circuit breaker."""
        import inspect
        from generate_audio import _generate_audio
        source = inspect.getsource(_generate_audio)

        self.assertIn('_tts_circuit_breaker.record_success()', source)


class TestPerformanceRegression(unittest.TestCase):
    """Ensure optimizations don't introduce performance regressions."""

    def test_circuit_breaker_overhead_minimal(self):
        """Circuit breaker check should be fast (< 0.1ms)."""
        import time
        from generate_audio import _tts_circuit_breaker

        start = time.perf_counter()
        for _ in range(1000):
            _tts_circuit_breaker.should_attempt()
        elapsed = time.perf_counter() - start

        # 1000 checks should take less than 10ms
        self.assertLess(elapsed, 0.01)

    def test_anthropic_pooling_overhead_minimal(self):
        """Pooled client lookup should be fast."""
        import time
        from generate_audio import _get_anthropic_client, _anthropic_client

        # Pre-initialize
        if _anthropic_client is None:
            generate_audio = sys.modules.get('generate_audio')
            if generate_audio:
                generate_audio._anthropic_client = MagicMock()

        start = time.perf_counter()
        for _ in range(1000):
            _get_anthropic_client()
        elapsed = time.perf_counter() - start

        # 1000 lookups should take less than 10ms
        self.assertLess(elapsed, 0.01)


if __name__ == "__main__":
    unittest.main()
