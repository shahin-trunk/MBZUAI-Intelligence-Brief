"""Tests for `run_chunked_card_batches` — Phase 2 parallel-by-section
Ghostwriter wrapper.

Covers:
- Fast path: ≤chunk_size items call route_and_run_card_agents once.
- Chunked path: items grouped by brief_section are fired concurrently.
- Merged output preserves Gatekeeper's expected_order (allowed_ids).
- Usage aggregation across chunks.

All `route_and_run_card_agents` calls are mocked — no Anthropic API traffic.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.card_batch import run_chunked_card_batches  # noqa: E402


def _mk_item(item_id: str, section: str, headline: str = "h") -> dict:
    return {
        "id": item_id,
        "brief_section": section,
        "headline": f"{headline} {item_id}",
    }


def _mk_result(items: list[dict]) -> dict:
    return {"date": "2026-04-18", "items": items}


@pytest.mark.asyncio
async def test_chunked_fast_path_single_call_when_small(monkeypatch):
    """≤ chunk_size items: no chunking overhead, single call."""
    items = [_mk_item(f"id-{i}", "UAE") for i in range(10)]
    gk_payload = {"selected": items, "allowed_ids": [i["id"] for i in items]}

    mock_route = AsyncMock(
        return_value=(_mk_result(items), {"input_tokens": 100, "output_tokens": 50})
    )
    monkeypatch.setattr(
        "pipeline.card_batch.route_and_run_card_agents", mock_route
    )

    result, usage = await run_chunked_card_batches(
        client=AsyncMock(),
        gatekeeper_payload=gk_payload,
        today="2026-04-18",
        chunk_size=15,
    )

    assert mock_route.await_count == 1
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 50
    assert len(result["items"]) == 10


@pytest.mark.asyncio
async def test_chunked_path_fans_out_by_section(monkeypatch):
    """> chunk_size items: each section becomes a parallel chunk call."""
    uae_items = [_mk_item(f"uae-{i}", "UAE") for i in range(10)]
    intl_items = [
        _mk_item(f"intl-{i}", "International Politics & Policy") for i in range(8)
    ]
    model_items = [
        _mk_item(f"mr-{i}", "Model Releases & Technical Developments") for i in range(5)
    ]
    selected = uae_items + intl_items + model_items

    expected_ids = [i["id"] for i in selected]
    gk_payload = {"selected": selected, "allowed_ids": expected_ids}

    async def fake_route(**kwargs):
        # Echo the items we were asked to author.
        batch_items = kwargs["selected"]
        return (
            _mk_result(batch_items),
            {"input_tokens": 10 * len(batch_items), "output_tokens": 5 * len(batch_items)},
        )

    mock_route = AsyncMock(side_effect=fake_route)
    monkeypatch.setattr(
        "pipeline.card_batch.route_and_run_card_agents", mock_route
    )

    result, usage = await run_chunked_card_batches(
        client=AsyncMock(),
        gatekeeper_payload=gk_payload,
        today="2026-04-18",
        chunk_size=15,
    )

    # One call per distinct section (3 sections) — 23 items > chunk_size=15.
    assert mock_route.await_count == 3
    # Usage aggregated across chunks.
    assert usage["input_tokens"] == 10 * 23
    assert usage["output_tokens"] == 5 * 23
    # Output preserves Gatekeeper order.
    assert [i["id"] for i in result["items"]] == expected_ids


@pytest.mark.asyncio
async def test_chunked_path_preserves_gatekeeper_order_when_sections_interleave(
    monkeypatch,
):
    """Gatekeeper may interleave items across sections in its ranked output;
    the chunked wrapper must restore that order post-merge."""
    selected = [
        _mk_item("a", "UAE"),
        _mk_item("b", "International Politics & Policy"),
        _mk_item("c", "UAE"),
        _mk_item("d", "International Politics & Policy"),
        _mk_item("e", "UAE"),
    ]
    # Pad each section beyond chunk_size so the fast path doesn't kick in.
    for i in range(12):
        selected.append(_mk_item(f"pad-uae-{i}", "UAE"))
    expected_ids = [i["id"] for i in selected]
    gk_payload = {"selected": selected, "allowed_ids": expected_ids}

    async def fake_route(**kwargs):
        batch_items = kwargs["selected"]
        return (_mk_result(batch_items), {"input_tokens": 0, "output_tokens": 0})

    mock_route = AsyncMock(side_effect=fake_route)
    monkeypatch.setattr(
        "pipeline.card_batch.route_and_run_card_agents", mock_route
    )

    result, _ = await run_chunked_card_batches(
        client=AsyncMock(),
        gatekeeper_payload=gk_payload,
        today="2026-04-18",
        chunk_size=15,
    )

    # Output must match expected_ids order exactly — NOT section-grouped.
    assert [i["id"] for i in result["items"]] == expected_ids


@pytest.mark.asyncio
async def test_chunked_empty_selected_returns_none(monkeypatch):
    gk_payload = {"selected": [], "allowed_ids": []}
    mock_route = AsyncMock()
    monkeypatch.setattr(
        "pipeline.card_batch.route_and_run_card_agents", mock_route
    )
    result, usage = await run_chunked_card_batches(
        client=AsyncMock(),
        gatekeeper_payload=gk_payload,
        today="2026-04-18",
    )
    assert result is None
    assert usage == {"input_tokens": 0, "output_tokens": 0}
    mock_route.assert_not_awaited()
