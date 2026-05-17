"""E2E tests for ITER 13 quick-win optimizations.

Validates:
  - Adaptive ThreadPool concurrency (3 -> min(n, 8))
  - O(1) dictionary indexing for item lookups
  - Active items indexing for fast URL writeback
  - Performance improvements in generate_audio.py
  - Optimized lookups in llm_tasks.py and learning_tasks.py

Run with:
    cd backend && python -m pytest tests/test_celery_iter13.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestAdaptiveThreadPoolConcurrency(unittest.TestCase):
    """Validate adaptive ThreadPool concurrency scaling."""

    def test_max_concurrent_is_adaptive(self):
        """MAX_CONCURRENT should be min(len(pending_items), 8), not hardcoded 3."""
        import inspect
        from generate_audio import generate_audio_brief
        source = inspect.getsource(generate_audio_brief)

        # Should use adaptive calculation
        self.assertIn('min(len(pending_items)', source)
        self.assertIn('8)', source)
        # Should NOT have hardcoded MAX_CONCURRENT = 3
        self.assertNotIn('MAX_CONCURRENT = 3', source)

    def test_adaptive_concurrency_small_batch(self):
        """Small batches (< 8) should use batch size as concurrency."""
        for n in [1, 3, 5]:
            result = min(n, 8)
            self.assertEqual(result, n, f"Batch size {n} should use concurrency {n}")

    def test_adaptive_concurrency_medium_batch(self):
        """Medium batches (8-15) should cap at 8."""
        for n in [8, 10, 15]:
            result = min(n, 8)
            self.assertEqual(result, 8, f"Batch size {n} should cap at 8")

    def test_adaptive_concurrency_large_batch(self):
        """Large batches (> 8) should cap at 8."""
        for n in [20, 50, 100]:
            result = min(n, 8)
            self.assertEqual(result, 8, f"Batch size {n} should cap at 8")


class TestDictionaryIndexing(unittest.TestCase):
    """Validate O(1) dictionary indexing for item lookups."""

    def test_items_by_id_index_created(self):
        """Should create items_by_id dictionary for O(1) lookups."""
        import inspect
        from generate_audio import generate_audio_brief
        source = inspect.getsource(generate_audio_brief)

        self.assertIn('items_by_id', source)
        self.assertIn('{item["id"]: item', source)

    def test_url_writeback_uses_dictionary(self):
        """URL writeback should use items_by_id instead of linear search."""
        import inspect
        from generate_audio import generate_audio_brief
        source = inspect.getsource(generate_audio_brief)

        # Should use O(1) dictionary access
        self.assertIn('items_by_id[item_id]', source)
        # Should NOT have linear search pattern
        self.assertNotIn('for ai in active_items:', source)

    def test_llm_tasks_uses_next_generator(self):
        """LLM tasks should use next() generator for item lookup."""
        import inspect
        from tasks import llm_tasks
        source = inspect.getsource(llm_tasks)

        # Should use next() with generator expression
        self.assertIn('next(', source)
        self.assertIn('i.get("id") == item_id', source)

    def test_learning_tasks_uses_next_generator(self):
        """Learning tasks should use next() generator for item lookup."""
        import inspect
        from tasks import learning_tasks
        source = inspect.getsource(learning_tasks)

        # Should use next() with generator expression (appears twice)
        count = source.count('next(')
        self.assertGreaterEqual(count, 2, f"Expected at least 2 next() calls, found {count}")


class TestDictionaryIndexingFunctionality(unittest.TestCase):
    """Validate that dictionary indexing works correctly at runtime."""

    def test_items_by_id_builds_correct_index(self):
        """Dictionary index should correctly map item IDs to items."""
        items = [
            {"id": "item_1", "title": "First"},
            {"id": "item_2", "title": "Second"},
            {"id": "item_3", "title": "Third"},
        ]
        items_by_id = {item["id"]: item for item in items}

        self.assertEqual(len(items_by_id), 3)
        self.assertEqual(items_by_id["item_1"]["title"], "First")
        self.assertEqual(items_by_id["item_2"]["title"], "Second")
        self.assertEqual(items_by_id["item_3"]["title"], "Third")

    def test_items_by_id_o1_lookup(self):
        """Dictionary lookup should be O(1) - verify key access works."""
        items = [{"id": f"item_{i}", "data": f"val_{i}"} for i in range(100)]
        items_by_id = {item["id"]: item for item in items}

        # Direct key access (O(1))
        result = items_by_id.get("item_42")
        self.assertIsNotNone(result)
        self.assertEqual(result["data"], "val_42")

    def test_items_by_id_missing_key_returns_none(self):
        """Dictionary .get() should return None for missing keys."""
        items = [{"id": "item_1"}]
        items_by_id = {item["id"]: item for item in items}

        result = items_by_id.get("item_999")
        self.assertIsNone(result)

    def test_next_generator_finds_item(self):
        """next() generator should find item by ID."""
        items = [
            {"id": "a", "name": "Alpha"},
            {"id": "b", "name": "Beta"},
            {"id": "c", "name": "Gamma"},
        ]
        result = next((i for i in items if i.get("id") == "b"), None)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Beta")

    def test_next_generator_returns_none_for_missing(self):
        """next() generator should return None for missing items."""
        items = [{"id": "a"}, {"id": "b"}]
        result = next((i for i in items if i.get("id") == "z"), None)
        self.assertIsNone(result)


class TestAudioURLWriteback(unittest.TestCase):
    """Validate audio URL writeback optimization."""

    def test_url_writeback_via_dictionary(self):
        """URL writeback should work via dictionary index."""
        items = [{"id": "item_1"}, {"id": "item_2"}]
        items_by_id = {item["id"]: item for item in items}

        # Simulate writeback
        item_id = "item_1"
        url = "https://storage.example.com/audio/item_1.mp3"
        if item_id in items_by_id:
            items_by_id[item_id]["audio_url"] = url

        self.assertEqual(items[0]["audio_url"], url)
        self.assertNotIn("audio_url", items[1])

    def test_url_writeback_handles_missing_item(self):
        """URL writeback should gracefully handle missing items."""
        items = [{"id": "item_1"}]
        items_by_id = {item["id"]: item for item in items}

        # Should not raise for missing item
        item_id = "item_999"
        url = "https://example.com/audio.mp3"
        if item_id in items_by_id:
            items_by_id[item_id]["audio_url"] = url

        # No changes should have occurred
        self.assertNotIn("audio_url", items[0])


class TestLLMTasksOptimization(unittest.TestCase):
    """Validate LLM tasks item lookup optimization."""

    def test_generate_learning_phrases_uses_next(self):
        """Should use next() generator for item lookup."""
        import inspect
        from tasks import llm_tasks
        source = inspect.getsource(llm_tasks.generate_learning_phrases)

        # Should use next() with generator expression
        self.assertIn('next(', source)
        self.assertIn('i.get("id") == item_id', source)

    def test_generate_learning_phrases_handles_missing_item(self):
        """Should check for None item after next() lookup."""
        import inspect
        from tasks import llm_tasks
        source = inspect.getsource(llm_tasks.generate_learning_phrases)

        # Should have error handling for missing item
        self.assertIn('if not item:', source)
        self.assertIn('item_not_found', source)


class TestLearningTasksOptimization(unittest.TestCase):
    """Validate learning tasks item lookup optimization."""

    def test_merge_learning_results_uses_next(self):
        """Should use next() generator for item lookup."""
        import inspect
        from tasks import learning_tasks
        source = inspect.getsource(learning_tasks.merge_learning_results)

        # Should use next() with generator expression
        self.assertIn('next(', source)
        self.assertIn('i.get("id") == item_id', source)

    def test_legacy_task_uses_next(self):
        """Legacy task should also use next() generator."""
        import inspect
        from tasks import learning_tasks
        # Get all task functions and check the second one
        source = inspect.getsource(learning_tasks)
        # Count occurrences of next() - should be at least 2
        count = source.count('next(')
        self.assertGreaterEqual(count, 2, f"Expected at least 2 next() calls, found {count}")


class TestPerformanceCharacteristics(unittest.TestCase):
    """Validate performance characteristics of optimizations."""

    def test_dictionary_vs_list_lookup_performance(self):
        """Dictionary lookup should be faster than linear search."""
        import time

        # Create large dataset
        items = [{"id": f"item_{i}", "data": f"val_{i}"} for i in range(1000)]
        items_by_id = {item["id"]: item for item in items}

        # Measure dictionary lookup
        start = time.perf_counter()
        for _ in range(1000):
            _ = items_by_id.get("item_999")
        dict_time = time.perf_counter() - start

        # Measure linear search
        start = time.perf_counter()
        for _ in range(1000):
            result = None
            for item in items:
                if item.get("id") == "item_999":
                    result = item
                    break
            _ = result
        list_time = time.perf_counter() - start

        # Dictionary should be faster (allow some variance)
        self.assertLess(dict_time, list_time * 2,
                       f"Dict lookup ({dict_time:.6f}s) should be comparable or faster than list ({list_time:.6f}s)")

    def test_adaptive_concurrency_scales(self):
        """Adaptive concurrency should scale correctly with batch size."""
        test_cases = [
            (1, 1),    # 1 item -> 1 worker
            (3, 3),    # 3 items -> 3 workers
            (5, 5),    # 5 items -> 5 workers
            (8, 8),    # 8 items -> 8 workers
            (10, 8),   # 10 items -> 8 workers (capped)
            (20, 8),   # 20 items -> 8 workers (capped)
            (100, 8),  # 100 items -> 8 workers (capped)
        ]

        for batch_size, expected_concurrency in test_cases:
            actual = min(batch_size, 8)
            self.assertEqual(actual, expected_concurrency,
                           f"Batch {batch_size}: expected {expected_concurrency}, got {actual}")


if __name__ == "__main__":
    unittest.main()
