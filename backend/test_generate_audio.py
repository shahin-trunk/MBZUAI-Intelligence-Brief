import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import generate_audio


def _sample_brief() -> dict:
    return {
        "brief_metadata": {"date": "2026-03-30"},
        "items": [
            {
                "section": "UAE",
                "headline": "Iran strikes Kuwaiti military camp, injuring 10 soldiers",
                "main_bullet": (
                    "**Iran** conducted a direct missile and drone strike on a **Kuwaiti** military camp. "
                    "[Source: https://example.com/source]"
                ),
                "implication": "Iran is widening its retaliatory strike envelope across Gulf military infrastructure.",
            },
            {
                "section": "Technology",
                "headline": "Anthropic publishes new Claude Code autonomy update",
                "main_bullet": "Anthropic says Claude Code can now handle longer autonomous sessions.",
                "implication": "Agent tooling is moving toward longer unattended execution windows.",
            },
            {
                "section": "Placeholder",
                "headline": "Should not appear",
                "main_bullet": "Placeholder content",
                "implication": "Placeholder implication",
                "is_placeholder": True,
            },
        ],
    }


class SharedOutlineTests(unittest.TestCase):
    def test_shared_outline_numbers_non_placeholder_items(self):
        outline, items = generate_audio._build_shared_outline(_sample_brief())

        self.assertEqual(len(items), 2)
        self.assertIn("LEAD ITEM 1", outline)
        self.assertIn("SECOND LEAD 2", outline)
        self.assertNotIn("Should not appear", outline)
        self.assertIn("Iran strikes Kuwaiti military camp", outline)
        self.assertIn("Anthropic publishes new Claude Code autonomy update", outline)

    def test_clean_outline_text_strips_source_tags_and_urls(self):
        cleaned = generate_audio._clean_outline_text(
            "**Headline** details here [Source: https://example.com/story] https://example.com/story"
        )

        self.assertEqual(cleaned, "Headline details here")


class PromptLoadingTests(unittest.TestCase):
    def test_french_prompt_includes_shared_outline_and_checklist(self):
        brief = _sample_brief()
        outline, _ = generate_audio._build_shared_outline(brief)

        prompt = generate_audio._load_podcast_prompt(brief, outline, lang="fr")

        self.assertIn(outline, prompt)
        self.assertIn("MANDATORY COVERAGE CHECKLIST", prompt)
        self.assertIn("1. [UAE] Iran strikes Kuwaiti military camp, injuring 10 soldiers", prompt)
        self.assertNotIn("{shared_outline}", prompt)


class BudgetAndParsingTests(unittest.TestCase):
    def test_french_budget_is_more_permissive_than_english(self):
        en_budget = generate_audio._get_script_budget("en")
        fr_budget = generate_audio._get_script_budget("fr")

        self.assertGreater(fr_budget["target_words"], en_budget["target_words"])
        self.assertGreater(fr_budget["hard_max_words"], en_budget["hard_max_words"])
        self.assertGreater(fr_budget["hard_max_chars"], en_budget["hard_max_chars"])

    def test_extract_json_object_handles_fenced_payload(self):
        parsed = generate_audio._extract_json_object(
            "```json\n{\"complete\": false, \"missing_item_numbers\": [3], \"notes\": \"tail item missing\"}\n```"
        )

        self.assertEqual(
            parsed,
            {"complete": False, "missing_item_numbers": [3], "notes": "tail item missing"},
        )

    def test_apply_break_markers_collapses_duplicate_breaks(self):
        formatted = generate_audio._apply_break_markers(
            "First paragraph.\n\n<break time=\"0.8s\" />\n\nSecond paragraph."
        )

        self.assertEqual(formatted.count('<break time="0.8s" />'), 1)


if __name__ == "__main__":
    unittest.main()
