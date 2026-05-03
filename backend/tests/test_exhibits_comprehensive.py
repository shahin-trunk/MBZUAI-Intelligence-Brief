"""
Comprehensive Exhibit & Model Release Pipeline Test Suite
=========================================================

Run:
  cd backend
  pytest tests/test_exhibits_comprehensive.py -m tier1 -v      # pure, no API
  pytest tests/test_exhibits_comprehensive.py -m llm -v        # LLM integration
  pytest tests/test_exhibits_comprehensive.py -m e2e -v        # end-to-end
  pytest tests/test_exhibits_comprehensive.py -v               # everything
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
from pathlib import Path

import pytest

# Ensure backend root is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.model_release import (
    attach_model_release_packet,
    build_model_release_packet,
    build_model_release_queries,
    canonicalise_benchmark_name,
    classify_model_release_heuristics,
    classify_model_release_result,
    detect_model_release_variants,
    extract_benchmark_table_facts,
    extract_coverage_notes,
    extract_key_number_facts,
    infer_model_family_root,
    is_possible_model_release,
    is_probable_model_release,
    reserve_model_release_search_results,
    validate_model_release_output,
    BENCHMARK_ALIASES,
    NOISY_MODEL_LABELS,
)
from pipeline.enricher import (
    _enforce_minimum_substance,
    _normalise_raw_content,
)
from pipeline.editor import repair_truncated_json_object
from pipeline.json_utils import safe_parse_json
from models.schemas import (
    BenchmarkData,
    ExhibitData,
    GhostwriterItem,
    GhostwriterOutput,
    ModelReleaseData,
)

from tests.conftest import (
    all_cached_brief_dates,
    find_model_release_items,
    load_brief,
    load_brief_items,
    load_gatekeeper_items,
    skip_no_anthropic,
    skip_no_serper,
    OUTPUT_DIR,
)
from tests.dummy_data import (
    AMBIGUOUS_FUNDING_PLUS_LAUNCH,
    AMBIGUOUS_OPEN_WEIGHT,
    BACKEND_BENCHMARK_TABLE,
    CLEAR_LAUNCH_GOOGLE,
    CLEAR_LAUNCH_OPENAI,
    ENRICHED_MINI_NANO_ITEM,
    FRONTEND_BENCHMARK_TABLE,
    GHOSTWRITER_OUTPUT_WITH_EXHIBITS,
    ITEM_COMPACT_PRICING,
    ITEM_CONTEXT_WINDOW,
    ITEM_COVERAGE_API_ONLY,
    ITEM_COVERAGE_NOT_DISCLOSED,
    ITEM_DIRECT_PRICING,
    ITEM_LONG_FORM_PRICING,
    ITEM_NO_TABLE,
    ITEM_NOISY_LABELS,
    ITEM_SPEED,
    ITEM_WITH_INLINE_TABLE,
    ITEM_WITH_STANDARD_TABLE,
    NON_LAUNCH_FUNDING,
    NON_LAUNCH_MARKET,
    NON_LAUNCH_RESEARCH,
    SEARCH_CANDIDATES,
    TRUNCATED_JSON_MID_EXHIBIT,
    TRUNCATED_JSON_MID_ITEMS,
    VALIDATION_COMPLETE_OUTPUT,
    VALIDATION_INCOMPLETE_OUTPUT,
    VALIDATION_SOURCE_ITEM,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 1: Pure Unit Tests (no API calls)
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassifyHeuristics:
    """T1.1-T1.3: Model release heuristic classification."""

    @pytest.mark.tier1
    @pytest.mark.parametrize("item", [CLEAR_LAUNCH_OPENAI, CLEAR_LAUNCH_GOOGLE])
    def test_true_for_clear_launches(self, item):
        decision, signals = classify_model_release_heuristics(item)
        assert decision is True, f"Expected True for: {item['headline']}"
        assert is_probable_model_release(item)

    @pytest.mark.tier1
    def test_true_detects_official_source(self):
        decision, signals = classify_model_release_heuristics(CLEAR_LAUNCH_OPENAI)
        assert signals["has_official_source"] is True

    @pytest.mark.tier1
    @pytest.mark.parametrize(
        "item",
        [NON_LAUNCH_FUNDING, NON_LAUNCH_RESEARCH, NON_LAUNCH_MARKET],
        ids=["funding", "research", "market"],
    )
    def test_false_for_non_launches(self, item):
        decision, signals = classify_model_release_heuristics(item)
        assert decision is False, f"Expected False for: {item['headline']}"
        assert not is_probable_model_release(item)

    @pytest.mark.tier1
    def test_false_for_ai_infrastructure_buildout(self):
        item = {
            "headline": "DIEZ, VOLT UAE team up to develop AI-ready data centres in Dubai Silicon Oasis",
            "summary": (
                "The Dubai Integrated Economic Zones Authority announced a joint venture "
                "with VOLT UAE to develop an advanced AI-ready data centre."
            ),
            "raw_content": (
                "The partnership will see the development of an advanced, AI-ready data centre "
                "in Dubai Silicon Oasis. Spanning up to 60,000 square metres, the development "
                "will be implemented in two phases: an initial 29 MW capacity followed by "
                "100 MW of committed power. VOLT addresses this with a full-stack AI compute "
                "platform designed to support sovereign AI capabilities, enabling organisations "
                "to develop, train, and deploy AI securely."
            ),
            "entities": ["DIEZ", "VOLT UAE", "Dubai Integrated Economic Zones Authority"],
            "brief_section": "UAE",
            "source": "WAM",
        }
        decision, signals = classify_model_release_heuristics(item)
        assert decision is False
        assert signals["has_infrastructure_build_cue"] is True
        assert not is_possible_model_release(item)

    @pytest.mark.tier1
    @pytest.mark.parametrize(
        "item",
        [AMBIGUOUS_OPEN_WEIGHT, AMBIGUOUS_FUNDING_PLUS_LAUNCH],
        ids=["open_weight", "funding_plus_launch"],
    )
    def test_none_for_ambiguous(self, item):
        decision, signals = classify_model_release_heuristics(item)
        assert decision is None, f"Expected None for: {item['headline']}"
        assert is_possible_model_release(item)
        assert not is_probable_model_release(item)


class TestDetectVariants:
    """T1.4-T1.5: Variant name extraction."""

    @pytest.mark.tier1
    def test_multi_variant(self):
        variants = detect_model_release_variants(
            "OpenAI releases GPT-5.4 mini and nano",
            entities=["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
            raw_content="GPT-5.4 mini and GPT-5.4 nano released.",
        )
        lower_variants = [v.lower() for v in variants]
        assert "gpt-5.4 mini" in lower_variants
        assert "gpt-5.4 nano" in lower_variants

    @pytest.mark.tier1
    def test_single_variant(self):
        variants = detect_model_release_variants(
            "Anthropic launches Claude 4 Sonnet",
            entities=["Anthropic", "Claude 4 Sonnet"],
        )
        lower_variants = [v.lower() for v in variants]
        assert "claude 4 sonnet" in lower_variants

    @pytest.mark.tier1
    def test_no_variant_terms(self):
        variants = detect_model_release_variants(
            "Google announces Gemini 3",
            entities=["Google", "Gemini 3"],
        )
        assert variants == []

    @pytest.mark.tier1
    def test_no_and_prefix_artifacts(self):
        variants = detect_model_release_variants(
            "OpenAI releases GPT-5.4 mini and nano",
            entities=["OpenAI"],
            raw_content="Released GPT-5.4 mini and GPT-5.4 nano.",
        )
        for v in variants:
            assert not v.lower().startswith("and ")

    @pytest.mark.tier1
    def test_infer_family_root_multi(self):
        root = infer_model_family_root(["GPT-5.4 mini", "GPT-5.4 nano"])
        assert root == "GPT-5.4"

    @pytest.mark.tier1
    def test_infer_family_root_single(self):
        root = infer_model_family_root(["Claude 4 Sonnet"])
        assert root == "Claude 4"

    @pytest.mark.tier1
    def test_infer_family_root_empty(self):
        assert infer_model_family_root([]) is None


class TestExtractBenchmarkTableFacts:
    """T1.6-T1.9: Benchmark table extraction."""

    @pytest.mark.tier1
    def test_standard_markdown_table(self):
        facts = extract_benchmark_table_facts(ITEM_WITH_STANDARD_TABLE)
        assert len(facts) >= 4, f"Expected >=4 facts, got {len(facts)}"
        benchmarks = {f["benchmark"] for f in facts}
        assert "SWE-bench Pro" in benchmarks
        assert "GPQA Diamond" in benchmarks
        models = {f["model"].lower() for f in facts}
        assert any("mini" in m for m in models)

    @pytest.mark.tier1
    def test_inline_markdown_table(self):
        facts = extract_benchmark_table_facts(ITEM_WITH_INLINE_TABLE)
        families = {f["benchmark"] for f in facts}
        assert len(families) >= 4, f"Expected >=4 benchmark families, got {sorted(families)}"

    @pytest.mark.tier1
    def test_no_table_returns_empty(self):
        facts = extract_benchmark_table_facts(ITEM_NO_TABLE)
        assert facts == []

    @pytest.mark.tier1
    def test_noisy_model_labels_filtered(self):
        packet = build_model_release_packet(ITEM_NOISY_LABELS)
        models = {f.get("model", "").lower() for f in packet.get("benchmark_facts", [])}
        for noisy in NOISY_MODEL_LABELS:
            assert noisy.lower() not in models, f"Noisy label leaked: {noisy}"


class TestExtractKeyNumberFacts:
    """T1.10-T1.12: Key number extraction."""

    @pytest.mark.tier1
    def test_direct_pricing(self):
        facts = extract_key_number_facts(ITEM_DIRECT_PRICING)
        pricing = [f for f in facts if f.get("kind") == "pricing"]
        assert pricing, "No pricing fact extracted from direct $X/$Y format"

    @pytest.mark.tier1
    def test_compact_pricing(self):
        facts = extract_key_number_facts(ITEM_COMPACT_PRICING)
        pricing = [f for f in facts if f.get("kind") == "pricing"]
        assert pricing, "No pricing fact extracted from compact $X\u2022$Y format"

    @pytest.mark.tier1
    def test_long_form_pricing(self):
        facts = extract_key_number_facts(ITEM_LONG_FORM_PRICING)
        pricing = [f for f in facts if f.get("kind") == "pricing"]
        assert pricing, "No pricing fact extracted from long-form per-1M format"

    @pytest.mark.tier1
    def test_context_window(self):
        facts = extract_key_number_facts(ITEM_CONTEXT_WINDOW)
        context = [f for f in facts if f.get("kind") == "context"]
        assert context, "No context window fact extracted"

    @pytest.mark.tier1
    def test_speed(self):
        facts = extract_key_number_facts(ITEM_SPEED)
        speed = [f for f in facts if f.get("kind") == "speed"]
        assert speed, "No speed fact extracted from '2X faster' pattern"


class TestCoverageNotes:
    """T1.13: Coverage note detection."""

    @pytest.mark.tier1
    def test_not_disclosed(self):
        notes = extract_coverage_notes(ITEM_COVERAGE_NOT_DISCLOSED)
        combined = " ".join(notes).lower()
        assert "pricing not disclosed" in combined

    @pytest.mark.tier1
    def test_api_only(self):
        notes = extract_coverage_notes(ITEM_COVERAGE_API_ONLY)
        combined = " ".join(notes).lower()
        assert "api-only" in combined


class TestPacketAssembly:
    """T1.14-T1.15: Packet building, deduplication, attachment."""

    @pytest.mark.tier1
    def test_packet_aggregation_dedup(self):
        item = copy.deepcopy(ENRICHED_MINI_NANO_ITEM)
        # Pre-seed with a duplicate fact
        item["benchmark_facts"] = [
            {"benchmark": "SWE-bench Pro", "model": "GPT-5.4 mini", "score": "54.38%", "source_url": ""},
        ]
        packet = build_model_release_packet(item)
        bf = packet["benchmark_facts"]
        # Check dedup: only one SWE-bench Pro / GPT-5.4 mini entry per source_url
        swe_mini = [f for f in bf if f["benchmark"] == "SWE-bench Pro" and "mini" in f["model"].lower()]
        urls = [f["source_url"] for f in swe_mini]
        assert len(urls) == len(set((f["benchmark"], f["model"], f["score"], f["source_url"]) for f in swe_mini))

    @pytest.mark.tier1
    def test_dual_model_release_detection(self):
        item = copy.deepcopy(ENRICHED_MINI_NANO_ITEM)
        item["_enrichment"] = {}
        attach_model_release_packet(item, search_exhausted=True)
        assert item["_enrichment"].get("dual_model_release") is True


class TestValidation:
    """T1.16-T1.17: Post-ghostwriter completeness guard."""

    @pytest.mark.tier1
    def test_catches_dropped_benchmarks_and_speed(self):
        issues = validate_model_release_output(VALIDATION_SOURCE_ITEM, VALIDATION_INCOMPLETE_OUTPUT)
        combined = " ".join(issues).lower()
        assert "benchmark families" in combined, f"Should catch dropped benchmarks: {issues}"
        assert "speed" in combined, f"Should catch dropped speed: {issues}"

    @pytest.mark.tier1
    def test_passes_on_complete_output(self):
        issues = validate_model_release_output(VALIDATION_SOURCE_ITEM, VALIDATION_COMPLETE_OUTPUT)
        assert issues == [], f"Expected no issues for complete output: {issues}"


class TestEnforceMinimumSubstance:
    """T1.18: Minimum substance enforcement."""

    @pytest.mark.tier1
    def test_model_release_35_word_forced_insufficient(self):
        short_content = " ".join(["word"] * 35)
        judge = {
            "decision": "SUFFICIENT",
            "confidence": 0.9,
            "missing_elements": [],
            "recommended_query_terms": ["test"],
            "reasoning": "Mock",
        }
        result = _enforce_minimum_substance(
            "Test headline", short_content, extracts=[], judge_result=judge, is_model_release=True,
        )
        assert result["decision"] == "INSUFFICIENT"

    @pytest.mark.tier1
    def test_general_60_word_passes(self):
        medium_content = " ".join(["word"] * 60)
        judge = {
            "decision": "SUFFICIENT",
            "confidence": 0.9,
            "missing_elements": [],
            "recommended_query_terms": [],
            "reasoning": "Mock",
        }
        result = _enforce_minimum_substance(
            "Test headline", medium_content, extracts=[], judge_result=judge, is_model_release=False,
        )
        assert result["decision"] == "SUFFICIENT"

    @pytest.mark.tier1
    def test_model_release_100_word_passes(self):
        long_content = " ".join(["word"] * 100)
        judge = {
            "decision": "SUFFICIENT",
            "confidence": 0.9,
            "missing_elements": [],
            "recommended_query_terms": [],
            "reasoning": "Mock",
        }
        result = _enforce_minimum_substance(
            "Test headline", long_content, extracts=[], judge_result=judge, is_model_release=True,
        )
        assert result["decision"] == "SUFFICIENT"


class TestQueryGeneration:
    """T1.19: Supplementary query generation."""

    @pytest.mark.tier1
    def test_four_queries_with_all_intents(self):
        queries = build_model_release_queries(
            "OpenAI releases GPT-5.4 mini and nano",
            entities=["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
        )
        assert len(queries) == 4
        intents = {q["intent"] for q in queries}
        assert intents == {"official", "benchmark", "pricing", "variant"}

    @pytest.mark.tier1
    def test_query_length_limit(self):
        queries = build_model_release_queries(
            "A very long headline about some new model " * 5,
            entities=[],
        )
        for q in queries:
            assert len(q["query"]) <= 200, f"Query too long: {q['query']}"

    @pytest.mark.tier1
    def test_variant_query_contains_vs(self):
        queries = build_model_release_queries(
            "OpenAI releases GPT-5.4 mini and nano",
            entities=["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
        )
        variant_q = next(q for q in queries if q["intent"] == "variant")
        assert "vs" in variant_q["query"].lower()


class TestSearchSlotReservation:
    """T1.20: Search result slot prioritization."""

    @pytest.mark.tier1
    def test_official_benchmark_pricing_reserved_first(self):
        reserved = reserve_model_release_search_results(SEARCH_CANDIDATES, max_total=4)
        domains = [r["link"] for r in reserved]
        assert any("openai.com" in d for d in domains), "Official slot missing"
        assert any("benchmarks.example" in d for d in domains), "Benchmark slot missing"
        assert any("pricing.example" in d for d in domains), "Pricing slot missing"

    @pytest.mark.tier1
    def test_max_total_respected(self):
        reserved = reserve_model_release_search_results(SEARCH_CANDIDATES, max_total=3)
        assert len(reserved) <= 3


class TestClassifyResult:
    """T1.21: Intent classification for search results."""

    @pytest.mark.tier1
    def test_official_domain(self):
        intents = classify_model_release_result("https://openai.com/blog/gpt-6")
        assert "official" in intents

    @pytest.mark.tier1
    def test_benchmark_keywords(self):
        intents = classify_model_release_result(
            "https://example.com/eval", title="SWE-bench evaluation results",
        )
        assert "benchmark" in intents

    @pytest.mark.tier1
    def test_pricing_keywords(self):
        intents = classify_model_release_result(
            "https://example.com/pricing", snippet="API pricing and availability",
        )
        assert "pricing" in intents


class TestEditorTruncationRepair:
    """T1.21-T1.22: Editor JSON truncation repair."""

    @pytest.mark.tier1
    def test_repair_truncated_mid_items(self):
        repaired = repair_truncated_json_object(TRUNCATED_JSON_MID_ITEMS)
        assert repaired is not None
        assert "final_brief" in repaired
        items = repaired["final_brief"]["items"]
        assert len(items) >= 1
        # First item should have exhibits intact
        first = items[0]
        assert first.get("exhibits") is not None
        assert len(first["exhibits"]) == 1
        assert first["exhibits"][0]["type"] == "benchmark_table"

    @pytest.mark.tier1
    def test_repair_truncated_mid_exhibit(self):
        repaired = repair_truncated_json_object(TRUNCATED_JSON_MID_EXHIBIT)
        assert repaired is not None
        assert "final_brief" in repaired


class TestBenchmarkCanonicalisation:
    """T1.25: Benchmark alias resolution."""

    @pytest.mark.tier1
    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("swe-bench pro", "SWE-bench Pro"),
            ("swe bench pro", "SWE-bench Pro"),
            ("GPQA Diamond", "GPQA Diamond"),
            ("gpqa diamond", "GPQA Diamond"),
            ("terminal-bench 2.0", "Terminal-Bench 2.0"),
            ("osworld-verified", "OSWorld-Verified"),
            ("mmlu", "MMLU"),
        ],
    )
    def test_alias_resolution(self, input_name, expected):
        assert canonicalise_benchmark_name(input_name) == expected


class TestFormatMismatch:
    """T1.23: Documents the critical backend/frontend benchmark table format mismatch."""

    @pytest.mark.tier1
    def test_backend_scores_array_lookup_fails(self):
        """Backend format uses scores as positional array — dict-style lookup fails."""
        row = BACKEND_BENCHMARK_TABLE["data"]["rows"][0]
        models = BACKEND_BENCHMARK_TABLE["data"]["models"]
        # The frontend ExhibitRenderer does: row.scores?.[col]
        # On an array, string key lookup returns None/undefined
        scores = row["scores"]
        assert isinstance(scores, list), "Backend scores should be a list"
        with pytest.raises((TypeError, KeyError)):
            _ = scores[models[0]]  # This fails — the bug

    @pytest.mark.tier1
    def test_frontend_scores_dict_lookup_works(self):
        """Frontend extraction API format uses scores as dict — lookup works."""
        row = FRONTEND_BENCHMARK_TABLE["data"]["rows"][0]
        columns = FRONTEND_BENCHMARK_TABLE["data"]["columns"]
        scores = row["scores"]
        assert isinstance(scores, dict), "Frontend scores should be a dict"
        assert scores[columns[0]] == "90%"


class TestPydanticRoundtrip:
    """T1.24: Schema validation preserves exhibits."""

    @pytest.mark.tier1
    def test_ghostwriter_output_preserves_exhibits(self):
        output = GhostwriterOutput.model_validate(GHOSTWRITER_OUTPUT_WITH_EXHIBITS)
        dumped = output.model_dump()
        item = dumped["items"][0]
        assert len(item["exhibits"]) == 1
        assert item["exhibits"][0]["type"] == "benchmark_table"
        assert item["is_model_release"] is True
        assert item["model_release_data"]["developer"] == "OpenAI"
        assert len(item["model_release_data"]["benchmarks"]["rows"]) == 2

    @pytest.mark.tier1
    def test_exhibit_data_accepts_any_type_string(self):
        """ExhibitData.type is str, not Literal — any string passes."""
        exhibit = ExhibitData(type="custom_chart", data={"x": 1})
        assert exhibit.type == "custom_chart"


class TestJsonUtils:
    """T1.25b: safe_parse_json edge cases."""

    @pytest.mark.tier1
    def test_markdown_fenced_json(self):
        result = safe_parse_json('```json\n{"type": "benchmark_table"}\n```')
        assert result["type"] == "benchmark_table"

    @pytest.mark.tier1
    def test_plain_json(self):
        result = safe_parse_json('{"type": "benchmark_table"}')
        assert result["type"] == "benchmark_table"


class TestCachedBriefIntegrity:
    """T1.26-T1.28: Audit all cached brief files for exhibit/model-release integrity."""

    @pytest.mark.tier1
    def test_all_exhibits_have_valid_structure(self):
        valid_types = {"benchmark_table", "comparison_table", "metric_highlight", "timeline", "raw_image"}
        dates = all_cached_brief_dates()
        if not dates:
            pytest.skip("No cached brief files found in backend/output/")

        issues = []
        total_exhibits = 0
        for date in dates:
            brief = load_brief(date)
            items = brief.get("items", [])
            for item in items:
                for i, exhibit in enumerate(item.get("exhibits") or []):
                    total_exhibits += 1
                    if exhibit is None:
                        issues.append(f"{date}/{item.get('id')}: exhibit[{i}] is None")
                        continue
                    if exhibit.get("type") not in valid_types:
                        issues.append(f"{date}/{item.get('id')}: unknown type '{exhibit.get('type')}'")
                    if not isinstance(exhibit.get("data"), dict):
                        issues.append(f"{date}/{item.get('id')}: data is not a dict")

        print(f"\nAudited {total_exhibits} exhibits across {len(dates)} briefs")
        assert not issues, f"Exhibit structure issues:\n" + "\n".join(issues)

    @pytest.mark.tier1
    def test_all_model_release_data_valid(self):
        dates = all_cached_brief_dates()
        if not dates:
            pytest.skip("No cached brief files found in backend/output/")

        issues = []
        total_mr = 0
        for date in dates:
            items = load_brief_items(date)
            for item in items:
                if not item.get("is_model_release"):
                    continue
                total_mr += 1
                mrd = item.get("model_release_data")
                item_id = item.get("id", "?")
                if mrd is None:
                    issues.append(f"{date}/{item_id}: is_model_release=True but model_release_data is None")
                    continue
                if not mrd.get("developer"):
                    issues.append(f"{date}/{item_id}: empty developer")
                if not mrd.get("model_name"):
                    issues.append(f"{date}/{item_id}: empty model_name")
                benchmarks = mrd.get("benchmarks")
                if benchmarks:
                    if not isinstance(benchmarks.get("rows"), list):
                        issues.append(f"{date}/{item_id}: benchmarks.rows is not a list")
                    if not isinstance(benchmarks.get("models"), list):
                        issues.append(f"{date}/{item_id}: benchmarks.models is not a list")

        print(f"\nAudited {total_mr} model release items across {len(dates)} briefs")
        assert not issues, f"Model release data issues:\n" + "\n".join(issues)

    @pytest.mark.tier1
    def test_benchmark_tables_frontend_compat(self):
        """Count how many pipeline benchmark_tables use array scores vs dict scores."""
        dates = all_cached_brief_dates()
        if not dates:
            pytest.skip("No cached brief files found in backend/output/")

        array_count = 0
        dict_count = 0
        total = 0
        for date in dates:
            items = load_brief_items(date)
            for item in items:
                for exhibit in item.get("exhibits") or []:
                    if exhibit.get("type") != "benchmark_table":
                        continue
                    total += 1
                    rows = exhibit.get("data", {}).get("rows", [])
                    for row in rows:
                        scores = row.get("scores")
                        if isinstance(scores, list):
                            array_count += 1
                            break
                        elif isinstance(scores, dict):
                            dict_count += 1
                            break

        print(f"\nBenchmark table format audit:")
        print(f"  Total benchmark_table exhibits: {total}")
        print(f"  Array scores (backend format, broken on frontend): {array_count}")
        print(f"  Dict scores (frontend format, renders correctly): {dict_count}")
        # This test documents the mismatch; it doesn't fail — the fix is tracked separately
        if array_count > 0:
            print(f"  WARNING: {array_count} exhibits will render '—' for every cell")


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 2: LLM Integration Tests (API calls, dummy data)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHaikuModelReleaseClassifier:
    """T2.1-T2.3: Haiku tie-breaker for ambiguous model releases."""

    @pytest.mark.llm
    @skip_no_anthropic
    @pytest.mark.asyncio
    async def test_haiku_classifies_open_weight(self, anthropic_client):
        from pipeline.enricher import _resolve_ambiguous_model_release_with_haiku
        from pipeline.model_release import get_model_release_heuristic_signals

        signals = get_model_release_heuristic_signals(AMBIGUOUS_OPEN_WEIGHT)
        decision, meta = await _resolve_ambiguous_model_release_with_haiku(
            anthropic_client, AMBIGUOUS_OPEN_WEIGHT, signals,
        )
        assert isinstance(decision, bool)
        assert "confidence" in meta
        assert isinstance(meta["confidence"], float)
        assert meta.get("decision_source") == "haiku"

    @pytest.mark.llm
    @skip_no_anthropic
    @pytest.mark.asyncio
    async def test_haiku_approves_clear_launch(self, anthropic_client):
        from pipeline.enricher import _resolve_ambiguous_model_release_with_haiku
        from pipeline.model_release import get_model_release_heuristic_signals

        signals = get_model_release_heuristic_signals(CLEAR_LAUNCH_OPENAI)
        decision, meta = await _resolve_ambiguous_model_release_with_haiku(
            anthropic_client, CLEAR_LAUNCH_OPENAI, signals,
        )
        assert decision is True, f"Haiku should approve clear launch, got {decision}: {meta}"
        assert meta.get("confidence", 0) > 0.3

    @pytest.mark.llm
    @skip_no_anthropic
    @pytest.mark.asyncio
    async def test_haiku_rejects_funding_round(self, anthropic_client):
        from pipeline.enricher import _resolve_ambiguous_model_release_with_haiku
        from pipeline.model_release import get_model_release_heuristic_signals

        signals = get_model_release_heuristic_signals(NON_LAUNCH_FUNDING)
        decision, meta = await _resolve_ambiguous_model_release_with_haiku(
            anthropic_client, NON_LAUNCH_FUNDING, signals,
        )
        assert decision is False, f"Haiku should reject funding round, got {decision}: {meta}"


class TestFinalizeModelReleaseFlag:
    """T2.4: Full finalize flow with Haiku tie-breaker."""

    @pytest.mark.llm
    @skip_no_anthropic
    @pytest.mark.asyncio
    async def test_finalize_ambiguous_item(self, anthropic_client):
        from pipeline.enricher import _finalize_model_release_flag

        item = copy.deepcopy(AMBIGUOUS_OPEN_WEIGHT)
        await _finalize_model_release_flag(item, anthropic_client)

        meta = item.get("_model_release_classifier", {})
        assert meta.get("finalized") is True
        assert meta.get("heuristic_decision") == "ambiguous"
        assert meta.get("decision_source") == "haiku"
        assert isinstance(item.get("is_model_release"), bool)


class TestLLMNormalizer:
    """T2.5-T2.6: Last-mile LLM normalization for benchmark extraction."""

    @pytest.mark.llm
    @skip_no_anthropic
    @pytest.mark.asyncio
    async def test_extracts_benchmarks_from_prose(self, anthropic_client):
        from pipeline.enricher import _maybe_normalise_model_release_packet_with_llm

        # Craft an item where regex extraction fails but benchmarks are mentioned
        # (no "scored X%" or "X% on Y" patterns, benchmarks in non-standard phrasing)
        item = {
            "headline": "OpenAI releases GPT-6",
            "entities": ["OpenAI", "GPT-6"],
            "is_model_release": True,
            "raw_content": "",
            "benchmark_facts": [],
            "key_number_facts": [],
            "enriched_sources": [
                {
                    "url": "https://example.com",
                    "title": "GPT-6 review",
                    "extract": (
                        "GPT-6 evaluation results: GPQA Diamond performance is listed "
                        "as ninety-six point two percent, with the prior model at ninety-three percent. "
                        "The SWE-bench Pro result is sixty-two point one percent."
                    ),
                }
            ],
        }
        await _maybe_normalise_model_release_packet_with_llm(
            anthropic_client, item["headline"], item,
        )
        # The LLM normalizer should extract facts from the written-out percentages
        assert len(item["benchmark_facts"]) > 0, "LLM normalizer should have extracted benchmark facts from prose"

    @pytest.mark.llm
    @skip_no_anthropic
    @pytest.mark.asyncio
    async def test_skips_when_regex_found_facts(self, anthropic_client):
        from pipeline.enricher import _maybe_normalise_model_release_packet_with_llm

        item = copy.deepcopy(ENRICHED_MINI_NANO_ITEM)
        # Build packet so benchmark_facts are populated by regex
        packet = build_model_release_packet(item)
        item["benchmark_facts"] = packet["benchmark_facts"]
        item["key_number_facts"] = packet["key_number_facts"]

        original_facts = copy.deepcopy(item["benchmark_facts"])
        await _maybe_normalise_model_release_packet_with_llm(
            anthropic_client, item["headline"], item,
        )
        # Facts should remain unchanged (no LLM call needed)
        assert item["benchmark_facts"] == original_facts


class TestGhostwriterExhibitGeneration:
    """T2.7: Ghostwriter produces exhibits for model releases."""

    @pytest.mark.llm
    @skip_no_anthropic
    @pytest.mark.asyncio
    async def test_ghostwriter_produces_model_release_exhibits(self, anthropic_client):
        from pipeline.ghostwriter import run_ghostwriter
        from prompts.loader import extract_prompt_from_md
        from config import PROMPTS_DIR

        # Model-release items route to the dedicated model_release_card
        # prompt (the main ghostwriter prompt explicitly declines them).
        prompt_template = extract_prompt_from_md(
            (PROMPTS_DIR / "model_release_card_prompt.md").read_text(encoding="utf-8")
        )

        # Build a minimal gatekeeper output for ghostwriter
        gatekeeper_item = copy.deepcopy(ENRICHED_MINI_NANO_ITEM)
        gatekeeper_item.update({
            "id": "test-001",
            "rank": 1,
            "source": "OpenAI",
            "source_url": "https://openai.com/gpt-5-4-mini",
            "date": "2026-04-13",
            "date_evidence": "Published April 13, 2026",
            "category": "model_release",
            "topic_relevance": 0.95,
            "news_significance": 0.92,
            "composite_score": 0.93,
            "selection_rationale": "Major model release",
        })
        packet = build_model_release_packet(gatekeeper_item)
        gatekeeper_item["benchmark_facts"] = packet["benchmark_facts"]
        gatekeeper_item["key_number_facts"] = packet["key_number_facts"]
        gatekeeper_item["coverage_notes"] = packet.get("coverage_notes", [])
        gatekeeper_item["compiled_packet"] = packet

        gatekeeper_output = {
            "selected": [gatekeeper_item],
            "dropped": [],
            "brief_summary": {
                "total_input_items": 1,
                "selected": 1,
                "dropped": 0,
                "section_distribution": {"Model Releases & Technical Developments": 1},
            },
        }

        prompt = prompt_template.replace("{gatekeeper_output}", json.dumps(gatekeeper_output, indent=2))
        prompt = prompt.replace("{date}", "2026-04-13")
        prompt = prompt.replace("{user_profile}", "Prof. Eric Xing, President of MBZUAI")
        prompt = prompt.replace("{previous_brief}", "No previous brief available.")

        result, usage = await run_ghostwriter(anthropic_client, prompt)
        items = result.get("items", [])
        assert len(items) >= 1, "Ghostwriter should produce at least 1 item"

        mr_items = [i for i in items if i.get("is_model_release")]
        assert mr_items, "At least one item should be is_model_release=True"

        item = mr_items[0]
        mrd = item.get("model_release_data")
        assert mrd is not None, "model_release_data should not be None"
        assert mrd.get("developer"), "developer should be non-empty"
        assert mrd.get("model_name"), "model_name should be non-empty"


class TestEditorExhibitPreservation:
    """T2.8-T2.9: Editor preserves exhibits from ghostwriter output."""

    @pytest.mark.llm
    @skip_no_anthropic
    @pytest.mark.asyncio
    async def test_editor_preserves_exhibits(self, anthropic_client):
        from pipeline.editor import run_editor
        from prompts.loader import extract_prompt_from_md
        from config import PROMPTS_DIR

        prompt_template = extract_prompt_from_md(
            (PROMPTS_DIR / "editor_prompt.md").read_text(encoding="utf-8")
        )

        ghostwriter_output = copy.deepcopy(GHOSTWRITER_OUTPUT_WITH_EXHIBITS)
        # Editor needs gatekeeper output too (for validation)
        gatekeeper_output = {
            "selected": [
                {
                    "id": "001",
                    "headline": "OpenAI launches GPT-6",
                    "rank": 1,
                    "brief_section": "Model Releases & Technical Developments",
                    "composite_score": 0.95,
                    "entities": ["OpenAI", "GPT-6"],
                    "source": "OpenAI",
                    "source_url": "https://openai.com/gpt-6",
                    "date": "2026-04-13",
                    "date_evidence": "April 13",
                    "summary": "GPT-6 released",
                    "raw_content": "OpenAI released GPT-6 with API access.",
                    "category": "model_release",
                    "topic_relevance": 0.95,
                    "news_significance": 0.92,
                    "selection_rationale": "Major release",
                }
            ],
            "dropped": [],
            "brief_summary": {
                "total_input_items": 1,
                "selected": 1,
                "dropped": 0,
                "section_distribution": {"Model Releases & Technical Developments": 1},
            },
        }

        prompt = prompt_template.replace(
            "{ghostwriter_output}", json.dumps(ghostwriter_output, indent=2),
        )
        prompt = prompt.replace(
            "{gatekeeper_output}", json.dumps(gatekeeper_output, indent=2),
        )
        prompt = prompt.replace("{date}", "2026-04-13")
        prompt = prompt.replace("{previous_brief}", "No previous brief available.")
        prompt = prompt.replace("{delivery_format}", "portal")

        result, usage = await run_editor(anthropic_client, prompt)
        final_items = result.get("final_brief", {}).get("items", [])
        assert len(final_items) >= 1

        mr_items = [i for i in final_items if i.get("is_model_release")]
        assert mr_items, "Editor should preserve is_model_release=True"
        mrd = mr_items[0].get("model_release_data")
        assert mrd is not None, "Editor should preserve model_release_data"


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 3: End-to-End Pipeline Tests (API calls, real cached data)
# ═══════════════════════════════════════════════════════════════════════════════


class TestReenrichCachedItems:
    """T3.1-T3.2: Re-enrich model release items from cached gatekeeper output."""

    @pytest.mark.e2e
    @skip_no_anthropic
    @skip_no_serper
    @pytest.mark.asyncio
    @pytest.mark.parametrize("date", ["2026-03-09", "2026-04-09"])
    async def test_reenrich_model_releases(self, anthropic_client, date):
        from pipeline.enricher import enrich_item

        gatekeeper_file = OUTPUT_DIR / f"gatekeeper_output_{date}.json"
        if not gatekeeper_file.exists():
            pytest.skip(f"Cached file not found: {gatekeeper_file}")

        items = load_gatekeeper_items(date)
        mr_items = find_model_release_items(items)
        if not mr_items:
            pytest.skip(f"No model release items in {date} gatekeeper output")

        # Test first item only (cost control)
        item = copy.deepcopy(mr_items[0])
        item.pop("_enrichment", None)
        item.pop("enriched_sources", None)
        item.pop("benchmark_facts", None)
        item.pop("key_number_facts", None)
        item.pop("coverage_notes", None)

        enriched = await enrich_item(item, anthropic_client)
        meta = enriched.get("_enrichment", {})

        assert enriched.get("is_model_release") is True, "Should be marked as model release"
        assert "web_search" in meta.get("steps_taken", []), f"Should reach web_search step: {meta.get('steps_taken')}"
        assert enriched.get("enriched_sources"), "Should have enrichment sources"

        # Check model release packet was built
        bf = enriched.get("benchmark_facts", [])
        knf = enriched.get("key_number_facts", [])
        print(f"\n  Date: {date}")
        print(f"  Headline: {enriched.get('headline', '')[:80]}")
        print(f"  Steps: {meta.get('steps_taken')}")
        print(f"  Benchmark facts: {len(bf)}")
        print(f"  Key number facts: {len(knf)}")
        print(f"  Benchmark families: {meta.get('benchmark_families_found', [])}")


class TestEnrichmentToPacketChain:
    """T3.3: Full enrichment → packet → completeness chain."""

    @pytest.mark.e2e
    @skip_no_anthropic
    @skip_no_serper
    @pytest.mark.asyncio
    async def test_enrichment_packet_completeness(self, anthropic_client):
        from pipeline.enricher import enrich_item
        from pipeline.model_release import summarise_model_release_completeness

        gatekeeper_file = OUTPUT_DIR / "gatekeeper_output_2026-03-09.json"
        if not gatekeeper_file.exists():
            pytest.skip("March 9 gatekeeper output not found")

        items = load_gatekeeper_items("2026-03-09")
        mr_items = find_model_release_items(items)
        if not mr_items:
            pytest.skip("No model release items in March 9 data")

        item = copy.deepcopy(mr_items[0])
        item.pop("_enrichment", None)
        item.pop("enriched_sources", None)
        item.pop("benchmark_facts", None)
        item.pop("key_number_facts", None)

        enriched = await enrich_item(item, anthropic_client)
        packet = build_model_release_packet(enriched)
        completeness = summarise_model_release_completeness(packet, search_exhausted=True)

        families = completeness.get("benchmark_families_found", [])
        print(f"\n  Completeness: {'COMPLETE' if completeness['complete'] else 'INCOMPLETE'}")
        print(f"  Benchmark families: {families}")
        print(f"  Official source: {completeness.get('official_source_found')}")
        print(f"  Pricing: {completeness.get('pricing_found')}")
        print(f"  Missing: {completeness.get('missing', [])}")

        # At minimum, enrichment should produce some structured data
        assert len(families) >= 1 or completeness.get("pricing_found"), \
            "Enrichment should extract at least one benchmark family or pricing"


class TestSupabaseExhibitConsistency:
    """T3.4: Verify exhibit data stored in Supabase matches expected schema."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_supabase_pending_items_exhibits(self):
        """Query pending_items with non-null exhibits and validate structure."""
        supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not service_key:
            pytest.skip("Supabase credentials not set")

        import httpx
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            # Query pending_items with exhibits
            resp = await client.get(
                f"{supabase_url}/rest/v1/pending_items",
                headers=headers,
                params={
                    "select": "id,headline,exhibits,model_release_data",
                    "exhibits": "not.is.null",
                    "limit": "50",
                },
            )
            if resp.status_code != 200:
                pytest.skip(f"Supabase query failed: {resp.status_code}")

            items = resp.json()
            if not items:
                pytest.skip("No pending_items with exhibits found")

            valid_types = {"benchmark_table", "comparison_table", "metric_highlight", "timeline", "raw_image"}
            issues = []
            for item in items:
                exhibits = item.get("exhibits") or []
                if not isinstance(exhibits, list):
                    issues.append(f"{item['id']}: exhibits is not a list")
                    continue
                for i, ex in enumerate(exhibits):
                    if not isinstance(ex, dict):
                        issues.append(f"{item['id']}/exhibit[{i}]: not a dict")
                        continue
                    if ex.get("type") not in valid_types:
                        issues.append(f"{item['id']}/exhibit[{i}]: unknown type '{ex.get('type')}'")
                    if not isinstance(ex.get("data"), dict):
                        issues.append(f"{item['id']}/exhibit[{i}]: data not a dict")

            print(f"\nValidated {len(items)} pending_items with exhibits")
            assert not issues, "Supabase exhibit schema issues:\n" + "\n".join(issues)
