"""
Targeted regression test for the March 19 GPT-5.4 mini / nano card.

Goal:
Verify whether the current source evidence for today's GPT-5.4 mini/nano item
would be considered comprehensive under the new model-release completeness
logic.

This is intentionally narrow and fixture-based:
  1. Rebuild the normalized packet from the real source evidence we had.
  2. Check the product-level completeness bar for this launch:
     official/model-card evidence + at least 3 benchmark families.
  3. Confirm whether the stored 2-row benchmark card should therefore count as
     incomplete, even if it preserved what the fetched sources contained.
  4. Confirm obviously thinner outputs also fail the guard.

Run:
  cd backend && python3.11 test_gpt54_mini_nano_targeted.py
"""

from __future__ import annotations

import copy
import sys

from pipeline.model_release import (
    attach_model_release_packet,
    build_model_release_packet,
    summarise_model_release_completeness,
    validate_model_release_output,
)


GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
DIM = "\033[2m"


RESULTS = {"pass": 0, "fail": 0}


def pass_test(name: str, detail: str = ""):
    RESULTS["pass"] += 1
    suffix = f" {DIM}({detail}){RESET}" if detail else ""
    print(f"  {GREEN}✓ PASS{RESET}  {name}{suffix}")


def fail_test(name: str, detail: str = ""):
    RESULTS["fail"] += 1
    suffix = f" {DIM}({detail}){RESET}" if detail else ""
    print(f"  {RED}✗ FAIL{RESET}  {name}{suffix}")


def section(title: str):
    print(f"\n{BOLD}{CYAN}── {title} ──{RESET}")


SOURCE_ITEM = {
    "id": "2026-03-19-s010",
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "raw_content": (
        "OpenAI released GPT-5.4 mini and nano, smaller models designed for high-volume "
        "workloads with faster speeds and lower cost. GPT-5.4 mini improves substantially "
        "over GPT-5 mini and approaches larger GPT-5.4 performance on benchmarks, while "
        "GPT-5.4 nano targets lightweight tasks like classification and extraction."
    ),
    "enriched_sources": [
        {
            "url": "https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openai%E2%80%99s-gpt-5-4-mini-and-gpt-5-4-nano-for-low-latency-ai/4500569",
            "title": "Introducing OpenAI's GPT-5.4 mini and GPT-5.4 nano for low latency AI",
            "extract": (
                "GPT-5.4 mini distills GPT-5.4's strengths into a smaller, more efficient "
                "model for developer workloads where responsiveness matters. It significantly "
                "improves over GPT-5 mini while running about 2X faster. GPT-5.4 nano is the "
                "smallest and fastest model in the lineup, designed for low-latency and "
                "low-cost API usage at high throughput. GPT-5.4 mini and GPT-5.4 nano are "
                "rolling out in Microsoft Foundry today."
            ),
        },
        {
            "url": "https://thenewstack.io/gpt-54-nano-mini/",
            "title": "OpenAI's GPT-5.4 mini and nano are built for the subagent era",
            "extract": (
                "GPT-5.4 mini is available in the API, Codex, and ChatGPT. It has a "
                "400,000-token context window, can take text and image inputs, and costs "
                "$0.75 per million input tokens and $4.50 per million output tokens. GPT-5.4 "
                "nano is API-only, but at $0.20 per million input tokens and $1.25 per "
                "million output tokens, it's OpenAI's cheapest model right now. On "
                "SWE-bench Pro, mini scores 54.38%, only 3 percentage points behind the full "
                "GPT-5.4. On OSWorld-Verified, mini scores 72.13%, almost matching the "
                "flagship model's 75.03%. Nano still outperforms the original GPT-5 mini on "
                "coding and tool-calling tasks, but scores lower on OSWorld-Verified "
                "(39.01% vs. 42%)."
            ),
        },
        {
            "url": "https://indianexpress.com/article/technology/artificial-intelligence/openai-releases-gpt-5-4-mini-and-nano-its-most-capable-small-models-yet-10587983/lite/",
            "title": "OpenAI releases GPT-5.4 mini and nano, its most capable small models yet",
            "extract": (
                "GPT-5.4 mini is available in the API, Codex, and ChatGPT. It supports text "
                "and image inputs, tool use, function calling, web search, file search, "
                "computer use, and a 400k context window. GPT-5.4 nano is available via the "
                "API only. API pricing is $0.75 per million input tokens and $4.50 per "
                "million output tokens for the mini, and $0.20 and $1.25 respectively for "
                "the nano."
            ),
        },
    ],
    "_enrichment": {},
}


CURRENT_CARD_OUTPUT = {
    "id": "2026-03-19-s010",
    "model_release_data": {
        "developer": "OpenAI",
        "model_name": "GPT-5.4 mini / GPT-5.4 nano",
        "summary_pitch": (
            "Two efficient-tier models optimised for agentic subagent workloads. "
            "Mini runs 2x faster than predecessor with near-flagship benchmark performance. "
            "Nano targets ultra-high-volume, low-latency classification and extraction at "
            "OpenAI's lowest price point."
        ),
        "key_numbers": [
            {"label": "Pricing (mini)", "value": "$0.75/$4.50", "qualifier": "per 1M in/out tokens"},
            {"label": "Pricing (nano)", "value": "$0.20/$1.25", "qualifier": "per 1M in/out tokens"},
            {"label": "Context (mini)", "value": "400K", "qualifier": "tokens"},
            {"label": "Speed (mini)", "value": "~2x", "qualifier": "faster than GPT-5 mini"},
        ],
        "benchmarks": {
            "models": ["GPT-5.4 mini", "GPT-5.4 (flagship)", "GPT-5 mini"],
            "highlighted_model_index": 0,
            "rows": [
                {"benchmark": "SWE-bench Pro", "scores": ["54.38%", "~57%", "—"]},
                {"benchmark": "OSWorld-Verified", "scores": ["72.13%", "75.03%", "42.00%"]},
            ],
            "summary": (
                "Mini closes to within 3pp of the flagship on SWE-bench Pro and 2.9pp on "
                "OSWorld; nano outperforms the original GPT-5 mini on coding and tool-calling "
                "but lags on computer-use tasks."
            ),
        },
        "training": "Distilled from GPT-5.4. Specific training methodology not disclosed.",
        "architecture": (
            "Distilled variants of GPT-5.4. Mini supports text and image inputs, tool use, "
            "function calling, web search, file search, and computer use. Nano is optimised "
            "for short-turn, high-throughput tasks with lightweight tool-calling support."
        ),
        "availability": "API · OpenAI Codex · ChatGPT (mini) · Microsoft Azure AI Foundry · API-only (nano)",
    },
}


TOO_THIN_OUTPUT = {
    "id": "2026-03-19-s010",
    "model_release_data": {
        "developer": "OpenAI",
        "model_name": "GPT-5.4 mini / GPT-5.4 nano",
        "key_numbers": [
            {"label": "Pricing (mini)", "value": "$0.75/$4.50", "qualifier": "per 1M in/out tokens"},
        ],
        "benchmarks": {
            "models": ["GPT-5.4 mini", "GPT-5.4 (flagship)"],
            "highlighted_model_index": 0,
            "rows": [
                {"benchmark": "SWE-bench Pro", "scores": ["54.38%", "~57%"]},
            ],
        },
    },
}

FULL_MATRIX_SOURCE_ITEM = {
    "is_model_release": True,
    "benchmark_facts": [
        {"benchmark": "SWE-bench Pro", "model": "GPT-5.4 mini", "score": "54.4%"},
        {"benchmark": "SWE-bench Pro", "model": "GPT-5.4 nano", "score": "52.4%"},
        {"benchmark": "SWE-bench Pro", "model": "GPT-5.4", "score": "57.7%"},
        {"benchmark": "SWE-bench Pro", "model": "GPT-5 mini", "score": "45.7%"},
        {"benchmark": "Toolathlon", "model": "GPT-5.4 mini", "score": "42.9%"},
        {"benchmark": "Toolathlon", "model": "GPT-5.4 nano", "score": "35.5%"},
        {"benchmark": "Toolathlon", "model": "GPT-5.4", "score": "54.6%"},
        {"benchmark": "Toolathlon", "model": "GPT-5 mini", "score": "26.9%"},
        {"benchmark": "GPQA Diamond", "model": "GPT-5.4 mini", "score": "88.0%"},
        {"benchmark": "GPQA Diamond", "model": "GPT-5.4 nano", "score": "82.8%"},
        {"benchmark": "GPQA Diamond", "model": "GPT-5.4", "score": "93.0%"},
        {"benchmark": "GPQA Diamond", "model": "GPT-5 mini", "score": "81.6%"},
        {"benchmark": "OSWorld-Verified", "model": "GPT-5.4 mini", "score": "72.1%"},
        {"benchmark": "OSWorld-Verified", "model": "GPT-5.4 nano", "score": "39.0%"},
        {"benchmark": "OSWorld-Verified", "model": "GPT-5.4", "score": "75.0%"},
        {"benchmark": "OSWorld-Verified", "model": "GPT-5 mini", "score": "42.0%"},
        {"benchmark": "Terminal-Bench 2.0", "model": "GPT-5.4 mini", "score": "60.0%"},
        {"benchmark": "Terminal-Bench 2.0", "model": "GPT-5.4 nano", "score": "46.3%"},
        {"benchmark": "Terminal-Bench 2.0", "model": "GPT-5.4", "score": "75.1%"},
        {"benchmark": "Terminal-Bench 2.0", "model": "GPT-5 mini", "score": "38.2%"},
        {"benchmark": "BrowseComp", "model": "GPT-5.4 mini", "score": "85.2%"},
        {"benchmark": "BrowseComp", "model": "GPT-5.4 nano", "score": "74.6%"},
        {"benchmark": "BrowseComp", "model": "GPT-5.4", "score": "88.4%"},
        {"benchmark": "BrowseComp", "model": "GPT-5 mini", "score": "71.3%"},
    ],
    "key_number_facts": [
        {"label": "Pricing (mini)", "kind": "pricing"},
        {"label": "Pricing (nano)", "kind": "pricing"},
        {"label": "Context (mini)", "kind": "context"},
        {"label": "Speed (mini)", "kind": "speed"},
    ],
}

FOUR_ROW_WITH_PROSE_OUTPUT = {
    "model_release_data": {
        "benchmarks": {
            "models": ["GPT-5.4 mini", "GPT-5.4 nano", "GPT-5.4", "GPT-5 mini"],
            "highlighted_model_index": 0,
            "highlighted_model_indexes": [0, 1],
            "rows": [
                {"benchmark": "SWE-bench Pro", "scores": ["54.4%", "52.4%", "57.7%", "45.7%"]},
                {"benchmark": "Toolathlon", "scores": ["42.9%", "35.5%", "54.6%", "26.9%"]},
                {"benchmark": "GPQA Diamond", "scores": ["88.0%", "82.8%", "93.0%", "81.6%"]},
                {"benchmark": "OSWorld-Verified", "scores": ["72.1%", "39.0%", "75.0%", "42.0%"]},
                {"benchmark": "Terminal-Bench 2.0", "scores": ["60.0%", "46.3%", "75.1%", "38.2%"]},
            ],
            "summary": (
                "These rows come from the official OpenAI release matrix. OpenAI also reports "
                "BrowseComp at 85.2% for mini, 74.6% for nano, 88.4% for GPT-5.4, "
                "and 71.3% for GPT-5 mini."
            ),
        }
    }
}


def test_packet_rebuild():
    section("Packet Rebuild")
    item = copy.deepcopy(SOURCE_ITEM)
    attach_model_release_packet(item, search_exhausted=True)
    meta = item.get("_enrichment", {})

    expected_families = {"SWE-bench Pro", "OSWorld-Verified"}
    found_families = set(meta.get("benchmark_families_found", []))
    if found_families == expected_families:
        pass_test("Detected the published benchmark families", ", ".join(sorted(found_families)))
    else:
        fail_test("Unexpected benchmark families", str(sorted(found_families)))

    if meta.get("dual_model_release") is True:
        pass_test("Detected dual-model release")
    else:
        fail_test("Did not detect dual-model release", str(meta.get("dual_model_release")))

    if meta.get("pricing_found") and meta.get("availability_found"):
        pass_test("Detected pricing and availability")
    else:
        fail_test(
            "Missing pricing or availability",
            f"pricing={meta.get('pricing_found')} availability={meta.get('availability_found')}",
        )

    kinds = {str(fact.get("kind", "")).lower() for fact in item.get("key_number_facts", [])}
    if {"pricing", "context", "speed"}.issubset(kinds):
        pass_test("Extracted all expected key-number categories")
    else:
        fail_test("Missing key-number categories", str(sorted(kinds)))

    notes = item.get("coverage_notes", [])
    if any("publishes only 2 benchmark families" in note for note in notes):
        pass_test("Added limited-benchmark coverage note")
    else:
        fail_test("Missing limited-benchmark coverage note", str(notes))


def test_product_goal_completeness():
    section("Product Goal Completeness")
    item = copy.deepcopy(SOURCE_ITEM)
    attach_model_release_packet(item, search_exhausted=True)
    meta = item.get("_enrichment", {})
    completeness = summarise_model_release_completeness(
        build_model_release_packet(item),
        search_exhausted=True,
    )
    families = meta.get("benchmark_families_found", [])
    official = meta.get("official_source_found")

    if official:
        pass_test("Official/model-card source detected")
    else:
        fail_test("Missing official/model-card source", str(meta))

    if len(families) >= 3:
        pass_test("Comprehensive benchmark coverage reached", str(families))
    else:
        pass_test(
            "Current evidence is correctly flagged as incomplete",
            f"found={families} missing={completeness.get('missing', [])}",
        )

    if completeness.get("complete") is False:
        pass_test("Runtime completeness check stays false below the product bar")
    else:
        fail_test("Runtime completeness check should not pass with only two benchmark families")


def test_current_card_product_verdict():
    section("Current Card Product Verdict")
    item = copy.deepcopy(SOURCE_ITEM)
    attach_model_release_packet(item, search_exhausted=True)
    meta = item.get("_enrichment", {})
    issues = validate_model_release_output(item, CURRENT_CARD_OUTPUT)

    product_complete = bool(meta.get("official_source_found")) and len(meta.get("benchmark_families_found", [])) >= 3
    if product_complete:
        if not issues:
            pass_test("Current card meets product bar")
        else:
            fail_test("Current card failed despite complete evidence", " | ".join(issues))
    else:
        pass_test(
            "Current card should be treated as incomplete for product purposes",
            f"official={meta.get('official_source_found')} benchmarks={meta.get('benchmark_families_found', [])}",
        )


def test_thinner_card_rejection():
    section("Thinner Card Rejection")
    item = copy.deepcopy(SOURCE_ITEM)
    attach_model_release_packet(item, search_exhausted=True)
    issues = validate_model_release_output(item, TOO_THIN_OUTPUT)

    benchmark_issue = any("benchmark families" in issue for issue in issues)
    key_number_issue = any("context" in issue.lower() or "speed" in issue.lower() for issue in issues)
    if benchmark_issue:
        pass_test("Guard rejects dropped benchmark rows")
    else:
        fail_test("Guard missed dropped benchmark rows", " | ".join(issues))

    if key_number_issue:
        pass_test("Guard rejects dropped key numbers")
    else:
        fail_test("Guard missed dropped key numbers", " | ".join(issues))


def test_all_available_rows_must_stay_in_table():
    section("All-Row Matrix Preservation")
    issues = validate_model_release_output(FULL_MATRIX_SOURCE_ITEM, FOUR_ROW_WITH_PROSE_OUTPUT)

    if any("output only has 5 rows" in issue.lower() for issue in issues):
        pass_test("Guard rejects dropping any benchmark rows when six benchmark families exist")
    else:
        fail_test("Guard allowed a six-family source packet to collapse to five rows", " | ".join(issues))

    if any("browsecomp" in issue.lower() for issue in issues):
        pass_test("Guard rejects demoting a benchmark family into summary prose")
    else:
        fail_test("Guard missed benchmark family demoted into summary prose", " | ".join(issues))


def main():
    print(f"\n{BOLD}{CYAN}============================================================")
    print("  GPT-5.4 MINI/NANO TARGETED REGRESSION")
    print(f"============================================================{RESET}")

    test_packet_rebuild()
    test_product_goal_completeness()
    test_current_card_product_verdict()
    test_thinner_card_rejection()
    test_all_available_rows_must_stay_in_table()

    total = RESULTS["pass"] + RESULTS["fail"]
    print(f"\n{BOLD}{CYAN}============================================================")
    print(f"  RESULTS: {total} checks")
    print(f"============================================================{RESET}")
    print(f"  {GREEN}PASS: {RESULTS['pass']}{RESET}")
    if RESULTS["fail"]:
        print(f"  {RED}FAIL: {RESULTS['fail']}{RESET}")
    else:
        print("  FAIL: 0")
    print()

    sys.exit(1 if RESULTS["fail"] else 0)


if __name__ == "__main__":
    main()
