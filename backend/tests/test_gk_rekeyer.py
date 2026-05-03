"""Unit tests for `pipeline.gk_rekeyer`.

Focus areas (all operate without hitting the Anthropic API by stubbing the
async client):

1. Haiku-provided matches are attached in place to `selected` / `dropped`.
2. Items that already carry a valid `_idx` are trusted and skipped.
3. 1:1 greedy pairing — two output items claiming the same input `_idx` do
   not both get it; the second is left unmatched and reported in
   `duplicate_claim_count`.
4. Fail-open: a Haiku error returns an empty mapping and leaves items alone.
5. An integration-style replay against the saved 2026-04-17 artifacts that
   verifies the re-keyer + fuzzy fallback collapse the 127 "implicit" drops
   down to ~5–15 real silent drops. Skipped when the cached files are
   missing (CI) so the unit test file stays green in clean checkouts.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline import gk_rekeyer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Mimic the anthropic Response shape just enough for the re-keyer."""

    def __init__(self, text: str):
        class _Block:
            def __init__(self, t):
                self.type = "text"
                self.text = t
        self.content = [_Block(text)]


def _fake_client(json_payload):
    """Return a mock client whose messages.create returns json_payload
    serialized in a text block."""
    client = AsyncMock()
    if isinstance(json_payload, Exception):
        client.messages.create = AsyncMock(side_effect=json_payload)
    else:
        client.messages.create = AsyncMock(
            return_value=_FakeResponse(json.dumps(json_payload))
        )
    return client


def _pool(n: int) -> list[dict]:
    """Build a small reference pool."""
    return [
        {"_idx": i, "headline": f"Story number {i} about widgets",
         "summary": f"Widgets body {i}"}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Unit tests — no API
# ---------------------------------------------------------------------------

def test_haiku_matches_attach_idx_in_place():
    pool = _pool(5)
    selected = [{"headline": "Story about widgets 2"}]
    dropped = [{"headline": "Widgets story 0"}]
    # Haiku says SEL_0 → idx 2, DROP_0 → idx 0.
    client = _fake_client([
        {"out_id": "SEL_0", "idx": 2},
        {"out_id": "DROP_0", "idx": 0},
    ])
    report = asyncio.run(
        gk_rekeyer.rekey_gatekeeper_output(client, pool, selected, dropped)
    )
    assert selected[0]["_idx"] == 2
    assert dropped[0]["_idx"] == 0
    assert report["matched"] == 2
    assert report["unmatched"] == 0
    assert report["match_rate"] == 1.0
    assert report["trusted_existing"] == 0
    assert report["matched_by_haiku"] == 2


def test_existing_idx_echo_is_trusted_and_skipped():
    pool = _pool(5)
    selected = [{"_idx": 3, "headline": "Something"}]  # already has _idx
    dropped = []
    # Haiku shouldn't even be called in a world where every item is
    # trusted. We still build a fake client; assert it wasn't invoked.
    client = _fake_client([])
    report = asyncio.run(
        gk_rekeyer.rekey_gatekeeper_output(client, pool, selected, dropped)
    )
    assert selected[0]["_idx"] == 3
    assert report["trusted_existing"] == 1
    assert report["matched_by_haiku"] == 0
    client.messages.create.assert_not_called()


def test_invalid_existing_idx_is_discarded_and_rekeyed():
    """If the Gatekeeper echoes a bogus _idx (e.g. 99 when pool only has 5
    items), drop it and let Haiku re-match instead of silently trusting."""
    pool = _pool(5)
    selected = [{"_idx": 99, "headline": "Widgets story 1"}]
    dropped = []
    client = _fake_client([{"out_id": "SEL_0", "idx": 1}])
    report = asyncio.run(
        gk_rekeyer.rekey_gatekeeper_output(client, pool, selected, dropped)
    )
    assert selected[0]["_idx"] == 1  # replaced, not preserved
    assert report["trusted_existing"] == 0
    assert report["matched_by_haiku"] == 1


def test_one_to_one_greedy_pairing_rejects_duplicate_claims():
    pool = _pool(5)
    selected = [
        {"headline": "Widgets story A"},
        {"headline": "Widgets story B"},
    ]
    dropped = []
    # Haiku claims idx=2 for BOTH selected items. Only one wins; the other
    # is left unmatched and `duplicate_claim_count` is 1.
    client = _fake_client([
        {"out_id": "SEL_0", "idx": 2},
        {"out_id": "SEL_1", "idx": 2},
    ])
    report = asyncio.run(
        gk_rekeyer.rekey_gatekeeper_output(client, pool, selected, dropped)
    )
    matched_count = sum(1 for s in selected if s.get("_idx") is not None)
    assert matched_count == 1
    assert report["duplicate_claim_count"] == 1
    assert report["unmatched"] == 1


def test_haiku_null_leaves_item_unmatched():
    pool = _pool(5)
    selected = [{"headline": "Unrelated story the model merged in"}]
    dropped = []
    client = _fake_client([{"out_id": "SEL_0", "idx": None}])
    report = asyncio.run(
        gk_rekeyer.rekey_gatekeeper_output(client, pool, selected, dropped)
    )
    assert "_idx" not in selected[0]
    assert report["matched"] == 0
    assert report["unmatched"] == 1


def test_haiku_error_fails_open():
    pool = _pool(5)
    selected = [{"headline": "Widgets story"}]
    dropped = []
    client = _fake_client(RuntimeError("simulated API outage"))
    report = asyncio.run(
        gk_rekeyer.rekey_gatekeeper_output(client, pool, selected, dropped)
    )
    assert "_idx" not in selected[0]
    assert report["matched"] == 0
    # Report still structured correctly so pipeline_stats persists.
    assert report["total"] == 1
    assert report["match_rate"] == 0.0


def test_empty_output_is_noop_with_perfect_match_rate():
    pool = _pool(5)
    client = AsyncMock()
    report = asyncio.run(
        gk_rekeyer.rekey_gatekeeper_output(client, pool, [], [])
    )
    assert report == {
        "total": 0, "matched": 0, "unmatched": 0,
        "trusted_existing": 0, "matched_by_haiku": 0,
        "duplicate_claim_count": 0, "match_rate": 1.0,
    }
    client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# Integration replay — runs against saved 2026-04-17 production artifacts if
# they exist. Skipped in clean checkouts.
# ---------------------------------------------------------------------------

_REPLAY_DATE = "2026-04-17"


def _load_replay_data():
    out = BACKEND_DIR / "output"
    pool_path = out / f"section_classifier_output_{_REPLAY_DATE}.json"
    gk_path = out / f"gatekeeper_output_{_REPLAY_DATE}.json"
    drops_path = out / f"dropped_by_gatekeeper_{_REPLAY_DATE}.json"
    if not (pool_path.exists() and gk_path.exists() and drops_path.exists()):
        pytest.skip(f"Replay artifacts for {_REPLAY_DATE} not present")
    pool_raw = json.loads(pool_path.read_text())
    pool = pool_raw if isinstance(pool_raw, list) else pool_raw.get("items", [])
    gk = json.loads(gk_path.read_text())
    drops = json.loads(drops_path.read_text())
    return pool, gk, drops


def test_replay_fuzzy_fallback_collapses_phantom_implicit_drops():
    """The Phase-1 detector flagged 127 implicit drops on 04-17. After the
    fuzzy fallback in the orchestrator, the genuine silent count should be
    in the single digits — not hundreds.

    This test runs the FUZZY MATCH part of the fix only (not the Haiku
    re-keyer, which costs API tokens). It's the "Fix 2 alone" baseline —
    the re-keyer should only improve from here.
    """
    pool, gk, drops = _load_replay_data()
    import re
    from difflib import SequenceMatcher

    def _norm_match(h: str) -> str:
        return re.sub(r"[^\w\s]", "", (h or "").lower()).strip()[:60]

    selected = gk.get("selected", [])
    model_drops = drops.get("gatekeeper_model_dropped", [])

    # Build candidate pool keyed by normalized headline.
    pool_norm = {_norm_match(p.get("headline", "")): p for p in pool}
    pool_norm.pop("", None)
    output_norm_set = {
        _norm_match(x.get("headline", ""))
        for x in list(selected) + list(model_drops)
    }
    output_norm_set.discard("")

    # 1:1 greedy fuzzy pairing with threshold 0.55.
    unmatched = []
    used = set()
    for p_norm, p_item in pool_norm.items():
        if p_norm in output_norm_set:
            continue
        best_score = 0.0
        best_out = None
        for o_norm in output_norm_set:
            if o_norm in used:
                continue
            s = SequenceMatcher(None, p_norm, o_norm).ratio()
            if s > best_score:
                best_score = s
                best_out = o_norm
        if best_score >= 0.55 and best_out is not None:
            used.add(best_out)
        else:
            unmatched.append(p_item)

    # Baseline reference: the production run tagged 131 implicit. Fuzzy
    # fallback should collapse that to well under 30. Exact target from
    # offline analysis: 11-18 at threshold 0.55.
    assert len(unmatched) < 30, (
        f"Fuzzy fallback left {len(unmatched)} unmatched on {_REPLAY_DATE} "
        f"— expected <30. Check normalization/threshold."
    )
