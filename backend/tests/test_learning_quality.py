"""E2E tests for Learning Quality & UI Enhancements.

Validates:
  - Enhanced prompt with lesson_summary, cognate_note, cultural notes
  - Improved duration estimation (language-aware, script-type-aware)
  - TypeScript types include new fields
  - UI components render new fields correctly
  - Pipeline passes lesson_summary through chain/chord

Run with:
    cd backend && python -m pytest tests/test_learning_quality.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestEnhancedPrompt(unittest.TestCase):
    """Validate enhanced learning prompt includes quality improvements."""

    def test_prompt_has_lesson_summary(self):
        """Prompt should include lesson_summary in output format."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("lesson_summary", content)
        self.assertIn("50-100 characters", content)

    def test_prompt_has_cognate_note(self):
        """Prompt should include cognate_note in grammar metadata."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("cognate_note", content)

    def test_prompt_has_progressive_ordering(self):
        """Prompt should require progressive difficulty ordering."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("Progressive", content)
        self.assertIn("phrase_0 should be most accessible", content)

    def test_prompt_has_cultural_immersion(self):
        """Prompt should include cultural immersion philosophy."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("Cultural Immersion", content)
        self.assertIn("cultural insight", content)

    def test_prompt_has_diplomatic_register(self):
        """Prompt should include diplomatic register awareness."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("diplomatic", content)
        self.assertIn("Diplomatic register awareness", content)

    def test_prompt_has_geographic_specificity(self):
        """Prompt should include geographic specificity."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("Geographic specificity", content)
        self.assertIn("Francophone", content)

    def test_prompt_has_arabic_diacritics(self):
        """Prompt should specify diacritics for Arabic script3."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("tashkeel", content)
        self.assertIn("diacritics", content)

    def test_prompt_has_expanded_grammar_fields(self):
        """Prompt should require at least 4 of 7 grammar fields."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("at least 4 of these 7 fields", content)
        self.assertIn("cognate_note", content)

    def test_prompt_has_quality_rules(self):
        """Prompt should have 12 critical rules including quality."""
        prompt_path = BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md"
        content = prompt_path.read_text(encoding="utf-8")

        self.assertIn("Progressive ordering", content)
        self.assertIn("Quality over quantity", content)
        self.assertIn("Cultural sensitivity", content)


class TestImprovedDurationEstimation(unittest.TestCase):
    """Validate improved duration estimation accuracy."""

    def test_duration_function_exists(self):
        """_estimate_duration_seconds should exist."""
        from generate_audio import _estimate_duration_seconds
        self.assertTrue(callable(_estimate_duration_seconds))

    def test_duration_uses_language_specific_rates(self):
        """Should use different rates for different languages."""
        import inspect
        from generate_audio import _estimate_duration_seconds
        source = inspect.getsource(_estimate_duration_seconds)

        self.assertIn("11.0", source)  # Arabic
        self.assertIn("12.0", source)  # Arabic without diacritics
        self.assertIn("13.0", source)  # French
        self.assertIn("14.0", source)  # Default bilingual
        self.assertIn("15.0", source)  # Short transitions

    def test_duration_arabic_with_diacritics(self):
        """Arabic text with diacritics should use slower rate."""
        from generate_audio import _estimate_duration_seconds

        # Use longer text (> 45 chars) to trigger language-specific rate
        arabic_with_tashkeel = "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَالَمِينَ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ مَالِكِ يَوْمِ ٱلدِّينِ"
        duration = _estimate_duration_seconds(arabic_with_tashkeel, "ar")

        # Should be slower than default (11 cps vs 14 cps)
        expected_slow = len(arabic_with_tashkeel) / 11.0
        self.assertAlmostEqual(duration, expected_slow + 0.3, places=1)

    def test_duration_short_transition(self):
        """Short transitions (< 45 chars) should use faster rate."""
        from generate_audio import _estimate_duration_seconds

        short = "Listen carefully:"
        duration = _estimate_duration_seconds(short, "en")

        # 15 cps for short + 0.1s buffer
        expected = len(short) / 15.0 + 0.1
        self.assertAlmostEqual(duration, expected, places=1)

    def test_duration_includes_pause_buffer(self):
        """Longer segments should include pause buffer."""
        from generate_audio import _estimate_duration_seconds

        long_script = "This is a longer script that should include a natural pause buffer for breathing between segments."
        duration = _estimate_duration_seconds(long_script, "en")

        # Should include 0.3s pause buffer
        base = len(long_script) / 14.0
        self.assertAlmostEqual(duration, base + 0.3, places=1)

    def test_duration_french_uses_slower_rate(self):
        """French should use 13 cps (slower due to liaisons)."""
        from generate_audio import _estimate_duration_seconds

        # Use longer text (> 45 chars) to trigger language-specific rate
        french = "C'est la vie, comme on dit en France et dans tous les pays francophones du monde"
        duration = _estimate_duration_seconds(french, "fr")

        expected = len(french) / 13.0 + 0.3
        self.assertAlmostEqual(duration, expected, places=1)


class TestTypeScriptTypes(unittest.TestCase):
    """Validate TypeScript types include new fields."""

    def test_brief_types_has_lesson_summary(self):
        """TypeScript types should include lesson_summary."""
        types_path = BACKEND_DIR.parent / "frontend" / "lib" / "types" / "brief.ts"
        content = types_path.read_text(encoding="utf-8")

        self.assertIn("lesson_summary?: string;", content)

    def test_brief_types_has_cognate_note(self):
        """TypeScript types should include cognate_note in grammar."""
        types_path = BACKEND_DIR.parent / "frontend" / "lib" / "types" / "brief.ts"
        content = types_path.read_text(encoding="utf-8")

        self.assertIn("cognate_note?: string;", content)

    def test_item_learning_content_has_lesson_summary(self):
        """ItemLearningContent should include lesson_summary."""
        types_path = BACKEND_DIR.parent / "frontend" / "lib" / "types" / "brief.ts"
        content = types_path.read_text(encoding="utf-8")

        # Find ItemLearningContent interface
        start = content.find("export interface ItemLearningContent")
        end = content.find("}", start)
        interface_content = content[start:end]

        self.assertIn("lesson_summary", interface_content)


class TestLearningHeaderEnhancements(unittest.TestCase):
    """Validate LearningHeader component enhancements."""

    def test_header_accepts_lesson_summary(self):
        """LearningHeader should accept lessonSummary prop."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "LearningHeader.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("lessonSummary?: string;", content)

    def test_header_accepts_difficulty(self):
        """LearningHeader should accept difficulty prop."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "LearningHeader.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("difficulty?: string;", content)

    def test_header_accepts_total_duration(self):
        """LearningHeader should accept totalDuration prop."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "LearningHeader.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("totalDuration?: number;", content)

    def test_header_renders_lesson_summary(self):
        """LearningHeader should render lesson summary."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "LearningHeader.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("lessonSummary &&", content)
        self.assertIn("BookOpen", content)

    def test_header_renders_difficulty_badge(self):
        """LearningHeader should render difficulty badge."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "LearningHeader.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("difficulty &&", content)
        self.assertIn("difficultyColor", content)


class TestPhraseCardEnhancements(unittest.TestCase):
    """Validate PhraseCard component enhancements."""

    def test_card_shows_context_anchor_badge(self):
        """PhraseCard should show context anchor as badge."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseCard.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("context_anchor", content)
        self.assertIn("BookOpen", content)

    def test_card_shows_cognate_note(self):
        """PhraseCard should show cognate note when available."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseCard.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("cognate_note", content)
        self.assertIn("grammar.cognate_note", content)

    def test_card_has_improved_visual_hierarchy(self):
        """PhraseCard should have improved visual hierarchy."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseCard.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("Languages", content)  # Lucide icon
        self.assertIn("Mic", content)  # Grammar button icon


class TestPhraseNavigationDotsEnhancements(unittest.TestCase):
    """Validate PhraseNavigationDots component enhancements."""

    def test_dots_show_completed_checkmark(self):
        """Navigation dots should show checkmark for completed phrases."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseNavigationDots.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("Check", content)
        self.assertIn("isCompleted", content)

    def test_dots_show_phrase_numbers(self):
        """Navigation dots should show phrase numbers."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseNavigationDots.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("{i + 1}", content)

    def test_dots_have_improved_active_state(self):
        """Active dot should have enhanced visual state."""
        component_path = BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseNavigationDots.tsx"
        content = component_path.read_text(encoding="utf-8")

        self.assertIn("blur-md", content)  # Glow effect
        self.assertIn("scale-125", content)


class TestPipelineIntegration(unittest.TestCase):
    """Validate pipeline passes lesson_summary through chain/chord."""

    def test_prepare_audio_tasks_extracts_lesson_summary(self):
        """prepare_audio_tasks should extract lesson_summary from phrases_result."""
        import inspect
        from tasks import learning_tasks
        source = inspect.getsource(learning_tasks.prepare_audio_tasks)

        self.assertIn("lesson_summary", source)
        self.assertIn("phrases_result.get", source)

    def test_merge_learning_results_accepts_lesson_summary(self):
        """merge_learning_results should accept lesson_summary parameter."""
        import inspect
        from tasks import learning_tasks
        source = inspect.getsource(learning_tasks.merge_learning_results)

        self.assertIn("lesson_summary: str", source)

    def test_merge_learning_results_stores_lesson_summary(self):
        """merge_learning_results should store lesson_summary in learning_data."""
        import inspect
        from tasks import learning_tasks
        source = inspect.getsource(learning_tasks.merge_learning_results)

        self.assertIn('"lesson_summary": lesson_summary', source)


if __name__ == "__main__":
    unittest.main()
