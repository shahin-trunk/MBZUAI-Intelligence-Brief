"""
Enrichment Pipeline Test Suite
==============================
Standalone validation script for backend/pipeline/enricher.py.
Run: cd backend && python test_enrichment.py

Tests the enrichment chain from unit-level helpers through API connectivity
to the full progressive enrichment chain on real gatekeeper output data.
"""

import asyncio
import copy
import json
import sys
import time
from pathlib import Path

# -- Import config first (triggers .env loading) --
from config import ANTHROPIC_API_KEY, OUTPUT_DIR

from pipeline.enricher import (
    is_thin,
    _parse_judge_json,
    _truncate_at_sentence,
    _normalise_raw_content,
    fetch_source_url,
    serper_search_with_retry,
    evaluate_content,
    enrich_item,
    enrich_selected_items,
    SERPER_API_KEY,
)

# ---------------------------------------------------------------------------
# Output helpers
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
# Test data loader
# ---------------------------------------------------------------------------

GATEKEEPER_FILE = "gatekeeper_output_2026-03-05.json"


def load_gatekeeper_items() -> list[dict]:
    """Load selected items from the most recent gatekeeper output."""
    path = OUTPUT_DIR / GATEKEEPER_FILE
    if not path.exists():
        # Try other dates
        for date in ("2026-03-04", "2026-03-03"):
            alt = OUTPUT_DIR / f"gatekeeper_output_{date}.json"
            if alt.exists():
                path = alt
                break
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["selected"]


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: is_thin() detection
# ═══════════════════════════════════════════════════════════════════════════


def test_is_thin():
    section("Test 1: is_thin() detection")

    try:
        # 1a: Short text — thin
        item = {"raw_content": "This is a short sentence with only a few words."}
        assert is_thin(item), "Short text should be thin"
        pass_test("Short text → thin")
    except Exception as e:
        fail_test("Short text → thin", str(e))

    try:
        # 1b: 100 words — not thin
        item = {"raw_content": " ".join(["word"] * 100)}
        assert not is_thin(item), "100 words should not be thin"
        pass_test("100 words → not thin")
    except Exception as e:
        fail_test("100 words → not thin", str(e))

    try:
        # 1c: Empty string
        assert is_thin({"raw_content": ""}), "Empty should be thin"
        pass_test("Empty raw_content → thin")
    except Exception as e:
        fail_test("Empty raw_content → thin", str(e))

    try:
        # 1d: Missing key
        assert is_thin({}), "Missing key should be thin"
        pass_test("Missing raw_content key → thin")
    except Exception as e:
        fail_test("Missing raw_content key → thin", str(e))

    try:
        # 1e: Dict raw_content (gets JSON-serialized)
        item = {"raw_content": {"key": "value", "nested": True}}
        assert is_thin(item), "Dict raw_content (few tokens) → thin"
        pass_test("Dict raw_content → thin")
    except Exception as e:
        fail_test("Dict raw_content → thin", str(e))

    try:
        # 1f: Boundary — exactly 80 words = NOT thin (threshold is <80)
        item = {"raw_content": " ".join(["word"] * 80)}
        assert not is_thin(item), "Exactly 80 words should NOT be thin"
        pass_test("80 words (boundary) → not thin")
    except Exception as e:
        fail_test("80 words (boundary) → not thin", str(e))

    try:
        # 1g: Boundary — 79 words = thin
        item = {"raw_content": " ".join(["word"] * 79)}
        assert is_thin(item), "79 words should be thin"
        pass_test("79 words (boundary) → thin")
    except Exception as e:
        fail_test("79 words (boundary) → thin", str(e))

    try:
        # 1h: Real gatekeeper item
        items = load_gatekeeper_items()
        assert is_thin(items[0]), f"First gatekeeper item should be thin"
        wc = len(_normalise_raw_content(items[0].get("raw_content", "")).split())
        pass_test("Real gatekeeper item → thin", f"{wc} words")
    except Exception as e:
        fail_test("Real gatekeeper item → thin", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: _parse_judge_json() and _truncate_at_sentence()
# ═══════════════════════════════════════════════════════════════════════════


def test_parse_and_truncate():
    section("Test 2: _parse_judge_json() and _truncate_at_sentence()")

    # -- JSON parsing --

    try:
        result = _parse_judge_json('{"decision": "SUFFICIENT", "confidence": 0.9}')
        assert result["decision"] == "SUFFICIENT"
        assert result["confidence"] == 0.9
        pass_test("Parse clean JSON")
    except Exception as e:
        fail_test("Parse clean JSON", str(e))

    try:
        result = _parse_judge_json('```json\n{"decision": "INSUFFICIENT", "confidence": 0.3}\n```')
        assert result["decision"] == "INSUFFICIENT"
        pass_test("Parse markdown-wrapped JSON (```json)")
    except Exception as e:
        fail_test("Parse markdown-wrapped JSON", str(e))

    try:
        result = _parse_judge_json('```\n{"decision": "SUFFICIENT", "confidence": 0.8}\n```')
        assert result["decision"] == "SUFFICIENT"
        pass_test("Parse bare-fenced JSON (```)")
    except Exception as e:
        fail_test("Parse bare-fenced JSON", str(e))

    try:
        result = _parse_judge_json("This is not JSON at all")
        assert result["decision"] == "INSUFFICIENT"
        assert result["confidence"] == 0.0
        assert len(result["missing_elements"]) > 0
        pass_test("Malformed JSON → fallback INSUFFICIENT")
    except Exception as e:
        fail_test("Malformed JSON → fallback", str(e))

    # -- Sentence truncation --

    try:
        short = "Hello world. This is fine."
        assert _truncate_at_sentence(short, max_words=100) == short
        pass_test("Truncate: text under limit → unchanged")
    except Exception as e:
        fail_test("Truncate: text under limit", str(e))

    try:
        # Build text with sentence boundary at ~50 words
        part1 = " ".join(["alpha"] * 50)
        part2 = " ".join(["beta"] * 50)
        long_text = f"{part1}. {part2}. End."
        truncated = _truncate_at_sentence(long_text, max_words=60)
        assert truncated.endswith(".")
        assert len(truncated.split()) <= 60
        pass_test("Truncate: sentence boundary respected", f"{len(truncated.split())} words")
    except Exception as e:
        fail_test("Truncate: sentence boundary", str(e))

    try:
        # No punctuation — falls back to word limit
        no_boundary = " ".join(["word"] * 200)
        truncated = _truncate_at_sentence(no_boundary, max_words=100)
        assert len(truncated.split()) == 100
        pass_test("Truncate: no boundary → exact word limit")
    except Exception as e:
        fail_test("Truncate: no boundary fallback", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Serper API connectivity
# ═══════════════════════════════════════════════════════════════════════════


async def test_serper():
    section("Test 3: Serper API connectivity")

    if not SERPER_API_KEY:
        skip_test("Serper search", "SERPER_API_KEY not set in .env")
        return

    try:
        results_list = await serper_search_with_retry("MBZUAI artificial intelligence")

        assert len(results_list) > 0, "No search results returned"

        first = results_list[0]
        assert "title" in first and first["title"], "Missing title"
        assert "link" in first and first["link"].startswith("http"), "Missing/invalid link"
        assert "snippet" in first, "Missing snippet"

        pass_test("Serper search returns results", f"{len(results_list)} result(s)")
        for r in results_list:
            print(f"    {DIM}→ {r['title'][:60]}{RESET}")
    except Exception as e:
        fail_test("Serper search", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: Source URL fetch (trafilatura)
# ═══════════════════════════════════════════════════════════════════════════


async def test_fetch_source_url():
    section("Test 4: Source URL fetch (trafilatura)")

    try:
        import trafilatura  # noqa: F401
    except ImportError:
        skip_test("URL fetch", "trafilatura not installed — run: pip install trafilatura")
        return

    # 4a: Valid URL — WAM article from gatekeeper output
    try:
        url = "https://www.wam.ae/en/article/qatarenergy-declares-force-majeure-on-lng"
        result = await fetch_source_url(url)

        if result is None:
            fail_test("URL fetch (valid URL)", f"returned None for {url} — site may block scrapers")
        else:
            assert result["url"] == url
            assert result["source_step"] == "url_fetch"
            wc = len(result["extract"].split())
            assert wc > 20, f"Extract too short: {wc} words"
            pass_test("URL fetch (valid URL)", f"{wc} words extracted")
    except Exception as e:
        fail_test("URL fetch (valid URL)", str(e))

    # 4b: Invalid/empty URL → None
    try:
        assert await fetch_source_url("") is None
        assert await fetch_source_url("not-a-url") is None
        pass_test("URL fetch (invalid URLs → None)")
    except Exception as e:
        fail_test("URL fetch (invalid URLs → None)", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Judge evaluation (Haiku)
# ═══════════════════════════════════════════════════════════════════════════


async def test_judge_evaluation():
    section("Test 5: Judge evaluation (Haiku)")

    if not ANTHROPIC_API_KEY:
        skip_test("Judge evaluation", "ANTHROPIC_API_KEY not set")
        return

    import anthropic
    client = anthropic.AsyncAnthropic()

    # 5a: Sufficient content — 120+ words with specific facts
    try:
        sufficient = (
            "The UAE Ministry of Defence confirmed that the Emirates' air defense "
            "systems successfully intercepted 12 ballistic missiles and 123 armed "
            "drones launched from Iranian territory over a 48-hour period beginning "
            "March 1, 2026. The THAAD and Patriot missile defense batteries, deployed "
            "across Abu Dhabi, Dubai, and key military installations, achieved a 97.8% "
            "interception rate. Three civilian injuries were reported in Fujairah from "
            "debris. The Ministry spokesperson stated that all critical infrastructure, "
            "including oil facilities at Ruwais and Jebel Ali port, remained fully "
            "operational. President Sheikh Mohamed bin Zayed convened an emergency "
            "National Security Council session and spoke with US President Trump, who "
            "reaffirmed American commitment to Gulf security. The attacks represent "
            "the largest direct military assault on UAE territory since the 2022 "
            "Houthi drone strikes."
        )

        judge_result, usage = await evaluate_content(
            client,
            headline="UAE air defences intercept 12 ballistic missiles and 123 drones",
            raw_content=sufficient,
            extracts=[],
            is_model_release=False,
        )

        assert judge_result["decision"] in ("SUFFICIENT", "INSUFFICIENT")
        assert usage["input_tokens"] > 0
        assert usage["output_tokens"] > 0

        if judge_result["decision"] == "SUFFICIENT":
            pass_test("Judge: sufficient content → SUFFICIENT",
                       f"confidence={judge_result.get('confidence')}")
        else:
            fail_test("Judge: sufficient content → got INSUFFICIENT",
                       judge_result.get("reasoning", ""))
    except Exception as e:
        fail_test("Judge: sufficient content", str(e))

    # 5b: Thin content — 10 words, no detail
    try:
        thin = "UAE stock markets fell sharply after Iranian attacks."

        judge_result2, usage2 = await evaluate_content(
            client,
            headline="UAE stock markets plunge after Iranian attacks",
            raw_content=thin,
            extracts=[],
            is_model_release=False,
        )

        assert judge_result2["decision"] in ("SUFFICIENT", "INSUFFICIENT")

        if judge_result2["decision"] == "INSUFFICIENT":
            pass_test("Judge: thin content → INSUFFICIENT",
                       f"confidence={judge_result2.get('confidence')}")
        else:
            fail_test("Judge: thin content → got SUFFICIENT",
                       judge_result2.get("reasoning", ""))
    except Exception as e:
        fail_test("Judge: thin content", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Full enrichment chain (single item)
# ═══════════════════════════════════════════════════════════════════════════


async def test_single_enrichment():
    section("Test 6: Full enrichment chain (single item)")

    if not ANTHROPIC_API_KEY:
        skip_test("Single enrichment", "ANTHROPIC_API_KEY not set")
        return
    if not SERPER_API_KEY:
        skip_test("Single enrichment", "SERPER_API_KEY not set")
        return

    import anthropic
    client = anthropic.AsyncAnthropic()

    items = load_gatekeeper_items()
    # Use item[2] — QatarEnergy, 45 words, has a real WAM source URL
    item = copy.deepcopy(items[2])
    headline = item.get("headline", "")

    assert is_thin(item), "Test item should be thin before enrichment"
    print(f"    {DIM}Item: {headline[:70]}...{RESET}")

    try:
        start = time.time()
        enriched = await enrich_item(item, client)
        elapsed = time.time() - start

        # Check enriched_sources
        sources = enriched.get("enriched_sources", [])
        assert isinstance(sources, list)
        if len(sources) > 0:
            pass_test("enriched_sources populated", f"{len(sources)} source(s)")
        else:
            fail_test("enriched_sources empty", "Expected at least 1 source")

        # Check _enrichment metadata
        meta = enriched.get("_enrichment", {})
        assert meta.get("was_thin") is True, "_enrichment.was_thin should be True"
        assert len(meta.get("steps_taken", [])) >= 2, "Should have at least url_fetch + judge_1"
        assert "elapsed_seconds" in meta
        assert "tokens" in meta
        assert meta["tokens"]["input"] > 0, "Should have used some input tokens"

        enriched_wc = meta.get("enriched_word_count", 0)
        original_wc = meta.get("original_word_count", 0)
        if enriched_wc > original_wc:
            pass_test("Word count increased",
                       f"{original_wc} → {enriched_wc} words")
        else:
            fail_test("Word count not increased",
                       f"{original_wc} → {enriched_wc}")

        pass_test("_enrichment metadata complete",
                   f"steps={meta['steps_taken']}, "
                   f"{elapsed:.1f}s, final={meta.get('final_source', '?')}, "
                   f"tokens={meta['tokens']['input']}in+{meta['tokens']['output']}out")

    except Exception as e:
        fail_test("Single enrichment chain", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# TEST 7: enrich_selected_items() — batch with mixed thin/non-thin
# ═══════════════════════════════════════════════════════════════════════════


async def test_batch_enrichment():
    section("Test 7: enrich_selected_items() batch (mixed items)")

    if not ANTHROPIC_API_KEY:
        skip_test("Batch enrichment", "ANTHROPIC_API_KEY not set")
        return
    if not SERPER_API_KEY:
        skip_test("Batch enrichment", "SERPER_API_KEY not set")
        return

    import anthropic
    client = anthropic.AsyncAnthropic()

    items = load_gatekeeper_items()

    # 2 thin items from gatekeeper + 1 synthetic non-thin item
    test_items = [
        copy.deepcopy(items[11]),  # ChatGPT GPT-5.3, 15 words
        copy.deepcopy(items[8]),   # China GDP target, 23 words
    ]

    # Synthetic non-thin item (100 words)
    fat_item = {
        "headline": "Synthetic non-thin test item — should not be enriched",
        "raw_content": " ".join(
            [f"Word{i}" for i in range(100)]
        ),
        "source_url": "",
        "entities": [],
        "is_model_release": False,
    }
    test_items.append(fat_item)

    # Pre-checks
    assert is_thin(test_items[0]), "Item 0 should be thin"
    assert is_thin(test_items[1]), "Item 1 should be thin"
    assert not is_thin(test_items[2]), "Item 2 (synthetic) should NOT be thin"

    try:
        start = time.time()
        result_items, usage = await enrich_selected_items(test_items, client)
        elapsed = time.time() - start

        # Non-thin item should NOT have enrichment
        if "_enrichment" not in result_items[2]:
            pass_test("Non-thin item untouched")
        else:
            fail_test("Non-thin item was enriched", "Should have been skipped")

        # Thin items should have enrichment
        for i in (0, 1):
            meta = result_items[i].get("_enrichment", {})
            headline = result_items[i].get("headline", "?")[:50]
            if meta.get("was_thin"):
                pass_test(f"Thin item [{i}] enriched",
                           f"steps={meta.get('steps_taken', [])}, "
                           f"headline={headline}")
            else:
                fail_test(f"Thin item [{i}] missing enrichment", headline)

        # Aggregate usage tokens
        assert isinstance(usage, dict)
        assert usage["input_tokens"] > 0, "Should have used input tokens"
        assert usage["output_tokens"] > 0, "Should have used output tokens"
        pass_test("Aggregate usage tokens",
                   f"input={usage['input_tokens']}, output={usage['output_tokens']}, "
                   f"{elapsed:.1f}s total")

    except Exception as e:
        fail_test("Batch enrichment", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════


def main():
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print("  ENRICHMENT PIPELINE TEST SUITE")
    print(f"{'=' * 60}{RESET}")

    # Show environment status
    print(f"\n  {DIM}ANTHROPIC_API_KEY: {'set' if ANTHROPIC_API_KEY else 'NOT SET'}")
    print(f"  SERPER_API_KEY:   {'set' if SERPER_API_KEY else 'NOT SET'}")
    print(f"  Test data:        {GATEKEEPER_FILE}{RESET}")

    start = time.time()

    # Pure unit tests (no API calls)
    test_is_thin()
    test_parse_and_truncate()

    # API tests (async)
    async def run_api_tests():
        await test_serper()
        await test_fetch_source_url()
        await test_judge_evaluation()
        await test_single_enrichment()
        await test_batch_enrichment()

    asyncio.run(run_api_tests())

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
