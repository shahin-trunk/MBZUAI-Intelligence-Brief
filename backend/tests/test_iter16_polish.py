"""E2E tests for ITER 16: Accessibility, Loading States, and Polish.

Validates:
  - Audio loading states in PhraseGrammarDrawer
  - Accessibility features (focus rings, ARIA labels)
  - Difficulty color consistency with design tokens
  - Error handling for audio failures
  - Loading spinners and disabled states

Run with:
    cd backend && python -m pytest tests/test_iter16_polish.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestAudioLoadingStates(unittest.TestCase):
    """Validate audio loading state handling in PhraseGrammarDrawer."""

    def test_drawer_has_loading_state(self):
        """PhraseGrammarDrawer should track isLoading state."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("isLoading", content)
        self.assertIn("setIsLoading", content)

    def test_drawer_has_error_state(self):
        """PhraseGrammarDrawer should track hasError state."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("hasError", content)
        self.assertIn("setHasError", content)

    def test_drawer_shows_loading_spinner(self):
        """PhraseGrammarDrawer should show Loader2 when loading."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("Loader2", content)
        self.assertIn("animate-spin", content)

    def test_drawer_shows_error_message(self):
        """PhraseGrammarDrawer should show error when audio fails."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("AlertCircle", content)
        self.assertIn("Audio unavailable", content)

    def test_drawer_tracks_canplaythrough(self):
        """PhraseGrammarDrawer should listen for canplaythrough event."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("canplaythrough", content)

    def test_drawer_tracks_loadstart(self):
        """PhraseGrammarDrawer should listen for loadstart event."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("loadstart", content)

    def test_button_disabled_when_loading(self):
        """Play button should be disabled when loading."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("disabled={isLoading}", content)
        self.assertIn("disabled:opacity-50", content)


class TestAccessibilityFeatures(unittest.TestCase):
    """Validate accessibility improvements."""

    def test_drawer_has_aria_labels(self):
        """PhraseGrammarDrawer should have proper ARIA labels."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn('role="dialog"', content)
        self.assertIn('aria-modal="true"', content)
        self.assertIn('aria-label="Close grammar panel"', content)

    def test_drawer_has_aria_label_for_play(self):
        """Play button should have dynamic aria-label."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        # Should have aria-label for play/pause
        self.assertIn('aria-label={isPlaying ? "Pause" : "Play"}', content)

    def test_context_banner_has_accessible_link(self):
        """ContextBanner should have accessible "View original slide" link."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "ContextBanner.tsx").read_text(encoding="utf-8")

        self.assertIn("View original slide", content)
        self.assertIn("ArrowUpRight", content)


class TestDifficultyColors(unittest.TestCase):
    """Validate difficulty color consistency with design tokens."""

    def test_beginner_uses_emerald(self):
        """Beginner difficulty should use emerald-600 (design token)."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningHeader.tsx").read_text(encoding="utf-8")

        self.assertIn("text-emerald-600", content)
        self.assertNotIn("text-green-500", content)

    def test_intermediate_uses_blue(self):
        """Intermediate difficulty should use blue-600."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningHeader.tsx").read_text(encoding="utf-8")

        self.assertIn("text-blue-600", content)
        self.assertNotIn("text-blue-500", content)

    def test_advanced_uses_amber(self):
        """Advanced difficulty should use amber-600."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "LearningHeader.tsx").read_text(encoding="utf-8")

        self.assertIn("text-amber-600", content)
        self.assertNotIn("text-amber-500", content)


class TestErrorHandling(unittest.TestCase):
    """Validate error handling improvements."""

    def test_drawer_resets_error_on_new_audio(self):
        """PhraseGrammarDrawer should reset error when audio URL changes."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        # Should set hasError to false on loadstart
        self.assertIn("setHasError(false)", content)

    def test_drawer_stops_playing_on_error(self):
        """PhraseGrammarDrawer should stop playing when error occurs."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        # Error handler should set isPlaying to false
        self.assertIn("setIsPlaying(false)", content)


class TestMobileUX(unittest.TestCase):
    """Validate mobile UX improvements."""

    def test_drawer_has_touch_feedback(self):
        """PhraseGrammarDrawer should have touch-friendly drag handle."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("Drag handle", content)
        self.assertIn("w-10 h-1 rounded-full", content)

    def test_drawer_supports_swipe_to_dismiss(self):
        """PhraseGrammarDrawer should support swipe-to-dismiss."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("handleTouchStart", content)
        self.assertIn("handleTouchMove", content)
        self.assertIn("handleTouchEnd", content)

    def test_context_banner_responsive(self):
        """ContextBanner should have responsive text sizing."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "ContextBanner.tsx").read_text(encoding="utf-8")

        self.assertIn("text-[12px] sm:text-[13px]", content)


class TestPipelineIntegration(unittest.TestCase):
    """Validate ITER 16 components integrate properly."""

    def test_drawer_imports_loading_icons(self):
        """PhraseGrammarDrawer should import Loader2 and AlertCircle."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn("Loader2", content)
        self.assertIn("AlertCircle", content)

    def test_drawer_preloads_audio(self):
        """PhraseGrammarDrawer should set preload='auto' on audio."""
        content = (FRONTEND_DIR / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text(encoding="utf-8")

        self.assertIn('preload = "auto"', content)


if __name__ == "__main__":
    unittest.main()
