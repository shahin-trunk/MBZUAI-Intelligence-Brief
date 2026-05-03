import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pipeline.orchestrator as orchestrator
import pipeline.enricher as enricher
from pipeline.manual_entries import convert_to_gatekeeper_shape
from pipeline.model_release import is_probable_model_release


class TriageParsingTests(unittest.TestCase):
    def test_parse_triage_keep_indices_extracts_dict_wrapped_keep_list(self):
        malformed_response = {
            "keep_indices": [0, 2, 5, 9],
            "notes": "Model wrapped the list in an object instead of returning a bare array.",
        }

        self.assertEqual(
            orchestrator._parse_triage_keep_indices(malformed_response),
            [0, 2, 5, 9],
        )

    def test_triage_log_captures_raw_response_and_input_size(self):
        items = [
            {"headline": "Alpha headline"},
            {"headline": "Beta headline"},
            {"headline": "Gamma headline"},
        ]
        saved = {}

        class FakeMessages:
            async def create(self, **_kwargs):
                return SimpleNamespace(
                    content=[SimpleNamespace(text='{"keep_indices":[1,3]}')]
                )

        fake_client = SimpleNamespace(messages=FakeMessages())

        def fake_save_intermediate(filename, data):
            saved["filename"] = filename
            saved["data"] = data
            return Path("/tmp") / filename

        with patch.object(orchestrator, "save_intermediate", fake_save_intermediate):
            kept = asyncio.run(orchestrator.triage_collected_items(items, fake_client))

        self.assertEqual([item["headline"] for item in kept], ["Alpha headline", "Gamma headline"])
        self.assertEqual(saved["filename"], f"triage_output_{orchestrator.get_today_date()}.json")
        self.assertEqual(saved["data"]["status"], "ok")
        self.assertEqual(saved["data"]["total_input"], 3)
        self.assertIn("approx_input_chars", saved["data"])
        self.assertGreater(saved["data"]["approx_input_chars"], 0)
        self.assertIn("approx_input_tokens_estimate", saved["data"])
        self.assertEqual(saved["data"]["attempts"][0]["raw_response"], '{"keep_indices":[1,3]}')
        self.assertEqual(saved["data"]["attempts"][0]["parsed_top_level_type"], "dict")


class ContentFilterBatchingTests(unittest.TestCase):
    def test_content_filter_batching_splits_368_items_and_recombines_results(self):
        items = [
            {
                "headline": f"Headline {i}",
                "source": "Source",
                "source_url": f"https://example.com/{i}",
                "date": "2026-03-16",
                "summary": f"Summary {i}",
                "category": "news",
                "also_covered_by": [],
            }
            for i in range(368)
        ]

        ranges = orchestrator._content_filter_batch_ranges(len(items))
        batch_sizes = [end - start for start, end in ranges]
        self.assertEqual(batch_sizes, [46] * 8)
        self.assertTrue(all(40 <= size <= 50 for size in batch_sizes))

        async def fake_run_content_filter(_client, prompt_text: str):
            batch_items = json.loads(prompt_text)
            verdicts = []
            for item in batch_items:
                keep = item["id"] % 7 != 0
                verdicts.append(
                    {
                        "id": item["id"],
                        "headline": item["headline"],
                        "date_check": "pass",
                        "news_test": "pass" if keep else "fail",
                        "duplicate_of": None,
                        "keep": keep,
                        "reason": "" if keep else "batched content filter drop",
                    }
                )
            return {"verdicts": verdicts}, {"input_tokens": 10, "output_tokens": 5}

        expected_drop_count = sum(1 for i in range(368) if i % 7 == 0)

        with patch.object(orchestrator, "load_prompt", lambda _filename, items_json="", **_kwargs: items_json):
            with patch.object(orchestrator, "run_content_filter", fake_run_content_filter):
                news_items, drops, verdicts, usage, batches = asyncio.run(
                    orchestrator.run_content_filter_batched(None, items)
                )

        self.assertEqual(len(batches), 8)
        self.assertTrue(all(batch["status"] == "ok" for batch in batches))
        self.assertEqual([batch["item_count"] for batch in batches], batch_sizes)
        self.assertEqual(len(verdicts), 368)
        self.assertEqual(len(drops), expected_drop_count)
        self.assertEqual(len(news_items), 368 - expected_drop_count)
        self.assertEqual(usage, {"input_tokens": 80, "output_tokens": 40})


class ManualEntryIdTests(unittest.TestCase):
    def test_manual_entry_ids_stay_stable_across_partial_resume_conversions(self):
        cached_rows = [
            {
                "id": "123",
                "brief_section": "UAE",
                "headline": "Cached manual item",
                "summary": "Existing cached item",
            }
        ]
        fresh_rows = [
            {
                "id": "456",
                "brief_section": "UAE",
                "headline": "Fresh manual item",
                "summary": "New pending item",
            }
        ]

        cached_items = convert_to_gatekeeper_shape(cached_rows, "2026-03-25")
        fresh_items = convert_to_gatekeeper_shape(fresh_rows, "2026-03-25")

        self.assertEqual(cached_items[0]["id"], "2026-03-25-m123")
        self.assertEqual(fresh_items[0]["id"], "2026-03-25-m456")
        self.assertNotEqual(cached_items[0]["id"], fresh_items[0]["id"])
        self.assertEqual(fresh_items[0]["_manual_entry_id"], "456")

    def test_reconcile_final_brief_restores_missing_manual_entries(self):
        selected = [
            {
                "id": "2026-03-26-s001",
                "rank": 1,
                "headline": "Kept selected item",
                "source": "Reuters",
                "source_url": "https://example.com/kept",
                "brief_section": "UAE",
                "summary": "A kept selected item summary.",
                "composite_score": 8.2,
            },
            {
                "id": "2026-03-26-mabc123",
                "headline": "Manual: whitehouse.gov",
                "source": "Manual Entry",
                "source_url": "https://www.whitehouse.gov/example",
                "brief_section": "UAE",
                "summary": "",
                "composite_score": 8.0,
                "_manual_entry_id": "abc123",
                "enriched_sources": [
                    {
                        "url": "https://www.whitehouse.gov/example",
                        "extract": (
                            "President Trump appointed members to the President's Council "
                            "of Advisors on Science and Technology."
                        ),
                    }
                ],
            },
        ]
        source_lookup = orchestrator.build_source_metadata_lookup(selected)
        final_brief = {
            "brief_metadata": {
                "date": "2026-03-26",
                "generated_at": "2026-03-26T05:00:00+04:00",
                "total_items": 1,
                "section_counts": {"UAE": 1},
                "lead_story_id": "2026-03-26-s001",
            },
            "items": [
                {
                    "id": "2026-03-26-s001",
                    "rank": 1,
                    "section": "UAE",
                    "headline": "Kept selected item",
                    "source_domain": "example.com",
                    "source_name": "Reuters",
                    "source_url": "https://example.com/kept",
                    "additional_sources": [],
                    "main_bullet": "A kept selected item summary. [Source: https://example.com/kept]",
                    "context": None,
                    "implication": None,
                    "entities": [],
                    "composite_score": 8.2,
                    "significance_level": "high",
                    "cluster": None,
                    "continuity": None,
                    "is_model_release": False,
                    "model_release_data": None,
                    "depth": "full",
                }
            ],
        }
        edit_log: list[dict] = []

        restored_ids = orchestrator.reconcile_final_brief_with_selected(
            final_brief,
            selected,
            source_lookup,
            edit_log=edit_log,
        )
        orchestrator.apply_source_metadata(final_brief["items"], source_lookup)

        self.assertEqual(restored_ids, ["2026-03-26-mabc123"])
        restored_item = next(
            item for item in final_brief["items"] if item["id"] == "2026-03-26-mabc123"
        )
        self.assertEqual(restored_item["_manual_entry_id"], "abc123")
        self.assertEqual(restored_item["source_name"], "Manual Entry")
        self.assertIn("whitehouse.gov/example", restored_item["main_bullet"])
        self.assertEqual(orchestrator.extract_included_manual_entry_ids(final_brief["items"]), {"abc123"})
        self.assertEqual(
            orchestrator.manual_entry_ids_ready_to_mark({"abc123", "missing"}, final_brief["items"]),
            ["abc123"],
        )
        self.assertEqual(edit_log[0]["type"], "pipeline_recovery")


class ModelReleaseClassificationTests(unittest.TestCase):
    def test_research_publication_in_model_section_is_not_treated_as_model_release(self):
        item = {
            "headline": "Sakana AI's AI Scientist system published in Nature journal",
            "summary": (
                "Sakana AI's AI Scientist system was published in Nature — the first AI "
                "system to automate the full scientific research cycle to appear in a top-tier journal."
            ),
            "raw_content": (
                "Sakana AI's AI Scientist system was published in Nature. "
                "The work claims to demonstrate a scaling law of science."
            ),
            "brief_section": "Model Releases & Technical Developments",
            "entities": ["Sakana AI", "Nature"],
            "source": "AINews (Latent Space)",
            "source_url": "",
            "enriched_sources": [
                {"url": "https://sakana.ai/ai-scientist/", "title": "Sakana AI"},
                {"url": "https://arxiv.org/html/2502.14297", "title": "Evaluating Sakana's AI Scientist"},
            ],
        }

        self.assertFalse(is_probable_model_release(item))

    def test_usage_rankings_are_not_treated_as_model_releases(self):
        item = {
            "headline": "Chinese AI models dominate global token consumption for third consecutive week",
            "summary": "Chinese models surpassed US peers on OpenRouter for a third week.",
            "raw_content": (
                "Chinese large language models led by MiniMax M2.5 surpassed US competitors "
                "on OpenRouter for a third consecutive week, recording 7.36T tokens versus "
                "3.54T for US models."
            ),
            "brief_section": "Model Releases & Technical Developments",
            "entities": ["MiniMax M2.5", "DeepSeek V3.2", "Kimi K2.5", "OpenRouter"],
            "source": "FT Briefing",
            "source_url": "",
            "enriched_sources": [],
        }

        self.assertFalse(is_probable_model_release(item))

    def test_funding_story_about_future_model_is_not_treated_as_model_release(self):
        item = {
            "headline": "Nvidia-backed Reflection raises $2.5B to build US open-weight frontier model",
            "summary": "Reflection is raising $2.5 billion to build a US open-weight frontier model.",
            "raw_content": (
                "Reflection, a startup creating freely available US AI systems, is raising "
                "$2.5 billion at a $25 billion valuation."
            ),
            "brief_section": "International Business & Technology",
            "entities": ["Reflection", "Nvidia", "DeepSeek"],
            "source": "TLDR AI",
            "source_url": "",
            "enriched_sources": [],
        }

        self.assertFalse(is_probable_model_release(item))

    def test_research_domain_model_release_without_developer_surface_is_not_treated_as_model_release(self):
        item = {
            "headline": "Meta FAIR releases TRIBE v2, a trimodal foundation model for brain activity prediction",
            "summary": (
                "Meta FAIR released TRIBE v2, a trimodal foundation model trained on fMRI "
                "data and released with weights and code."
            ),
            "raw_content": (
                "Meta FAIR released TRIBE v2, a trimodal foundation model trained on "
                "1,117 hours of fMRI data across 720 subjects. Weights and code are "
                "publicly released. It ranked first on Algonauts 2025."
            ),
            "brief_section": "Model Releases & Technical Developments",
            "entities": ["Meta FAIR", "TRIBE v2", "Algonauts"],
            "source": "Manual Entry",
            "source_url": "https://github.com/facebookresearch/tribev2",
            "enriched_sources": [
                {"url": "https://github.com/facebookresearch/tribev2", "title": "GitHub"},
                {"url": "https://huggingface.co/facebook/tribev2", "title": "Hugging Face"},
            ],
        }

        self.assertFalse(is_probable_model_release(item))

    def test_real_model_launch_still_qualifies_as_model_release(self):
        item = {
            "headline": "OpenAI releases GPT-5.4 mini and nano in the API",
            "summary": "OpenAI launched GPT-5.4 mini and nano with API availability and pricing.",
            "raw_content": (
                "OpenAI released GPT-5.4 mini and nano in the API with pricing, benchmark "
                "results, and availability details in the model card."
            ),
            "brief_section": "Model Releases & Technical Developments",
            "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
            "source": "OpenAI",
            "source_url": "https://openai.com/index/gpt-5-4-mini-nano/",
            "enriched_sources": [
                {"url": "https://openai.com/index/gpt-5-4-mini-nano/", "title": "OpenAI release"},
                {"url": "https://platform.openai.com/docs/models", "title": "Model card"},
            ],
        }

        self.assertTrue(is_probable_model_release(item))

    def test_anthropic_api_launch_still_qualifies_as_model_release(self):
        item = {
            "headline": "Anthropic launches Claude Sonnet 5 in the API and Claude app",
            "summary": (
                "Anthropic launched Claude Sonnet 5 with API docs, model card details, "
                "pricing, and availability in the Claude app."
            ),
            "raw_content": (
                "Anthropic launched Claude Sonnet 5 in the API and Claude app. "
                "The release includes pricing, documentation, a model card, "
                "and benchmark results for coding and reasoning."
            ),
            "brief_section": "Model Releases & Technical Developments",
            "entities": ["Anthropic", "Claude Sonnet 5"],
            "source": "Anthropic",
            "source_url": "https://www.anthropic.com/news/claude-sonnet-5",
            "enriched_sources": [
                {"url": "https://www.anthropic.com/news/claude-sonnet-5", "title": "Anthropic launch"},
                {"url": "https://docs.anthropic.com/en/docs/about-claude/models", "title": "API docs"},
            ],
        }

        self.assertTrue(is_probable_model_release(item))

    def test_google_vertex_launch_still_qualifies_as_model_release(self):
        item = {
            "headline": "Google releases Gemini 3.0 Flash on Vertex AI",
            "summary": (
                "Google released Gemini 3.0 Flash with Vertex AI availability, "
                "pricing guidance, and developer documentation."
            ),
            "raw_content": (
                "Google released Gemini 3.0 Flash on Vertex AI and ai.google.dev. "
                "The launch includes API access, documentation, pricing, "
                "context window details, and benchmark results."
            ),
            "brief_section": "Model Releases & Technical Developments",
            "entities": ["Google", "Gemini 3.0 Flash", "Vertex AI"],
            "source": "Google",
            "source_url": "https://ai.google.dev/gemini-api/docs/models/gemini-3.0-flash",
            "enriched_sources": [
                {"url": "https://ai.google.dev/gemini-api/docs/models/gemini-3.0-flash", "title": "Google AI docs"},
                {"url": "https://cloud.google.com/vertex-ai/generative-ai/docs/models", "title": "Vertex AI docs"},
            ],
        }

        self.assertTrue(is_probable_model_release(item))


class ModelReleaseResolverTests(unittest.TestCase):
    def test_ambiguous_model_release_uses_haiku_resolver(self):
        item = {
            "headline": "Mistral releases Devstral Small open weights on Hugging Face",
            "summary": "Mistral released Devstral Small as open weights on Hugging Face.",
            "raw_content": (
                "Mistral released Devstral Small as open weights on Hugging Face with "
                "a technical report, but no deployable product surface was included."
            ),
            "brief_section": "Model Releases & Technical Developments",
            "entities": ["Mistral", "Devstral Small"],
            "source": "Mistral",
            "source_url": "https://huggingface.co/mistralai/devstral-small",
            "enriched_sources": [
                {
                    "url": "https://huggingface.co/mistralai/devstral-small",
                    "title": "Hugging Face",
                }
            ],
        }

        async def fake_resolver(_client, _item, _signals):
            return True, {
                "decision_source": "haiku",
                "confidence": 0.91,
                "reason": "Open-weight release is the primary event.",
            }

        with patch.object(enricher, "_resolve_ambiguous_model_release_with_haiku", fake_resolver):
            result = asyncio.run(enricher._finalize_model_release_flag(item, client=object()))

        self.assertTrue(result)
        self.assertTrue(item["is_model_release"])
        self.assertEqual(item["_model_release_classifier"]["heuristic_decision"], "ambiguous")
        self.assertEqual(item["_model_release_classifier"]["decision_source"], "haiku")


if __name__ == "__main__":
    unittest.main()
