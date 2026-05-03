"""
Targeted regression test for Anthropic Claude Sonnet 4.6 extraction.

Goal:
Verify that the generalized model-release extraction path works on a
non-OpenAI launch with different naming and source formatting.

This fixture intentionally uses official Anthropic-style source material:
  1. Official release-note prose for pricing, context, and availability.
  2. Official system-card benchmark snippets for numeric performance data.

Run:
  cd backend && python3.11 test_anthropic_sonnet46_targeted.py
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
    "id": "anthropic-sonnet-4.6-fixture",
    "headline": "Anthropic releases Claude Sonnet 4.6 for coding and computer-use workflows",
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "entities": ["Anthropic", "Claude Sonnet 4.6"],
    "raw_content": (
        "Anthropic introduced Claude Sonnet 4.6 as an upgraded model for coding, "
        "computer use, and long-context reasoning."
    ),
    "enriched_sources": [
        {
            "url": "https://www.anthropic.com/news/claude-sonnet-4-6",
            "title": "Introducing Claude Sonnet 4.6",
            "extract": (
                "Claude Sonnet 4.6 is our most capable Sonnet model yet. "
                "Claude Sonnet 4.6 features a 1M token context window in beta. "
                "Claude Sonnet 4.6 pricing starts at $3/$15 per million tokens. "
                "Claude Sonnet 4.6 is available in Claude.ai, the Anthropic API, "
                "Amazon Bedrock, Google Vertex AI, and Microsoft Azure AI Foundry."
            ),
        },
        {
            "url": "https://www.anthropic.com/transparency/model-report",
            "title": "Anthropic Model Report",
            "extract": (
                "Claude Sonnet 4.6 can be accessed through Claude.ai, the Anthropic API, "
                "Amazon Bedrock, Google Vertex AI, and Microsoft Azure AI Foundry."
            ),
        },
        {
            "url": "https://www-cdn.anthropic.com/78073f739564e986ff3e28522761a7a0b4484f84.pdf",
            "title": "Claude Sonnet 4.6 System Card",
            "extract": (
                "Claude Sonnet 4.6 achieved 79.6% on SWE-bench Verified. "
                "Using this setup, Claude Sonnet 4.6 achieved a 59.1% pass rate on "
                "Terminal-Bench 2.0. Claude Sonnet 4.6 achieved an OSWorld-Verified "
                "score of 72.5%, within 0.2% of Claude Opus 4.6's 72.7% score. "
                "Claude Sonnet 4.6 achieved a score of 89.9% on GPQA Diamond."
            ),
        },
    ],
    "_enrichment": {},
}


TOO_THIN_OUTPUT = {
    "id": "anthropic-sonnet-4.6-fixture",
    "model_release_data": {
        "developer": "Anthropic",
        "model_name": "Claude Sonnet 4.6",
        "key_numbers": [
            {"label": "Pricing (sonnet 4.6)", "value": "$3/$15", "qualifier": "per 1M in/out tokens"},
        ],
        "benchmarks": {
            "models": ["Claude Sonnet 4.6", "Claude Opus 4.6"],
            "highlighted_model_index": 0,
            "rows": [
                {"benchmark": "OSWorld-Verified", "scores": ["72.5%", "72.7%"]},
            ],
        },
    },
}


def test_packet_rebuild():
    section("Packet Rebuild")
    item = copy.deepcopy(SOURCE_ITEM)
    packet = build_model_release_packet(item)

    variants = packet.get("variants", [])
    if variants == ["Claude Sonnet 4.6"]:
        pass_test("Detected Claude-style versioned variant", str(variants))
    else:
        fail_test("Unexpected Claude variant detection", str(variants))

    families = set(packet.get("benchmark_families_found", []))
    expected = {"SWE-bench Verified", "Terminal-Bench 2.0", "OSWorld-Verified", "GPQA Diamond"}
    if expected.issubset(families):
        pass_test("Extracted benchmark families from official Anthropic sources", str(sorted(families)))
    else:
        fail_test("Missing Anthropic benchmark families", str(sorted(families)))

    kinds = {(fact.get("label"), fact.get("value")) for fact in packet.get("key_number_facts", [])}
    if ("Pricing (sonnet 4.6)", "$3/$15") in kinds:
        pass_test("Extracted pricing from Anthropic release prose", str(sorted(kinds)))
    else:
        fail_test("Missing Anthropic pricing extraction", str(sorted(kinds)))

    if ("Context (sonnet 4.6)", "1M") in kinds:
        pass_test("Extracted token context window from Anthropic release prose", str(sorted(kinds)))
    else:
        fail_test("Missing Anthropic context extraction", str(sorted(kinds)))

    completeness = summarise_model_release_completeness(packet, search_exhausted=True)
    if completeness.get("official_source_found") and completeness.get("availability_found"):
        pass_test("Detected official source and availability coverage")
    else:
        fail_test(
            "Missing official-source or availability coverage",
            f"official={completeness.get('official_source_found')} availability={completeness.get('availability_found')}",
        )


def test_completeness():
    section("Completeness Verdict")
    item = copy.deepcopy(SOURCE_ITEM)
    attach_model_release_packet(item, search_exhausted=True)
    completeness = summarise_model_release_completeness(
        build_model_release_packet(item),
        search_exhausted=True,
    )

    if completeness.get("complete") is True:
        pass_test("Anthropic Claude Sonnet 4.6 fixture clears completeness bar")
    else:
        fail_test("Anthropic Claude Sonnet 4.6 fixture should be complete", str(completeness))

    if len(completeness.get("benchmark_families_found", [])) >= 4:
        pass_test("Benchmark breadth is above the minimum product bar", str(completeness.get("benchmark_families_found", [])))
    else:
        fail_test("Benchmark breadth is unexpectedly thin", str(completeness.get("benchmark_families_found", [])))


def test_sparse_output_rejected():
    section("Sparse Output Guard")
    item = copy.deepcopy(SOURCE_ITEM)
    attach_model_release_packet(item, search_exhausted=True)
    issues = validate_model_release_output(item, TOO_THIN_OUTPUT)

    if any("benchmark families" in issue for issue in issues):
        pass_test("Guard rejects dropped Anthropic benchmark rows", str(issues))
    else:
        fail_test("Guard missed dropped Anthropic benchmark rows", str(issues))

    if any("context" in issue.lower() for issue in issues):
        pass_test("Guard rejects dropped Anthropic context key number", str(issues))
    else:
        fail_test("Guard missed dropped Anthropic context key number", str(issues))


def main():
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print("  ANTHROPIC MODEL RELEASE TARGETED CHECK")
    print(f"{'=' * 60}{RESET}")

    test_packet_rebuild()
    test_completeness()
    test_sparse_output_rejected()

    total = RESULTS["pass"] + RESULTS["fail"]
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  RESULTS: {total} checks")
    print(f"{'=' * 60}{RESET}")
    print(f"  {GREEN}PASS: {RESULTS['pass']}{RESET}")
    if RESULTS["fail"]:
        print(f"  {RED}FAIL: {RESULTS['fail']}{RESET}")
    else:
        print("  FAIL: 0")
    print()

    sys.exit(1 if RESULTS["fail"] else 0)


if __name__ == "__main__":
    main()
