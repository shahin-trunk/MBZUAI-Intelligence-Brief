"""Tests for the event-tuple extraction stage (Phase 2 of structural plan).

Pins:
1. The Pydantic schema accepts the documented shape.
2. The extractor's idempotent / empty / fallback paths work.
3. The structured-outputs path returns valid tuples for representative
   fixtures (gated on ANTHROPIC_API_KEY, mirrors test_triage live tests).

Mock tests cover the application layer; live tests cover end-to-end
quality. The Phase 3/4 dedup tests then consume tuples downstream.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.schemas import (  # noqa: E402
    EventTuple, EventTupleVerdict, EventTupleBatchOutput,
)
from pipeline.event_tuples import (  # noqa: E402
    extract_event_tuples,
    _candidate_signal,
    _build_user_message,
    _load_extraction_prompt,
    _apply_tuples,
    EXTRACT_BATCH_SIZE,
    EXTRACT_CONCURRENCY,
)


# ---------------------------------------------------------------------------
# Pydantic schema invariants
# ---------------------------------------------------------------------------


def test_event_tuple_accepts_minimal_shape():
    t = EventTuple(event_type="other", action="x")
    assert t.primary_actor is None
    assert t.counterpart is None
    assert t.location is None
    assert t.date_or_period is None
    assert t.key_numbers == []


def test_event_tuple_accepts_full_shape():
    t = EventTuple(
        event_type="diplomatic_action",
        primary_actor="Trump",
        counterpart="Iran",
        action="cancels talks",
        location="Pakistan",
        date_or_period="April 27",
        key_numbers=["$10B", "10%"],
    )
    assert t.primary_actor == "Trump"
    assert t.counterpart == "Iran"
    assert t.key_numbers == ["$10B", "10%"]


def test_event_tuple_rejects_unknown_event_type():
    """The closed enum prevents the judge from inventing event_types."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        EventTuple(event_type="not_a_real_type", action="x")


def test_event_tuple_coerces_null_key_numbers_to_empty_list():
    """Mirrors the Sonnet-null-coercion pattern in other schemas: a model
    that emits `null` instead of `[]` for empty lists must not trip
    validation."""
    t = EventTuple(event_type="other", action="x", key_numbers=None)
    assert t.key_numbers == []


def test_event_tuple_verdict_uses_tuple_alias():
    """The Pydantic field is `tuple_` (Python keyword) but exposed as
    `tuple` in JSON. Both populate-by-name and populate-by-alias must
    work so the model can be reconstructed from either input shape."""
    v_alias = EventTupleVerdict.model_validate({
        "id": 0,
        "tuple": {"event_type": "other", "action": "x"},
    })
    v_name = EventTupleVerdict(
        id=0, tuple_=EventTuple(event_type="other", action="x")
    )
    assert v_alias.tuple_.event_type == "other"
    assert v_name.tuple_.event_type == "other"
    # Round-trip JSON form preserves the alias.
    dumped = v_name.model_dump(by_alias=True)
    assert "tuple" in dumped


def test_event_tuple_batch_output_required():
    """The `verdicts` field is required — empty batch is allowed but
    missing field is not."""
    from pydantic import ValidationError
    EventTupleBatchOutput(verdicts=[])  # empty OK
    with pytest.raises(ValidationError):
        EventTupleBatchOutput()  # missing verdicts


# ---------------------------------------------------------------------------
# Helper-function invariants (no network)
# ---------------------------------------------------------------------------


def test_candidate_signal_truncates_long_summary():
    item = {"headline": "H", "summary": "A" * 1000}
    sig = _candidate_signal(item)
    # Headline + " | " + 300 chars of summary = ~305 chars total.
    assert len(sig) < 350
    assert sig.startswith("H | ")


def test_candidate_signal_falls_back_to_raw_content():
    item = {"headline": "H", "summary": "", "raw_content": "fallback body"}
    sig = _candidate_signal(item)
    assert "fallback body" in sig


def test_candidate_signal_handles_missing_body():
    item = {"headline": "Lone headline"}
    assert _candidate_signal(item) == "Lone headline"


def test_build_user_message_uses_zero_based_ids():
    items = [{"headline": "A"}, {"headline": "B"}, {"headline": "C"}]
    msg = _build_user_message(items)
    assert msg.startswith("0. A")
    assert "1. B" in msg
    assert "2. C" in msg


def test_load_extraction_prompt_extracts_critical_rules():
    """The prompt body must survive the .md fence extraction and contain
    the structural anchors (CRITICAL_RULES + EXAMPLES)."""
    body = _load_extraction_prompt()
    assert "<critical_rules>" in body
    assert "PRIMARY_ACTOR" in body
    assert "COUNTERPART" in body
    assert "<examples>" in body
    # All four worked-example pairs that motivated the structural fix
    # must appear.
    assert "Abdullah bin Zayed" in body  # bilateral counterpart
    assert "Vance" in body and "Trump" in body  # principal-shift
    assert "GPT-5.5" in body  # paraphrase
    assert "Tencent" in body and "DeepSeek" in body  # event_type differs


def test_apply_tuples_writes_event_tuple_in_place():
    items = [{"headline": "X"}, {"headline": "Y"}]
    parsed = EventTupleBatchOutput(verdicts=[
        EventTupleVerdict(
            id=0, tuple_=EventTuple(event_type="other", action="a"),
        ),
        EventTupleVerdict(
            id=1, tuple_=EventTuple(event_type="other", action="b"),
        ),
    ])
    applied = _apply_tuples(items, chunk_offset=0, parsed=parsed)
    assert applied == 2
    assert items[0]["_event_tuple"]["action"] == "a"
    assert items[1]["_event_tuple"]["action"] == "b"


def test_apply_tuples_respects_chunk_offset():
    """When verdicts come from a non-zero-offset chunk, the verdict.id is
    chunk-local; the offset moves it back to the global index."""
    items = [{"headline": str(i)} for i in range(5)]
    parsed = EventTupleBatchOutput(verdicts=[
        EventTupleVerdict(
            id=0, tuple_=EventTuple(event_type="other", action="a"),
        ),
        EventTupleVerdict(
            id=1, tuple_=EventTuple(event_type="other", action="b"),
        ),
    ])
    # Apply with chunk_offset=3 -> verdicts hit items[3] and items[4].
    _apply_tuples(items, chunk_offset=3, parsed=parsed)
    assert "_event_tuple" not in items[0]
    assert "_event_tuple" not in items[2]
    assert items[3]["_event_tuple"]["action"] == "a"
    assert items[4]["_event_tuple"]["action"] == "b"


def test_apply_tuples_handles_none_parsed():
    items = [{"headline": "X"}]
    applied = _apply_tuples(items, chunk_offset=0, parsed=None)
    assert applied == 0
    assert "_event_tuple" not in items[0]


# ---------------------------------------------------------------------------
# extract_event_tuples paths (no network)
# ---------------------------------------------------------------------------


def test_extract_event_tuples_empty_input_returns_zero_status():
    items, telem = asyncio.run(extract_event_tuples(None, []))
    assert items == []
    assert telem["status"] == "ok"
    assert telem["total_items"] == 0
    assert telem["tuples_extracted"] == 0


def test_extract_event_tuples_idempotent_skip_when_all_have_tuples():
    """The resume path: if every item already carries `_event_tuple`,
    extraction skips entirely — saves the API call cost and keeps the
    pipeline fast on `--from-stage` resume runs."""
    items = [
        {"headline": "X", "_event_tuple": {"event_type": "other", "action": "a"}},
        {"headline": "Y", "_event_tuple": {"event_type": "other", "action": "b"}},
    ]
    out, telem = asyncio.run(extract_event_tuples(None, items))
    assert telem["status"] == "idempotent_skip"
    assert telem["tuples_extracted"] == 2
    assert telem["input_tokens"] == 0  # no API call


@pytest.mark.asyncio
async def test_extract_event_tuples_chunks_and_merges(monkeypatch):
    """End-to-end with a mocked client: 5 items split into 3 chunks of 2,
    each chunk's response gets merged back to the right global indices.
    """
    from pipeline import event_tuples

    monkeypatch.setattr(event_tuples, "EXTRACT_BATCH_SIZE", 2)
    monkeypatch.setattr(event_tuples, "EXTRACT_CONCURRENCY", 2)

    items = [{"headline": f"H{i}"} for i in range(5)]

    class _FakeContent:
        def __init__(self, text):
            self.text = text
            self.type = "text"

    class _FakeUsage:
        input_tokens = 100
        output_tokens = 50

    class _FakeResponse:
        def __init__(self, parsed):
            self.parsed_output = parsed
            self.usage = _FakeUsage()
            self.content = []

    class _FakeMessages:
        @staticmethod
        async def parse(*, model, max_tokens, system, messages, output_format, timeout):
            # Always return tuples for both items in the chunk, with
            # local 0-based ids. The wrapper applies the chunk offset.
            user = messages[0]["content"]
            n = len(user.splitlines())
            verdicts = [
                EventTupleVerdict(
                    id=i,
                    tuple_=EventTuple(
                        event_type="other",
                        action=f"chunk-action-{i}",
                    ),
                )
                for i in range(n)
            ]
            return _FakeResponse(EventTupleBatchOutput(verdicts=verdicts))

    class _FakeClient:
        messages = _FakeMessages

    out, telem = await extract_event_tuples(_FakeClient(), items)

    assert telem["status"] == "ok"
    assert telem["tuples_extracted"] == 5
    assert telem["tuples_failed"] == 0
    # Every item must have a tuple.
    for it in out:
        assert "_event_tuple" in it
        assert it["_event_tuple"]["event_type"] == "other"


@pytest.mark.asyncio
async def test_extract_event_tuples_falls_back_to_manual_json(monkeypatch):
    """When `messages.parse()` raises TypeError/AttributeError (older SDK
    or missing `output_format` support), the extractor falls back to
    `messages.create()` + manual JSON parsing without dropping items."""
    from pipeline import event_tuples

    monkeypatch.setattr(event_tuples, "EXTRACT_BATCH_SIZE", 5)
    items = [{"headline": f"H{i}"} for i in range(3)]

    class _Block:
        type = "text"
        def __init__(self, text):
            self.text = text

    class _FakeUsage:
        input_tokens = 80
        output_tokens = 40

    class _CreateResponse:
        usage = _FakeUsage()
        def __init__(self, text):
            self.content = [_Block(text)]

    class _FakeMessages:
        @staticmethod
        async def parse(**kwargs):
            raise TypeError("output_format not supported")

        @staticmethod
        async def create(**kwargs):
            payload = {
                "verdicts": [
                    {
                        "id": i,
                        "tuple": {"event_type": "other", "action": f"a{i}"},
                    }
                    for i in range(3)
                ]
            }
            return _CreateResponse(json.dumps(payload))

    class _FakeClient:
        messages = _FakeMessages

    out, telem = await extract_event_tuples(_FakeClient(), items)
    assert telem["status"] == "ok"
    assert telem["tuples_extracted"] == 3
    assert all("_event_tuple" in it for it in out)
    # Both attempts captured in the chunk telemetry.
    assert len(telem["chunks"][0]["attempts"]) == 2
    assert telem["chunks"][0]["attempts"][0]["path"] == "structured_outputs"
    assert telem["chunks"][0]["attempts"][1]["path"] == "manual_json"


@pytest.mark.asyncio
async def test_extract_event_tuples_fails_open_when_both_paths_fail(monkeypatch):
    """If structured outputs AND manual JSON both fail, the chunk is
    reported as failed but downstream stages still receive the items
    (without `_event_tuple`). They must fall back to legacy LLM-judged
    dedup gracefully."""
    from pipeline import event_tuples

    monkeypatch.setattr(event_tuples, "EXTRACT_BATCH_SIZE", 5)
    items = [{"headline": "H"}]

    class _Block:
        type = "text"
        def __init__(self, text): self.text = text

    class _Resp:
        usage = None
        def __init__(self, text): self.content = [_Block(text)]

    class _FakeMessages:
        @staticmethod
        async def parse(**_):
            raise RuntimeError("network down")
        @staticmethod
        async def create(**_):
            return _Resp("not json at all")

    class _FakeClient:
        messages = _FakeMessages

    out, telem = await extract_event_tuples(_FakeClient(), items)
    assert telem["status"] == "failed_open"
    assert telem["tuples_extracted"] == 0
    assert "_event_tuple" not in out[0]


# ---------------------------------------------------------------------------
# Live-API regression — gated on ANTHROPIC_API_KEY
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live event_tuples test",
)
def test_extract_event_tuples_live_resolves_4_27_conflations():
    """End-to-end live test: the four conflation cases from the 2026-04-27
    review must produce DISTINGUISHING tuples (not necessarily identical
    to a fixed gold standard, but the key fields must differ in the
    expected directions)."""
    import anthropic

    items = [
        {"headline": "Joint Statement following meeting between Abdullah bin Zayed, UK Foreign Secretary"},
        {"headline": "Abdullah bin Zayed, US Secretary of State discuss regional developments in phone call"},
        {"headline": "Vance cancels Pakistan trip as Iran withholds negotiators before ceasefire expiry"},
        {"headline": "Trump cancels US-Iran peace talks in Pakistan"},
        {"headline": "OpenAI releases GPT-5.5, its first fully retrained base model since GPT-4.5"},
        {"headline": "GPT-5.5 launched by OpenAI in Pro and Thinking modes with 1M context"},
    ]

    client = anthropic.AsyncAnthropic()
    out, telem = asyncio.run(extract_event_tuples(client, items))

    assert telem["status"] == "ok", f"extraction failed: {telem}"
    assert telem["tuples_extracted"] == len(items)

    # Bilateral conflation pair: counterpart MUST differ.
    abdullah_uk = out[0]["_event_tuple"]
    abdullah_us = out[1]["_event_tuple"]
    assert abdullah_uk["counterpart"] != abdullah_us["counterpart"], (
        f"Abdullah-UK and Abdullah-US must produce DIFFERENT counterparts; "
        f"got {abdullah_uk['counterpart']!r} vs {abdullah_us['counterpart']!r}"
    )

    # Principal-shift pair: primary_actor MUST differ.
    vance = out[2]["_event_tuple"]
    trump = out[3]["_event_tuple"]
    assert vance["primary_actor"] != trump["primary_actor"], (
        f"Vance and Trump cancellations must produce DIFFERENT primary_actors; "
        f"got {vance['primary_actor']!r} vs {trump['primary_actor']!r}"
    )

    # Paraphrase pair: event_type AND primary_actor MUST match.
    gpt55_a = out[4]["_event_tuple"]
    gpt55_b = out[5]["_event_tuple"]
    assert gpt55_a["event_type"] == gpt55_b["event_type"], (
        f"GPT-5.5 paraphrase pair must share event_type"
    )
    assert gpt55_a["primary_actor"] == gpt55_b["primary_actor"] == "OpenAI", (
        f"GPT-5.5 paraphrase pair must share primary_actor=OpenAI; "
        f"got {gpt55_a['primary_actor']!r} vs {gpt55_b['primary_actor']!r}"
    )
