"""Ghostwriter refusal-fallback tests.

Lock the contract that when an overridden model (e.g. a newly-released
Opus trial) refuses a prompt, ``run_ghostwriter`` retries once against
the canonical ``config.MODEL`` instead of crashing the whole pipeline.

Regression context: on 2026-04-17, Opus 4.7 (released that day) returned
``stop_reason="refusal"`` with ``tokens_out=1`` on a 17-item gatekeeper
batch, killing the pipeline. Reproduced deterministically across two
runs with identical token counts. Rolling Ghostwriter back to Sonnet 4.6
(commit 29ca625) unblocked that day's brief; this test pins the
refusal-fallback logic that lets future model trials fail safe rather
than taking down the morning brief.

Tier 1 — no API calls. Mocks ``client.messages.create`` directly.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import MODEL  # noqa: E402
from pipeline.ghostwriter import run_ghostwriter  # noqa: E402


# Minimal payload that passes GhostwriterOutput validation (date: str,
# items: list[GhostwriterItem]). Empty items is legal.
SUCCESS_JSON = '{"date": "2026-04-17", "items": []}'
TRIAL_MODEL = "claude-opus-4-7"


def _make_response(*, stop_reason: str, text: str | None = None,
                   input_tokens: int = 100, output_tokens: int | None = None):
    """Build a minimal Anthropic-shaped response object."""
    content = []
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    if output_tokens is None:
        # Refusals come back with a single meta-token; successful writes
        # with real prose. Caller can override for precise assertions.
        output_tokens = 1 if text is None else 50
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        usage=SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens,
        ),
    )


def _make_client(*responses):
    """Wrap a sequence of responses in an Anthropic-client shim."""
    create_mock = AsyncMock(
        side_effect=list(responses) if len(responses) > 1 else None,
        return_value=responses[0] if len(responses) == 1 else None,
    )
    client = SimpleNamespace(messages=SimpleNamespace(create=create_mock))
    return client, create_mock


# ---------------------------------------------------------------------------
# Refusal + fallback
# ---------------------------------------------------------------------------


@pytest.mark.tier1
@pytest.mark.asyncio
async def test_override_model_refusal_falls_back_to_canonical_model():
    """Trial model refuses → fallback call to MODEL returns prose."""
    client, create_mock = _make_client(
        _make_response(stop_reason="refusal", input_tokens=100),
        _make_response(stop_reason="end_turn", text=SUCCESS_JSON, input_tokens=100),
    )

    result, usage = await run_ghostwriter(
        client, "prompt", model=TRIAL_MODEL,
    )

    # Both calls happened, in order
    assert create_mock.await_count == 2
    first_kwargs = create_mock.await_args_list[0].kwargs
    second_kwargs = create_mock.await_args_list[1].kwargs
    assert first_kwargs["model"] == TRIAL_MODEL
    assert second_kwargs["model"] == MODEL
    # Prompt and max_tokens preserved in the fallback call
    assert second_kwargs["messages"] == [{"role": "user", "content": "prompt"}]
    assert second_kwargs["max_tokens"] == first_kwargs["max_tokens"]
    # Usage is summed across both calls
    assert usage["input_tokens"] == 200
    assert usage["output_tokens"] == 51  # 1 refusal + 50 success
    # Result is the fallback's parsed output
    assert result["date"] == "2026-04-17"
    assert result["items"] == []


@pytest.mark.tier1
@pytest.mark.asyncio
async def test_refusal_on_canonical_model_raises_without_fallback():
    """MODEL itself refuses: there's nothing safer to fall back to."""
    client, create_mock = _make_client(
        _make_response(stop_reason="refusal"),
    )

    with pytest.raises(ValueError, match="No text blocks"):
        await run_ghostwriter(client, "prompt")  # model=None → MODEL

    assert create_mock.await_count == 1


@pytest.mark.tier1
@pytest.mark.asyncio
async def test_refusal_on_canonical_model_raises_even_when_passed_explicitly():
    """Passing MODEL explicitly must also skip the fallback path."""
    client, create_mock = _make_client(
        _make_response(stop_reason="refusal"),
    )

    with pytest.raises(ValueError, match="No text blocks"):
        await run_ghostwriter(client, "prompt", model=MODEL)

    assert create_mock.await_count == 1


@pytest.mark.tier1
@pytest.mark.asyncio
async def test_both_models_refuse_raises_explanatory_error():
    """Both override and fallback refuse: fail with a message that names both."""
    client, create_mock = _make_client(
        _make_response(stop_reason="refusal"),
        _make_response(stop_reason="refusal"),
    )

    with pytest.raises(ValueError) as exc_info:
        await run_ghostwriter(client, "prompt", model=TRIAL_MODEL)

    msg = str(exc_info.value)
    assert TRIAL_MODEL in msg
    assert MODEL in msg
    assert "refused" in msg
    assert create_mock.await_count == 2


# ---------------------------------------------------------------------------
# Happy path + non-refusal failures
# ---------------------------------------------------------------------------


@pytest.mark.tier1
@pytest.mark.asyncio
async def test_success_on_first_try_skips_fallback():
    """Happy path: one API call, no fallback, usage reflects one call."""
    client, create_mock = _make_client(
        _make_response(stop_reason="end_turn", text=SUCCESS_JSON),
    )

    result, usage = await run_ghostwriter(client, "prompt", model=TRIAL_MODEL)

    assert create_mock.await_count == 1
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 50
    assert result["date"] == "2026-04-17"


@pytest.mark.tier1
@pytest.mark.asyncio
async def test_non_refusal_empty_response_does_not_trigger_fallback():
    """If the API returns empty text for a non-refusal reason (e.g. max_tokens
    hit), raise immediately — no second call, since fallback is specifically
    for refusals."""
    client, create_mock = _make_client(
        _make_response(stop_reason="max_tokens"),
    )

    with pytest.raises(ValueError, match="No text blocks"):
        await run_ghostwriter(client, "prompt", model=TRIAL_MODEL)

    # Only one call — max_tokens is not a refusal, so no fallback
    assert create_mock.await_count == 1
