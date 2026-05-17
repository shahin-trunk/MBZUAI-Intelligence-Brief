"""E2E tests for ITER 15: Learning Page Enhancements.

Validates:
  - ContextBanner component shows briefing slide context
  - LearningStats component displays progress metrics
  - PhraseBookmark component persists bookmarks
  - Integration of new components into LanguageLearningView
  - Enhanced UI/UX features (badges, tips, navigation)

Run with:
    cd backend && python -m pytest tests/test_iter15_enhancements.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestContextBanner(unittest.TestCase):
    """Validate ContextBanner component for briefing context alignment."""

    def test_context_banner_file_exists(self):
        """ContextBanner.tsx should exist."""
        banner_path = FRONTEND_DIR / "components" / "language-learning" / "ContextBanner.tsx"
        self.assertTrue(banner_path.exists())

    def test_context_banner_accepts_required_props(self):
        """ContextBanner should accept headline, briefDate, slideIndex."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "ContextBanner.tsx").read_text(encoding="utf-8")

        self.assertIn("headline: string;", content)
        self.assertIn("briefDate: string;", content)
        self.assertIn("slideIndex: number;", content)

    def test_context_banner_has_view_slide_link(self):
        """ContextBanner should have 'View original slide' link."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "ContextBanner.tsx").read_text(encoding="utf-8")

        self.assertIn("View original slide", content)
        self.assertIn("ArrowUpRight", content)

    def test_context_banner_shows_category(self):
        """ContextBanner should display category when available."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "ContextBanner.tsx").read_text(encoding="utf-8")

        self.assertIn("category", content)
        self.assertIn("From briefing", content)

    def test_context_banner_has_visual_design(self):
        """ContextBanner should have gradient background and icon."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "ContextBanner.tsx").read_text(encoding="utf-8")

        self.assertIn("bg-gradient-to-br", content)
        self.assertIn("Eye", content)

    def test_language_learning_view_imports_context_banner(self):
        """LanguageLearningView should import ContextBanner."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LanguageLearningView.tsx").read_text(encoding="utf-8")

        self.assertIn('import ContextBanner', content)

    def test_language_learning_view_renders_context_banner(self):
        """LanguageLearningView should render ContextBanner with props."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LanguageLearningView.tsx").read_text(encoding="utf-8")

        self.assertIn("<ContextBanner", content)
        self.assertIn("headline={item.headline}", content)
        self.assertIn("briefDate={briefDate}", content)
        self.assertIn("slideIndex={slideIndex}", content)


class TestLearningStats(unittest.TestCase):
    """Validate LearningStats component for progress tracking."""

    def test_learning_stats_file_exists(self):
        """LearningStats.tsx should exist."""
        stats_path = FRONTEND_DIR / "components" / "language-learning" / "LearningStats.tsx"
        self.assertTrue(stats_path.exists())

    def test_learning_stats_accepts_required_props(self):
        """LearningStats should accept totalPhrases, completedPhrases, etc."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningStats.tsx").read_text(encoding="utf-8")

        self.assertIn("totalPhrases: number;", content)
        self.assertIn("completedPhrases: number;", content)
        self.assertIn("totalDuration?: number;", content)
        self.assertIn('language: "fr" | "ar";', content)

    def test_learning_stats_calculates_mastery_rate(self):
        """LearningStats should calculate mastery percentage."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningStats.tsx").read_text(encoding="utf-8")

        self.assertIn("masteryRate", content)
        self.assertIn("Math.round", content)

    def test_learning_stats_calculates_xp(self):
        """LearningStats should calculate XP earned."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningStats.tsx").read_text(encoding="utf-8")

        self.assertIn("xpEarned", content)
        self.assertIn("completedPhrases * 10", content)

    def test_learning_stats_displays_four_metrics(self):
        """LearningStats should display Mastery, Phrases, XP, Duration."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningStats.tsx").read_text(encoding="utf-8")

        self.assertIn("Mastery", content)
        self.assertIn("Phrases", content)
        self.assertIn("XP Earned", content)
        self.assertIn("Duration", content)

    def test_learning_stats_has_icons(self):
        """LearningStats should use Lucide icons for metrics."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningStats.tsx").read_text(encoding="utf-8")

        self.assertIn("Target", content)  # Mastery icon
        self.assertIn("Trophy", content)  # Phrases icon
        self.assertIn("Zap", content)     # XP icon
        self.assertIn("Clock", content)   # Duration icon

    def test_language_learning_view_imports_learning_stats(self):
        """LanguageLearningView should import LearningStats."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LanguageLearningView.tsx").read_text(encoding="utf-8")

        self.assertIn('import LearningStats', content)

    def test_language_learning_view_renders_learning_stats(self):
        """LanguageLearningView should render LearningStats on completion."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LanguageLearningView.tsx").read_text(encoding="utf-8")

        self.assertIn("<LearningStats", content)
        self.assertIn("totalPhrases={phrases.length}", content)
        self.assertIn("completedPhrases={completedPhrases.size}", content)


class TestPhraseBookmark(unittest.TestCase):
    """Validate PhraseBookmark component for saving phrases."""

    def test_phrase_bookmark_file_exists(self):
        """PhraseBookmark.tsx should exist."""
        bookmark_path = FRONTEND_DIR / "components" / "language-learning" / "PhraseBookmark.tsx"
        self.assertTrue(bookmark_path.exists())

    def test_phrase_bookmark_accepts_required_props(self):
        """PhraseBookmark should accept phraseId, phraseText, language."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseBookmark.tsx").read_text(encoding="utf-8")

        self.assertIn("phraseId: string;", content)
        self.assertIn("phraseText: string;", content)
        self.assertIn('language: "fr" | "ar";', content)

    def test_phrase_bookmark_persists_to_localstorage(self):
        """PhraseBookmark should save to localStorage."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseBookmark.tsx").read_text(encoding="utf-8")

        self.assertIn("localStorage.setItem", content)
        self.assertIn("localStorage.getItem", content)

    def test_phrase_bookmark_has_toggle_functionality(self):
        """PhraseBookmark should toggle between bookmarked states."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseBookmark.tsx").read_text(encoding="utf-8")

        self.assertIn("toggleBookmark", content)
        self.assertIn("Bookmark", content)
        self.assertIn("BookmarkCheck", content)

    def test_phrase_bookmark_stops_event_propagation(self):
        """PhraseBookmark click should not trigger parent handlers."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseBookmark.tsx").read_text(encoding="utf-8")

        self.assertIn("e.stopPropagation()", content)

    def test_phrase_card_imports_bookmark(self):
        """PhraseCard should import PhraseBookmark."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseCard.tsx").read_text(encoding="utf-8")

        self.assertIn('import PhraseBookmark', content)

    def test_phrase_card_renders_bookmark_script1(self):
        """PhraseCard should render bookmark in script 1 view."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseCard.tsx").read_text(encoding="utf-8")

        # Check that PhraseBookmark appears (we already verified it's imported)
        # Count occurrences - should appear at least twice (script1 and script3)
        bookmark_count = content.count("<PhraseBookmark")
        self.assertGreaterEqual(bookmark_count, 2)

    def test_phrase_card_renders_bookmark_script3(self):
        """PhraseCard should render bookmark in script 3 view."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseCard.tsx").read_text(encoding="utf-8")

        # Check that PhraseBookmark appears after script 3 return
        script3_return = content.find("return (", content.find("Script 3:"))
        self.assertIn("<PhraseBookmark", content[script3_return:])


class TestEnhancedUIFeatures(unittest.TestCase):
    """Validate enhanced UI features in ITER 15."""

    def test_context_banner_has_responsive_design(self):
        """ContextBanner should have responsive sizing."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "ContextBanner.tsx").read_text(encoding="utf-8")

        self.assertIn("text-[12px] sm:text-[13px]", content)

    def test_learning_stats_has_responsive_grid(self):
        """LearningStats should have responsive grid layout."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningStats.tsx").read_text(encoding="utf-8")

        self.assertIn("grid grid-cols-2", content)
        self.assertIn("gap-3 sm:gap-4", content)

    def test_learning_stats_has_responsive_text_sizes(self):
        """LearningStats should scale text sizes."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningStats.tsx").read_text(encoding="utf-8")

        self.assertIn("text-xl sm:text-2xl", content)
        self.assertIn("text-[10px] sm:text-[11px]", content)

    def test_phrase_bookmark_has_visual_states(self):
        """PhraseBookmark should have bookmarked/unbookmarked states."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseBookmark.tsx").read_text(encoding="utf-8")

        self.assertIn("isBookmarked", content)
        self.assertIn("bg-accent-primary/15", content)  # Bookmarked state
        self.assertIn("bg-bg-surface/40", content)      # Default state


class TestPipelineIntegration(unittest.TestCase):
    """Validate ITER 15 components integrate with existing pipeline."""

    def test_context_banner_uses_item_section(self):
        """LanguageLearningView should pass item.section to ContextBanner."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LanguageLearningView.tsx").read_text(encoding="utf-8")

        self.assertIn("category={item.section}", content)

    def test_learning_stats_uses_content_duration(self):
        """LanguageLearningView should pass duration to LearningStats."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LanguageLearningView.tsx").read_text(encoding="utf-8")

        self.assertIn("totalDuration={currentContent?.total_duration_seconds}", content)

    def test_bookmark_uses_phrase_id(self):
        """PhraseCard should pass phrase.id to PhraseBookmark."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseCard.tsx").read_text(encoding="utf-8")

        self.assertIn("phraseId={phrase.id}", content)


if __name__ == "__main__":
    unittest.main()
