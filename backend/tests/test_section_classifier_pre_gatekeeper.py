"""Tests for the pre-Gatekeeper section classifier (Phase 2).

Covers `classify_candidate_sections` in `pipeline/section_classifier.py`:
- Writes both `brief_section` and `section` fields.
- Batches items across multiple Haiku calls.
- Defaults to "International Business & Technology" when the classifier
  can't place an item.
- Idempotency: no-op when every item already has a canonical section.

All Anthropic API calls are mocked (no network, no API keys needed).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.section_classifier import (  # noqa: E402
    DEFAULT_SECTION,
    SECTIONS,
    classify_candidate_sections,
)


def _mock_anthropic_response(text: str) -> MagicMock:
    """Build a MagicMock that quacks like an anthropic.Messages response."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


def _mock_client(text_responses: list[str]) -> MagicMock:
    """Mock AsyncAnthropic whose `.messages.create` returns each text in order."""
    responses = [_mock_anthropic_response(t) for t in text_responses]
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(side_effect=responses)
    return client


@pytest.mark.asyncio
async def test_classify_candidate_sections_writes_both_fields():
    items = [
        {"_idx": 0, "headline": "G42 launches sovereign cloud", "summary": "AI infra"},
        {"_idx": 1, "headline": "MBZUAI opens new lab", "summary": "Research"},
    ]
    client = _mock_client([
        '[{"id": "0", "section": "UAE"}, '
        '{"id": "1", "section": "Regional Research & Academic Events"}]'
    ])
    await classify_candidate_sections(client, items)
    assert items[0]["brief_section"] == "UAE"
    assert items[0]["section"] == "UAE"
    assert items[1]["brief_section"] == "Regional Research & Academic Events"
    assert items[1]["section"] == "Regional Research & Academic Events"


@pytest.mark.asyncio
async def test_classify_candidate_sections_defaults_when_missing():
    """Items the classifier didn't return should default (no 'Other' bucket)."""
    items = [
        {"_idx": 0, "headline": "Story A", "summary": "x"},
        {"_idx": 1, "headline": "Story B", "summary": "y"},
        {"_idx": 2, "headline": "Story C", "summary": "z"},
    ]
    # Classifier only returns id=0; ids 1 and 2 fall through to default.
    client = _mock_client(['[{"id": "0", "section": "UAE"}]'])
    await classify_candidate_sections(client, items)
    assert items[0]["brief_section"] == "UAE"
    assert items[1]["brief_section"] == DEFAULT_SECTION
    assert items[2]["brief_section"] == DEFAULT_SECTION
    assert DEFAULT_SECTION == "International Business & Technology"


@pytest.mark.asyncio
async def test_classify_candidate_sections_batches_across_calls(monkeypatch):
    """With CANDIDATE_BATCH_SIZE=30, 45 items should split into 2 batches."""
    from pipeline import section_classifier

    monkeypatch.setattr(section_classifier, "CANDIDATE_BATCH_SIZE", 30)
    items = [
        {"_idx": i, "headline": f"Headline {i}", "summary": "s"}
        for i in range(45)
    ]
    # Build two responses — first 30 items UAE, next 15 International Politics.
    r1 = (
        "["
        + ",".join(f'{{"id": "{i}", "section": "UAE"}}' for i in range(30))
        + "]"
    )
    r2 = (
        "["
        + ",".join(
            f'{{"id": "{i}", "section": "International Politics & Policy"}}'
            for i in range(30, 45)
        )
        + "]"
    )
    client = _mock_client([r1, r2])
    await classify_candidate_sections(client, items)

    assert client.messages.create.await_count == 2
    assert items[0]["brief_section"] == "UAE"
    assert items[29]["brief_section"] == "UAE"
    assert items[30]["brief_section"] == "International Politics & Policy"
    assert items[44]["brief_section"] == "International Politics & Policy"


@pytest.mark.asyncio
async def test_classify_candidate_sections_idempotent_skip():
    """No-op when every item already has a canonical section — safe on
    --from-stage=gatekeeper resume without double-billing."""
    items = [
        {"_idx": 0, "headline": "x", "summary": "y", "brief_section": "UAE"},
        {
            "_idx": 1,
            "headline": "a",
            "summary": "b",
            "brief_section": "Model Releases & Technical Developments",
        },
    ]
    client = _mock_client([])  # Should never be invoked.
    await classify_candidate_sections(client, items)
    client.messages.create.assert_not_awaited()
    # Fields unchanged.
    assert items[0]["brief_section"] == "UAE"
    assert items[1]["brief_section"] == "Model Releases & Technical Developments"


@pytest.mark.asyncio
async def test_classify_candidate_sections_empty_input():
    """No-op on empty list — fast path before any client work."""
    client = _mock_client([])
    await classify_candidate_sections(client, [])
    client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify_candidate_sections_rejects_non_canonical_section():
    """If the classifier returns a section not in SECTIONS (e.g. hallucinated
    'Other' bucket), the item defaults rather than accepting the bad label."""
    items = [{"_idx": 0, "headline": "x", "summary": "y"}]
    # Classifier returns a non-canonical section name.
    client = _mock_client(['[{"id": "0", "section": "Other"}]'])
    await classify_candidate_sections(client, items)
    assert items[0]["brief_section"] == DEFAULT_SECTION
    assert items[0]["brief_section"] in SECTIONS


@pytest.mark.asyncio
async def test_classify_candidate_sections_handles_malformed_response():
    """Bad JSON from Haiku → every item defaults; no exception propagates."""
    items = [{"_idx": 0, "headline": "x"}, {"_idx": 1, "headline": "y"}]
    client = _mock_client(["not json at all {{{"])
    await classify_candidate_sections(client, items)
    assert items[0]["brief_section"] == DEFAULT_SECTION
    assert items[1]["brief_section"] == DEFAULT_SECTION
