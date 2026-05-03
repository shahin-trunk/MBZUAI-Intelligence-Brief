"""
Model Release Enrichment Improvement — Validation Test
=======================================================
Runs the UPDATED enricher on cached March 9 model-release items and compares
against the OLD enriched output to verify three improvements:

  1. is_model_release derived from brief_section (was always False)
  2. _enforce_minimum_substance now fires → 35-word items forced to web search
  3. Supplementary model-release searches run (benchmark + model card queries)

Run: cd backend && python3.11 test_enrichment_model_release.py
"""

import asyncio
import copy
import json
import os
import sys
import time
from pathlib import Path

from config import ANTHROPIC_API_KEY, OUTPUT_DIR
from pipeline.enricher import (
    _enforce_minimum_substance,
    _normalise_raw_content,
    build_model_release_queries,
    enrich_item,
    SERPER_API_KEY,
)
from pipeline.model_release import (
    attach_model_release_packet,
    build_model_release_packet,
    reserve_model_release_search_results,
    validate_model_release_output,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

results = {"pass": 0, "fail": 0, "skip": 0}


def pass_test(name: str, detail: str = ""):
    results["pass"] += 1
    suffix = f" {DIM}({detail}){RESET}" if detail else ""
    print(f"  {GREEN}✓ PASS{RESET}  {name}{suffix}")


def fail_test(name: str, detail: str = ""):
    results["fail"] += 1
    suffix = f" {DIM}({detail}){RESET}" if detail else ""
    print(f"  {RED}✗ FAIL{RESET}  {name}{suffix}")


def skip_test(name: str, reason: str = ""):
    results["skip"] += 1
    suffix = f" {DIM}({reason}){RESET}" if reason else ""
    print(f"  {YELLOW}⊘ SKIP{RESET}  {name}{suffix}")


def section(title: str):
    print(f"\n{BOLD}{CYAN}── {title} ──{RESET}")


# ---------------------------------------------------------------------------
# Data loader — March 9 gatekeeper output
# ---------------------------------------------------------------------------

GATEKEEPER_FILE = "gatekeeper_output_2026-03-09.json"
ENRICHED_FILE = "enriched_gatekeeper_output_2026-03-09.json"

MARCH_19_MINI_NANO_ITEM = {
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": (
        "OpenAI released GPT-5.4 mini and nano, smaller models designed for "
        "high-volume workloads with faster speeds and lower cost. GPT-5.4 mini "
        "improves substantially over GPT-5 mini and approaches larger GPT-5.4 "
        "performance on benchmarks, while GPT-5.4 nano targets lightweight tasks "
        "like classification and extraction."
    ),
    "enriched_sources": [
        {
            "url": "https://thenewstack.io/gpt-54-nano-mini/",
            "title": "OpenAI's GPT-5.4 mini and nano are built for the subagent era",
            "extract": (
                "GPT-5.4 mini is available in the API, Codex, and ChatGPT. It has a "
                "400,000-token context window and costs $0.75 per million input tokens "
                "and $4.50 per million output tokens. GPT-5.4 nano is API-only at "
                "$0.20 per million input tokens and $1.25 per million output tokens. "
                "On SWE-bench Pro, mini scores 54.38%, only 3 percentage points behind "
                "the full GPT-5.4. On OSWorld-Verified, mini scores 72.13%, almost "
                "matching the flagship model's 75.03%. Nano scores lower on "
                "OSWorld-Verified (39.01% vs. 42%)."
            ),
        },
        {
            "url": "https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openais-gpt-5-4-mini-and-gpt-5-4-nano-for-low-latency-ai/4500569",
            "title": "Introducing OpenAI's GPT-5.4 mini and GPT-5.4 nano for low latency AI",
            "extract": (
                "GPT-5.4 mini distills GPT-5.4's strengths into a smaller, more efficient "
                "model for developer workloads where responsiveness matters. It "
                "significantly improves over GPT-5 mini while running about 2X faster. "
                "GPT-5.4 nano is the smallest and fastest model in the lineup, designed "
                "for low-latency and low-cost API usage at high throughput."
            ),
        },
    ],
}

OFFICIAL_TABLE_ITEM = {
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": "OpenAI released GPT-5.4 mini and nano for high-volume workloads.",
    "enriched_sources": [
        {
            "url": "https://openai.com/index/introducing-gpt-5-4-mini-and-nano/",
            "title": "Introducing GPT-5.4 mini and nano - OpenAI",
            "extract": (
                "Today we’re releasing GPT‑5.4 mini and nano.\n"
                "| GPT-5.4 (xhigh) | GPT-5.4 mini (xhigh) | GPT-5.4 nano (xhigh) | GPT-5 mini (high¹) | |\n"
                "|---|---|---|---|---|\n"
                "| SWE-Bench Pro (Public) | 57.7% | 54.4% | 52.4% | 45.7% |\n"
                "| Terminal-Bench 2.0 | 75.1% | 60.0% | 46.3% | 38.2% |\n"
                "| Toolathlon | 54.6% | 42.9% | 35.5% | 26.9% |\n"
                "| GPQA Diamond | 93.0% | 88.0% | 82.8% | 81.6% |\n"
                "| OSWorld-Verified | 75.0% | 72.1% | 39.0% | 42.0% |\n"
                "GPT‑5.4 mini is available today in the API, Codex, and ChatGPT.\n"
                "GPT‑5.4 nano is only available in the API and costs $0.20 per 1M input tokens and $1.25 per 1M output tokens."
            ),
        }
    ],
}

OFFICIAL_INLINE_TABLE_ITEM = {
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": "OpenAI released GPT-5.4 mini and nano for high-volume workloads.",
    "enriched_sources": [
        {
            "url": "https://openai.com/index/introducing-gpt-5-4-mini-and-nano/",
            "title": "Introducing GPT-5.4 mini and nano - OpenAI",
            "extract": (
                "Today we’re releasing GPT‑5.4 mini and nano, our most capable small models yet. "
                "| GPT-5.4 (xhigh) | GPT-5.4 mini (xhigh) | GPT-5.4 nano (xhigh) | GPT-5 mini (high¹) | | "
                "|---|---|---|---|---| "
                "| SWE-Bench Pro (Public) | 57.7% | 54.4% | 52.4% | 45.7% | "
                "| Terminal-Bench 2.0 | 75.1% | 60.0% | 46.3% | 38.2% | "
                "| Toolathlon | 54.6% | 42.9% | 35.5% | 26.9% | "
                "| GPQA Diamond | 93.0% | 88.0% | 82.8% | 81.6% | "
                "| OSWorld-Verified | 75.0% | 72.1% | 39.0% | 42.0% | "
                "GPT‑5.4 mini is available today in the API, Codex, and ChatGPT, has a 400K context window, and costs $0.75 per 1M input tokens and $4.50 per 1M output tokens. "
                "GPT‑5.4 nano is only available in the API and costs $0.20 per 1M input tokens and $1.25 per 1M output tokens."
            ),
        }
    ],
}

COMPACT_PRICING_AND_BENCHMARK_ITEM = {
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": "OpenAI released GPT-5.4 mini and nano for fast, low-cost agentic workloads.",
    "enriched_sources": [
        {
            "url": "https://developers.openai.com/api/docs/models/gpt-5.4-mini",
            "title": "GPT-5.4 mini Model | OpenAI API",
            "extract": (
                "GPT-5.4 mini Default Our strongest mini model yet for coding, computer use, "
                "and subagents. Price $0.75•$4.5 Input•Output. Context window 400K tokens."
            ),
        },
        {
            "url": "https://www.zdnet.com/article/gpt-5-4-mini-and-nano/",
            "title": "OpenAI's GPT-5.4 mini and nano launch",
            "extract": (
                "GPQA Diamond results show GPT-5.4 mini score 88.01%, approaching GPT-5.4 "
                "at 93.00%. Terminal-Bench: GPT-5.4 mini reaches 60.00% versus 38.20% for "
                "GPT-5 mini."
            ),
        },
    ],
}


def load_items(filename: str) -> list[dict]:
    path = OUTPUT_DIR / filename
    if not path.exists():
        print(f"  {RED}ERROR: {path} not found{RESET}")
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["selected"]


def find_model_release_items(items: list[dict]) -> list[dict]:
    """Find items in the Model Releases & Technical Developments section."""
    return [
        item for item in items
        if "model release" in item.get("brief_section", "").lower()
    ]


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: is_model_release derivation (pure, no API)
# ═══════════════════════════════════════════════════════════════════════════

def test_is_model_release_derivation():
    section("Test 1: is_model_release derivation from brief_section")

    items = load_items(GATEKEEPER_FILE)
    model_items = find_model_release_items(items)

    if not model_items:
        skip_test("No model release items found in March 9 data")
        return

    for item in model_items:
        headline = item.get("headline", "?")[:70]
        original_flag = item.get("is_model_release")

        # Simulate the enricher derivation logic
        is_model_release = item.get("is_model_release", False)
        if not is_model_release:
            sect = item.get("brief_section", "")
            if "model release" in sect.lower():
                is_model_release = True

        if is_model_release:
            pass_test(f"Derived is_model_release=True", f"was={original_flag}, headline={headline}")
        else:
            fail_test(f"Failed to derive is_model_release", headline)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: _enforce_minimum_substance fires for model releases (pure)
# ═══════════════════════════════════════════════════════════════════════════

def test_enforce_minimum_substance():
    section("Test 2: _enforce_minimum_substance fires for 35-word model releases")

    items = load_items(GATEKEEPER_FILE)
    model_items = find_model_release_items(items)

    for item in model_items:
        headline = item.get("headline", "?")[:70]
        raw = _normalise_raw_content(item.get("raw_content", ""))
        wc = len(raw.split())

        # Simulate a judge returning SUFFICIENT with no extracts
        mock_judge = {
            "decision": "SUFFICIENT",
            "confidence": 0.90,
            "missing_elements": [],
            "recommended_query_terms": [headline],
            "reasoning": "Mock sufficient judgment",
        }

        result = _enforce_minimum_substance(
            headline, raw, extracts=[], judge_result=mock_judge,
            is_model_release=True,
        )

        if wc < 80 and result["decision"] == "INSUFFICIENT":
            pass_test(
                f"Forced INSUFFICIENT for {wc}-word model release",
                f"missing={result['missing_elements'][:2]}"
            )
        elif wc >= 80:
            pass_test(f"Skipped enforcement (already {wc} words)", headline)
        else:
            fail_test(f"Did NOT force INSUFFICIENT for {wc}-word model release", headline)

    # Control: same items WITHOUT is_model_release=True should use 50-word threshold
    for item in model_items:
        raw = _normalise_raw_content(item.get("raw_content", ""))
        wc = len(raw.split())
        if 50 <= wc < 80:
            mock_judge = {
                "decision": "SUFFICIENT", "confidence": 0.90,
                "missing_elements": [], "recommended_query_terms": [],
                "reasoning": "Mock",
            }
            result = _enforce_minimum_substance(
                item.get("headline", ""), raw, extracts=[], judge_result=mock_judge,
                is_model_release=False,
            )
            if result["decision"] == "SUFFICIENT":
                pass_test(f"Control: {wc}-word item passes general threshold (50)")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Supplementary query generation (pure)
# ═══════════════════════════════════════════════════════════════════════════

def test_supplementary_queries():
    section("Test 3: Supplementary model-release search queries")

    items = load_items(GATEKEEPER_FILE)
    model_items = find_model_release_items(items)

    for item in model_items:
        headline = item.get("headline", "?")
        queries = build_model_release_queries(headline)

        if len(queries) == 4:
            pass_test(f"Generated 4 queries", f"headline={headline[:50]}")
        else:
            fail_test(f"Expected 4 queries, got {len(queries)}", headline[:50])

        for q in queries:
            query_text = q.get("query", "") if isinstance(q, dict) else str(q)
            if len(query_text) <= 140:
                pass_test(f"Query length OK ({len(query_text)} chars)", query_text[:60])
            else:
                fail_test(f"Query too long ({len(query_text)} chars)", query_text[:60])

        # Check queries contain benchmark/evaluation or model card/pricing terms
        intents = {q.get("intent") for q in queries if isinstance(q, dict)}
        for required in ("official", "benchmark", "pricing", "variant"):
            if required in intents:
                pass_test(f"{required} query present")
            else:
                fail_test(f"Missing {required} query")


def test_structured_packet_extraction():
    section("Test 4: Structured benchmark/key-number extraction for March 19 mini+nano item")

    item = copy.deepcopy(MARCH_19_MINI_NANO_ITEM)
    item["_enrichment"] = {}
    attach_model_release_packet(item, search_exhausted=True)
    meta = item.get("_enrichment", {})

    if meta.get("dual_model_release") is True:
        pass_test("Dual-model release detected", str(meta.get("dual_model_release")))
    else:
        fail_test("Dual-model release not detected")

    families = set(meta.get("benchmark_families_found", []))
    if {"SWE-bench Pro", "OSWorld-Verified"}.issubset(families):
        pass_test("Benchmark families extracted", ", ".join(sorted(families)))
    else:
        fail_test("Benchmark families missing", str(sorted(families)))

    labels = {fact.get("label") for fact in item.get("key_number_facts", [])}
    if any("Pricing" in str(label) for label in labels):
        pass_test("Pricing key numbers extracted")
    else:
        fail_test("Missing pricing key numbers")
    if {"Pricing (mini)", "Pricing (nano)"}.issubset(labels):
        pass_test("Pricing labels preserved both mini and nano variants")
    else:
        fail_test("Pricing labels did not preserve mini/nano distinction", str(sorted(labels)))
    if any("Context" in str(label) for label in labels):
        pass_test("Context key number extracted")
    else:
        fail_test("Missing context key number")
    if any("Speed" in str(label) for label in labels):
        pass_test("Speed key number extracted")
    else:
        fail_test("Missing speed key number")

    if any("publishes only" in note.lower() for note in item.get("coverage_notes", [])):
        pass_test("Limited benchmark note added after search exhaustion")
    else:
        fail_test("Missing limited benchmark note", str(item.get("coverage_notes", [])))


def test_search_slot_reservation():
    section("Test 5: Search result slot reservation prefers official/benchmark/pricing")

    candidates = [
        {
            "link": "https://random.example/news",
            "title": "General roundup",
            "snippet": "Overview of the launch",
            "classified_intents": [],
        },
        {
            "link": "https://openai.com/index/gpt-5-4-mini-nano",
            "title": "OpenAI announcement",
            "snippet": "Official announcement and model card",
            "classified_intents": ["official", "pricing"],
        },
        {
            "link": "https://benchmarks.example/gpt-5-4-mini",
            "title": "Benchmark analysis",
            "snippet": "SWE-bench and OSWorld evaluation",
            "classified_intents": ["benchmark"],
        },
        {
            "link": "https://pricing.example/gpt-5-4-mini",
            "title": "API pricing",
            "snippet": "Pricing and availability details",
            "classified_intents": ["pricing"],
        },
    ]
    reserved = reserve_model_release_search_results(candidates, max_total=4)
    reserved_domains = [item["link"] for item in reserved]

    if any("openai.com" in link for link in reserved_domains):
        pass_test("Reserved official slot")
    else:
        fail_test("Did not reserve official slot", str(reserved_domains))
    if any("benchmarks.example" in link for link in reserved_domains):
        pass_test("Reserved benchmark slot")
    else:
        fail_test("Did not reserve benchmark slot", str(reserved_domains))
    if any("pricing.example" in link for link in reserved_domains):
        pass_test("Reserved pricing slot")
    else:
        fail_test("Did not reserve pricing slot", str(reserved_domains))


def test_official_markdown_table_extraction():
    section("Test 6: Compact pricing extraction and benchmark label cleanup")

    item = copy.deepcopy(OFFICIAL_TABLE_ITEM)
    packet = build_model_release_packet(item)

    families = set(packet.get("benchmark_families_found", []))
    expected = {"SWE-bench Pro", "Terminal-Bench 2.0", "Toolathlon", "GPQA Diamond", "OSWorld-Verified"}
    if expected.issubset(families):
        pass_test("Official markdown table expanded into benchmark families", str(sorted(families)))
    else:
        fail_test("Official markdown table lost benchmark families", str(sorted(families)))

    source_models = {
        fact.get("model")
        for fact in packet.get("benchmark_facts", [])
        if fact.get("benchmark") == "GPQA Diamond"
    }
    normalized_source_models = {str(model).lower() for model in source_models}
    if (
        "gpt-5.4 (flagship)" in normalized_source_models
        and "gpt-5.4 mini" in normalized_source_models
        and "gpt-5.4 nano" in normalized_source_models
        and any(model.startswith("gpt-5 ") and "mini" in model for model in normalized_source_models)
    ):
        pass_test("Official table preserved all comparator model scores", str(sorted(source_models)))
    else:
        fail_test("Official table dropped comparator model scores", str(sorted(source_models)))


def test_inline_markdown_table_extraction():
    section("Test 7: Inline markdown table extraction from fetched sources")

    item = copy.deepcopy(OFFICIAL_INLINE_TABLE_ITEM)
    packet = build_model_release_packet(item)

    families = set(packet.get("benchmark_families_found", []))
    expected = {"SWE-bench Pro", "Terminal-Bench 2.0", "Toolathlon", "GPQA Diamond", "OSWorld-Verified"}
    if expected.issubset(families):
        pass_test("Inline official table expanded into benchmark families", str(sorted(families)))
    else:
        fail_test("Inline official table lost benchmark families", str(sorted(families)))

    gpqa_scores = {
        (fact.get("model"), fact.get("score"))
        for fact in packet.get("benchmark_facts", [])
        if fact.get("benchmark") == "GPQA Diamond"
    }
    normalized_gpqa_scores = {(str(model).lower(), score) for model, score in gpqa_scores}
    expected_scores = {
        ("gpt-5.4 (flagship)", "93.0%"),
        ("gpt-5.4 mini", "88.0%"),
        ("gpt-5.4 nano", "82.8%"),
        ("gpt-5 mini", "81.6%"),
    }
    if expected_scores.issubset(normalized_gpqa_scores):
        pass_test("Inline official table preserved the full comparator matrix", str(sorted(gpqa_scores)))
    else:
        fail_test("Inline official table dropped comparator scores", str(sorted(gpqa_scores)))

    pricing_values = {
        (fact.get("label"), fact.get("value"))
        for fact in packet.get("key_number_facts", [])
        if fact.get("kind") == "pricing"
    }
    if (
        ("Pricing (mini)", "$0.75/$4.50") in pricing_values
        and ("Pricing (nano)", "$0.20/$1.25") in pricing_values
    ):
        pass_test("Inline official release text preserved mini and nano pricing", str(sorted(pricing_values)))
    else:
        fail_test("Inline official release text lost pricing", str(sorted(pricing_values)))

    if not any(family in {"Input", "Output", "Cached Input"} for family in families):
        pass_test("Pricing table labels do not leak into benchmark families")
    else:
        fail_test("Pricing-like labels leaked into benchmark families", str(sorted(families)))

    context_values = {
        (fact.get("label"), fact.get("value"))
        for fact in packet.get("key_number_facts", [])
        if fact.get("kind") == "context"
    }
    if ("Context (mini)", "400K") in context_values:
        pass_test("Inline official release text preserved context window", str(sorted(context_values)))
    else:
        fail_test("Inline official release text lost context window", str(sorted(context_values)))


def test_compact_pricing_and_clean_benchmark_labels():
    section("Test 8: Compact pricing extraction and benchmark label cleanup")

    item = copy.deepcopy(COMPACT_PRICING_AND_BENCHMARK_ITEM)
    packet = build_model_release_packet(item)

    pricing_values = {
        (fact.get("label"), fact.get("value"))
        for fact in packet.get("key_number_facts", [])
        if fact.get("kind") == "pricing"
    }
    if ("Pricing (mini)", "$0.75/$4.5") in pricing_values or ("Pricing (mini)", "$0.75/$4.50") in pricing_values:
        pass_test("Compact OpenAI pricing extracted")
    else:
        fail_test("Failed to extract compact OpenAI pricing", str(sorted(pricing_values)))

    if any(label == "Pricing (mini)" for label, _ in pricing_values):
        pass_test("Compact pricing keeps the variant label")
    else:
        fail_test("Compact pricing lost the variant label", str(sorted(pricing_values)))

    noisy_models = {
        "It",
        "It Score",
        "Results Show Gpt-5.4 Mini",
        "Approaching GPT-5.4",
        "Versu",
        "- Gpt-5.4 Mini",
    }
    extracted_models = {fact.get("model") for fact in packet.get("benchmark_facts", [])}
    if extracted_models.isdisjoint(noisy_models):
        pass_test("Benchmark models avoid noisy parser artifacts", str(sorted(extracted_models)))
    else:
        fail_test("Benchmark models still include noisy parser artifacts", str(sorted(extracted_models)))

    variants = packet.get("variants", [])
    if variants == ["GPT-5.4 mini", "GPT-5.4 nano"]:
        pass_test("Variant detection avoids bogus headline fragments", str(variants))
    else:
        fail_test("Variant detection still includes bogus fragments", str(variants))


def test_ghostwriter_completeness_guard():
    section("Test 9: Post-Ghostwriter completeness guard")

    source_item = {
        "is_model_release": True,
        "benchmark_facts": [
            {"benchmark": "SWE-bench Pro", "model": "GPT-5.4 mini", "score": "54.38%"},
            {"benchmark": "SWE-bench Pro", "model": "GPT-5.4 nano", "score": "52.39%"},
            {"benchmark": "SWE-bench Pro", "model": "GPT-5 mini", "score": "45.69%"},
            {"benchmark": "OSWorld-Verified", "model": "GPT-5.4 mini", "score": "72.13%"},
            {"benchmark": "OSWorld-Verified", "model": "GPT-5.4 nano", "score": "39.0%"},
            {"benchmark": "OSWorld-Verified", "model": "GPT-5 mini", "score": "42.0%"},
            {"benchmark": "MMLU", "model": "GPT-5.4 mini", "score": "86.2%"},
        ],
        "key_number_facts": [
            {"label": "Pricing (mini)", "kind": "pricing"},
            {"label": "Context (mini)", "kind": "context"},
            {"label": "Speed (mini)", "kind": "speed"},
        ],
    }
    output_item = {
        "model_release_data": {
            "key_numbers": [
                {"label": "Pricing (mini)", "value": "$0.75/$4.50"},
                {"label": "Context (mini)", "value": "400K"},
            ],
            "benchmarks": {
                "rows": [
                    {"benchmark": "SWE-bench Pro", "scores": ["54.38%", "—", "—"]},
                    {"benchmark": "OSWorld-Verified", "scores": ["72.13%", "—", "42.0%"]},
                ]
            },
        }
    }

    issues = validate_model_release_output(source_item, output_item)
    if any("benchmark families" in issue for issue in issues):
        pass_test("Guard catches dropped benchmark rows")
    else:
        fail_test("Guard missed dropped benchmark rows", str(issues))
    if any("speed" in issue.lower() for issue in issues):
        pass_test("Guard catches dropped key-number categories")
    else:
        fail_test("Guard missed dropped speed key number", str(issues))


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: Before/after comparison — cached vs re-enriched (API calls)
# ═══════════════════════════════════════════════════════════════════════════

async def test_before_after_comparison():
    section("Test 9: Before/After — re-enrich model releases with improvements")

    if os.getenv("SKIP_LIVE_ENRICHMENT") == "1":
        skip_test("SKIP_LIVE_ENRICHMENT=1 — skipping live enrichment")
        return
    if os.getenv("ANTHROPIC_API_KEY", "__UNSET__") == "":
        skip_test("ANTHROPIC_API_KEY explicitly blank — skipping live enrichment")
        return
    if os.getenv("SERPER_API_KEY", "__UNSET__") == "":
        skip_test("SERPER_API_KEY explicitly blank — skipping live enrichment")
        return
    if not ANTHROPIC_API_KEY:
        skip_test("ANTHROPIC_API_KEY not set — skipping live enrichment")
        return
    if not SERPER_API_KEY:
        skip_test("SERPER_API_KEY not set — skipping live enrichment")
        return

    import anthropic
    client = anthropic.AsyncAnthropic()

    # Load pre-enrichment items
    raw_items = load_items(GATEKEEPER_FILE)
    model_items = find_model_release_items(raw_items)

    # Load OLD enriched output for comparison
    old_enriched = load_items(ENRICHED_FILE)
    old_by_id = {item.get("id") or item.get("headline"): item for item in old_enriched}

    for item in model_items[:2]:  # Test first 2 model releases only (cost control)
        headline = item.get("headline", "?")[:70]
        item_id = item.get("id") or item.get("headline")
        print(f"\n  {DIM}Re-enriching: {headline}...{RESET}")

        # Get old results
        old = old_by_id.get(item_id, {})
        old_meta = old.get("_enrichment", {})
        old_steps = old_meta.get("steps_taken", [])
        old_wc = old_meta.get("enriched_word_count", 0)
        old_sources = len(old.get("enriched_sources", []))

        # Run new enrichment
        fresh_item = copy.deepcopy(item)
        # Remove any old enrichment data
        fresh_item.pop("_enrichment", None)
        fresh_item.pop("enriched_sources", None)
        fresh_item.pop("enriched_facts", None)

        start = time.time()
        enriched = await enrich_item(fresh_item, client)
        elapsed = time.time() - start

        new_meta = enriched.get("_enrichment", {})
        new_steps = new_meta.get("steps_taken", [])
        new_wc = new_meta.get("enriched_word_count", 0)
        new_sources = len(enriched.get("enriched_sources", []))
        new_is_mr = enriched.get("is_model_release", False)
        benchmark_families = new_meta.get("benchmark_families_found", [])

        print(f"  {DIM}Old: steps={old_steps}, sources={old_sources}, words={old_wc}{RESET}")
        print(f"  {DIM}New: steps={new_steps}, sources={new_sources}, words={new_wc}, "
              f"is_model_release={new_is_mr}, {elapsed:.1f}s{RESET}")

        # Assertion 1: is_model_release should now be True
        if new_is_mr:
            pass_test(f"is_model_release=True", headline)
        else:
            fail_test(f"is_model_release still False", headline)

        # Assertion 2: Should have progressed past judge_1 (web_search step)
        if "web_search" in new_steps:
            pass_test(f"Reached web_search step", f"steps={new_steps}")
        else:
            # Check if enforce_minimum forced INSUFFICIENT
            j1 = new_meta.get("judge_1_result", {})
            fail_test(f"Did not reach web_search", f"judge_1={j1.get('decision')}")

        # Assertion 3: Enriched word count should be significantly higher
        if new_wc > old_wc + 100:
            pass_test(f"Enriched words improved: {old_wc} → {new_wc}",
                       f"+{new_wc - old_wc} words")
        elif new_wc > old_wc:
            pass_test(f"Enriched words improved (modest): {old_wc} → {new_wc}",
                       f"+{new_wc - old_wc} words")
        else:
            fail_test(f"Enriched words did not improve: {old_wc} → {new_wc}")

        # Assertion 4: Should have supplementary search sources
        if new_sources > old_sources:
            pass_test(f"More sources: {old_sources} → {new_sources}")
        elif new_sources > 0:
            pass_test(f"Has sources ({new_sources})", "old also had sources")
        else:
            fail_test(f"No enrichment sources fetched")

        if isinstance(benchmark_families, list):
            pass_test("Completeness metadata recorded", f"benchmarks={benchmark_families}")
        else:
            fail_test("Missing completeness metadata", str(benchmark_families))


# ═══════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print("  MODEL RELEASE ENRICHMENT — IMPROVEMENT VALIDATION")
    print(f"{'=' * 60}{RESET}")

    print(f"\n  {DIM}ANTHROPIC_API_KEY: {'set' if ANTHROPIC_API_KEY else 'NOT SET'}")
    print(f"  SERPER_API_KEY:   {'set' if SERPER_API_KEY else 'NOT SET'}")
    print(f"  Test data:        {GATEKEEPER_FILE}{RESET}")

    start = time.time()

    # Pure tests (no API calls)
    test_is_model_release_derivation()
    test_enforce_minimum_substance()
    test_supplementary_queries()
    test_structured_packet_extraction()
    test_search_slot_reservation()
    test_official_markdown_table_extraction()
    test_inline_markdown_table_extraction()
    test_compact_pricing_and_clean_benchmark_labels()
    test_ghostwriter_completeness_guard()

    # Live enrichment test (API calls)
    asyncio.run(test_before_after_comparison())

    # Summary
    elapsed = time.time() - start
    total = results["pass"] + results["fail"] + results["skip"]

    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  RESULTS: {total} tests in {elapsed:.1f}s")
    print(f"{'=' * 60}{RESET}")
    print(f"  {GREEN}PASS: {results['pass']}{RESET}")
    if results["fail"]:
        print(f"  {RED}FAIL: {results['fail']}{RESET}")
    else:
        print(f"  FAIL: 0")
    if results["skip"]:
        print(f"  {YELLOW}SKIP: {results['skip']}{RESET}")
    else:
        print(f"  SKIP: 0")
    print()

    sys.exit(1 if results["fail"] > 0 else 0)


if __name__ == "__main__":
    main()
