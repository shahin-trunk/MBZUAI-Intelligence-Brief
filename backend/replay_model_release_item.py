"""
Live replay utility for a single model-release item.

Default use:
  python3.11 replay_model_release_item.py \
    --pipeline-run-json /tmp/pipeline_run_2026-03-19.json \
    --headline-substring "gpt-5.4 mini and nano"

The script:
  1. Loads the saved gatekeeper item from a pipeline_runs export.
  2. Re-runs current enrichment logic live against that exact item.
  3. Prints the resulting source coverage, benchmark facts, key numbers,
     and the model-release completeness verdict.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
from pathlib import Path
from typing import Any

import anthropic

from config import ANTHROPIC_API_KEY
from pipeline.enricher import SERPER_API_KEY, enrich_item
from pipeline.model_release import build_model_release_packet, summarise_model_release_completeness


CYAN = "\033[96m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
DIM = "\033[2m"


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}── {title} ──{RESET}")


def load_pipeline_item(path: Path, headline_substring: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError(f"Unexpected pipeline run payload in {path}")

    gatekeeper_log = (data[0] or {}).get("gatekeeper_log") or {}
    selected = gatekeeper_log.get("selected") or []
    needle = headline_substring.lower()
    matches = [
        item for item in selected
        if needle in str(item.get("headline", "")).lower()
    ]
    if not matches:
        raise ValueError(
            f"No gatekeeper item matched headline substring {headline_substring!r} in {path}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"Multiple gatekeeper items matched headline substring {headline_substring!r}"
        )
    return matches[0]


def print_sources(item: dict[str, Any]) -> None:
    sources = item.get("enriched_sources") or []
    if not sources:
        print(f"{YELLOW}No enrichment sources returned.{RESET}")
        return
    for idx, source in enumerate(sources, start=1):
        url = source.get("url", "")
        title = source.get("title", "")
        extract = " ".join(str(source.get("extract", "")).split())
        preview = extract[:220] + ("..." if len(extract) > 220 else "")
        print(f"{idx}. {title}")
        print(f"   {DIM}{url}{RESET}")
        if preview:
            print(f"   {preview}")


def print_facts(label: str, facts: list[dict[str, Any]], fields: list[str]) -> None:
    section(label)
    if not facts:
        print(f"{YELLOW}None found.{RESET}")
        return
    for idx, fact in enumerate(facts, start=1):
        parts = [str(fact.get(field, "")).strip() for field in fields if str(fact.get(field, "")).strip()]
        print(f"{idx}. {' | '.join(parts)}")


async def replay(args: argparse.Namespace) -> int:
    if not ANTHROPIC_API_KEY:
        print(f"{RED}ANTHROPIC_API_KEY is required for live replay.{RESET}")
        return 1
    if not SERPER_API_KEY:
        print(f"{RED}SERPER_API_KEY is required for live replay.{RESET}")
        return 1

    source_item = load_pipeline_item(Path(args.pipeline_run_json), args.headline_substring)
    source_item = copy.deepcopy(source_item)
    source_item["is_model_release"] = True
    source_item.pop("_enrichment", None)
    source_item.pop("enriched_sources", None)
    source_item.pop("enriched_facts", None)
    source_item.pop("benchmark_facts", None)
    source_item.pop("key_number_facts", None)
    source_item.pop("coverage_notes", None)

    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print("  MODEL RELEASE LIVE REPLAY")
    print(f"{'=' * 60}{RESET}")
    print(f"\nHeadline: {source_item.get('headline', '')}")
    print(f"Item ID:   {source_item.get('id', '')}")
    print(f"Section:   {source_item.get('brief_section', '')}")
    print(f"Entities:  {', '.join(source_item.get('entities', []) or [])}")

    section("Raw Content")
    print(source_item.get("raw_content", ""))

    client = anthropic.AsyncAnthropic()
    enriched = await enrich_item(source_item, client)

    packet = build_model_release_packet(enriched)
    completeness = summarise_model_release_completeness(packet, search_exhausted=True)
    meta = enriched.get("_enrichment") or {}

    section("Replay Steps")
    print(f"Steps:      {meta.get('steps_taken', [])}")
    print(f"Final src:  {meta.get('final_source')}")
    print(f"Word count: {meta.get('enriched_word_count')}")
    judge1 = meta.get("judge_1_result") or {}
    judge2 = meta.get("judge_2_result") or {}
    if judge1:
        print(f"Judge 1:    {judge1.get('decision')} | missing={judge1.get('missing_elements', [])}")
    if judge2:
        print(f"Judge 2:    {judge2.get('decision')} | missing={judge2.get('missing_elements', [])}")

    section("Sources")
    print_sources(enriched)

    print_facts(
        "Benchmark Facts",
        packet.get("benchmark_facts", []),
        ["benchmark", "model", "score", "source_url"],
    )
    print_facts(
        "Key Number Facts",
        packet.get("key_number_facts", []),
        ["label", "value", "qualifier", "source_url"],
    )

    section("Coverage Notes")
    notes = completeness.get("coverage_notes", [])
    if notes:
        for idx, note in enumerate(notes, start=1):
            print(f"{idx}. {note}")
    else:
        print(f"{YELLOW}None.{RESET}")

    section("Completeness Verdict")
    families = completeness.get("benchmark_families_found", [])
    status = "COMPLETE" if completeness.get("complete") else "INCOMPLETE"
    color = GREEN if completeness.get("complete") else RED
    print(f"Status:     {color}{status}{RESET}")
    print(f"Benchmarks: {families}")
    print(f"Official:   {completeness.get('official_source_found')}")
    print(f"Pricing:    {completeness.get('pricing_found')}")
    print(f"Availability: {completeness.get('availability_found')}")
    print(f"Dual model: {completeness.get('dual_model_release')}")
    if completeness.get("missing"):
        print(f"Missing:    {completeness.get('missing')}")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a single model-release item live.")
    parser.add_argument(
        "--pipeline-run-json",
        default="/tmp/pipeline_run_2026-03-19.json",
        help="Path to a pipeline_runs export containing gatekeeper_log.",
    )
    parser.add_argument(
        "--headline-substring",
        default="gpt-5.4 mini and nano",
        help="Case-insensitive headline substring used to select the item.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(replay(parse_args())))
