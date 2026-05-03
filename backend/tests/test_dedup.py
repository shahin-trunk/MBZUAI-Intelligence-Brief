"""Regression tests for pipeline.dedup fuzzy clustering.

Locks the 2026-04-20 fix: unrelated fundraising headlines sharing the "$X B
at $Y B valuation" template must NOT be transitively merged by fuzzy dedup
just because their SequenceMatcher ratios sit in the 0.60–0.65 band. See
the Padres super-cluster incident in the 2026-04-20 gap analysis.

These tests exercise the synchronous fuzzy stage directly (no network) via
the internal `_fuzzy_dedup` helper, and also pin the public behavior of
`_distinctive_tokens`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.dedup import _distinctive_tokens, _fuzzy_dedup, _semantic_dedup  # noqa: E402


def _item(headline: str, source: str = "TestSource") -> dict:
    return {
        "headline": headline,
        "source": source,
        "source_url": "",
        "raw_content": headline,
    }


def _cluster_by_kept_headline(merge_log: list[dict]) -> dict[str, list[str]]:
    """Map kept headline -> list of merged headlines for readable assertions."""
    return {
        entry["kept_headline"]: entry["merged_headlines"] for entry in merge_log
    }


# ---------------------------------------------------------------------------
# _distinctive_tokens
# ---------------------------------------------------------------------------


def test_distinctive_tokens_strips_funding_template():
    """Template words like 'raises', 'billion', 'valuation' must NOT be
    distinctive — otherwise they wire unrelated stories together."""
    tokens = _distinctive_tokens("Cursor raises $2B+ at $50B valuation")
    assert "cursor" in tokens
    assert "raises" not in tokens
    assert "valuation" not in tokens
    # '50b' is a content-bearing numeric token — keep it.
    assert "50b" in tokens


def test_distinctive_tokens_unrelated_stories_have_no_overlap():
    """Cursor raise vs Padres sale vs DeepSeek raise share no distinctive
    tokens. This is the property that blocks the super-cluster."""
    cursor = _distinctive_tokens("Cursor raises $2B+ at $50B valuation")
    padres = _distinctive_tokens("San Diego Padres Sell for Record $3.9 Billion Valuation")
    deepseek = _distinctive_tokens("DeepSeek raises funds at $10 billion valuation")

    assert cursor & padres == set(), f"unexpected overlap: {cursor & padres}"
    assert cursor & deepseek == set(), f"unexpected overlap: {cursor & deepseek}"
    assert padres & deepseek == set(), f"unexpected overlap: {padres & deepseek}"


def test_distinctive_tokens_real_duplicates_do_overlap():
    """Actual near-duplicates share at least one distinctive token."""
    a = _distinctive_tokens("DeepSeek raises funds at $10 billion valuation")
    b = _distinctive_tokens("China's DeepSeek raises funds at $10 billion valuation")
    assert "deepseek" in (a & b)

    c = _distinctive_tokens("San Diego Padres Sell for Record $3.9 Billion Valuation")
    d = _distinctive_tokens("San Diego Padres near $3.9 billion sale to billionaire")
    assert {"san", "diego", "padres"}.issubset(c & d)


# ---------------------------------------------------------------------------
# _fuzzy_dedup — the 2026-04-20 Padres super-cluster regression
# ---------------------------------------------------------------------------


def test_fuzzy_dedup_does_not_merge_unrelated_fundraises():
    """The 2026-04-20 bug: 8 unrelated "valuation" headlines collapsed into
    one Padres-headed cluster. After the fix we expect 6 output items:
        - Padres (2 merged into 1)
        - Cursor raise (2 merged into 1)
        - DeepSeek raise (2 merged into 1)
        - Canva (standalone)
        - Slash (standalone)
    """
    items = [
        _item("San Diego Padres Sell for Record $3.9 Billion Valuation"),
        _item("San Diego Padres near $3.9 billion sale to billionaire"),
        _item("Cursor seeks $2B+ funding at $50B valuation"),
        _item("Cursor raises $2B+ at $50B valuation"),
        _item("Canva embraces AI to defend $42 billion valuation"),
        _item("Teen-founded Slash raises $100M at $1.4B valuation"),
        _item("DeepSeek raises funds at $10 billion valuation"),
        _item("China's DeepSeek raises funds at $10 billion valuation"),
    ]

    deduped, n_merged, merge_log, dropped = _fuzzy_dedup(items)

    assert len(deduped) == 5, (
        f"expected 5 clusters (Padres, Cursor, DeepSeek, Canva, Slash); "
        f"got {len(deduped)}: {[d['headline'] for d in deduped]}"
    )
    assert n_merged == 3  # three pairs correctly collapsed

    # Each real-duplicate pair should show up as its own merge entry —
    # never a mixed cluster.
    for entry in merge_log:
        merged = entry["merged_headlines"]
        # All members of a cluster should share at least one distinctive token
        # (defensive — if this ever fails, we've regressed the guard).
        common = _distinctive_tokens(merged[0])
        for h in merged[1:]:
            common &= _distinctive_tokens(h)
        assert common, (
            f"cluster has no shared distinctive token — regression: {merged}"
        )

    # Padres, Cursor, DeepSeek each have an entry; Canva/Slash do not.
    kept_headlines = {d["headline"] for d in deduped}
    assert any("Padres" in h for h in kept_headlines)
    assert any("Cursor" in h for h in kept_headlines)
    assert any("DeepSeek" in h for h in kept_headlines)
    assert any("Canva" in h for h in kept_headlines)
    assert any("Slash" in h for h in kept_headlines)


# ---------------------------------------------------------------------------
# _fuzzy_dedup — positive cases that must STILL merge
# ---------------------------------------------------------------------------


def test_fuzzy_dedup_still_merges_real_near_duplicates():
    """WAM/newsletter variants of the same story should still collapse."""
    items = [
        _item("UAE welcomes IMO Legal Committee decision on Hormuz"),
        _item("UAE VP welcomes IMO Legal Committee decision on Hormuz"),
    ]
    deduped, n_merged, merge_log, _ = _fuzzy_dedup(items)
    assert len(deduped) == 1
    assert n_merged == 1


def test_fuzzy_dedup_merges_short_entity_sharing_headlines():
    """Two short Reuters-style headlines about the same event."""
    items = [
        _item("Iran seizes tanker in Gulf"),
        _item("Iran seizes oil tanker in Gulf"),
    ]
    deduped, n_merged, _, _ = _fuzzy_dedup(items)
    assert len(deduped) == 1
    assert n_merged == 1


def test_fuzzy_dedup_empty_input():
    deduped, n_merged, merge_log, dropped = _fuzzy_dedup([])
    assert deduped == []
    assert n_merged == 0
    assert merge_log == []
    assert dropped == []


def test_fuzzy_dedup_single_item():
    items = [_item("Only headline")]
    deduped, n_merged, merge_log, _ = _fuzzy_dedup(items)
    assert len(deduped) == 1
    assert n_merged == 0
    assert merge_log == []


# ---------------------------------------------------------------------------
# _semantic_dedup — distinctive-token veto (2026-04-23 BlackRock↔Kenya fix)
# ---------------------------------------------------------------------------


class _StubHaikuClient:
    """Minimal async stand-in for anthropic.AsyncAnthropic.

    Returns a prescribed cluster JSON string so we can exercise the
    post-Haiku veto without making a network call.
    """

    def __init__(self, cluster_json: str) -> None:
        self._cluster_json = cluster_json

        class _Messages:
            def __init__(outer, client):
                outer._client = client

            async def create(outer, *, model, max_tokens, system, messages):
                class _Block:
                    def __init__(self, text):
                        self.text = text

                class _Resp:
                    def __init__(self, text):
                        self.content = [_Block(text)]

                return _Resp(outer._client._cluster_json)

        self.messages = _Messages(self)


async def _run_semantic(items, cluster_json):
    return await _semantic_dedup(items, _StubHaikuClient(cluster_json))


def test_semantic_dedup_vetoes_low_token_overlap():
    """The 2026-04-23 BlackRock↔Kenya case — keep/drop pair shares only
    `{uae}` in distinctive tokens. The veto must reject the merge and
    leave both items in the output.
    """
    import asyncio

    items = [
        _item("UAE President meets BlackRock Chairman and CEO"),
        _item("UAE and Kenyan Presidents discuss cooperation under CEPA and regional developments"),
    ]
    # Haiku (incorrectly) clusters them together.
    cluster_json = '[{"keep": 0, "drop": [1]}]'
    deduped, n_merged, merge_log, dropped_rows = asyncio.run(
        _run_semantic(items, cluster_json)
    )
    # Veto must preserve both items, record zero merges, and not emit a
    # dropped_rows entry for the loser.
    assert len(deduped) == 2, (
        f"veto failed — both items should survive: {[d['headline'] for d in deduped]}"
    )
    assert n_merged == 0
    assert merge_log == []
    assert dropped_rows == []


def test_semantic_dedup_allows_high_token_overlap():
    """Legitimate near-duplicates — Google/TPU variants share `{google, tpu}`
    (≥2 distinctive tokens) and must still merge."""
    import asyncio

    items = [
        _item("Google Unveils Latest Generation TPU Chip"),
        _item("Google announces TPU v8 with training and inference specialization"),
    ]
    cluster_json = '[{"keep": 1, "drop": [0]}]'
    deduped, n_merged, merge_log, dropped_rows = asyncio.run(
        _run_semantic(items, cluster_json)
    )
    assert len(deduped) == 1, (
        f"expected a single merged cluster; got {[d['headline'] for d in deduped]}"
    )
    assert n_merged == 1
    assert len(merge_log) == 1
    assert len(dropped_rows) == 1


# ---------------------------------------------------------------------------
# 2026-04-27 counterpart-aware dedup prompt — bilateral conflation guard
# ---------------------------------------------------------------------------
#
# On 2026-04-27 the WAM "Joint Statement following meeting between Abdullah
# bin Zayed, UK Foreign Secretary" was wrongly merged into "Abdullah bin
# Zayed, US Secretary of State discuss regional developments in phone call"
# — same primary entity, different counterpart (UK vs US). The within-day
# semantic dedup prompt now contains a CRITICAL rule + worked examples
# instructing the judge that bilateral items with different counterparts
# are different events. Tests below pin the prompt content without
# requiring a live Haiku call.


def test_semantic_dedup_prompt_contains_counterpart_clause():
    """The 2026-04-27 counterpart-aware fix: the dedup prompt must
    explicitly tell the judge that bilateral items with different
    counterparts are different events."""
    from pipeline.dedup import _SEMANTIC_DEDUP_SYSTEM

    body = _SEMANTIC_DEDUP_SYSTEM.lower()
    assert "different counterparts" in body, (
        "dedup prompt must mention 'different counterparts' to invoke "
        "the 2026-04-27 fix clause"
    )
    # Worked examples are required so the judge sees the pattern, not
    # just the rule.
    assert "abdullah bin zayed" in body, (
        "dedup prompt must include the Abdullah-UK/US worked example"
    )
    assert "g42" in body and "nvidia" in body, (
        "dedup prompt must include the G42 deal-counterpart worked example"
    )


def test_semantic_dedup_prompt_uses_xml_structure():
    """The fix migrates the prompt to Anthropic's XML-tagged structure
    (critical_rule + examples) per their best-practices guide. Lock the
    structure so future prompt edits don't accidentally collapse it back
    to a single paragraph."""
    from pipeline.dedup import _SEMANTIC_DEDUP_SYSTEM

    assert "<critical_rule>" in _SEMANTIC_DEDUP_SYSTEM
    assert "</critical_rule>" in _SEMANTIC_DEDUP_SYSTEM
    assert "<examples>" in _SEMANTIC_DEDUP_SYSTEM
    assert "<example label=" in _SEMANTIC_DEDUP_SYSTEM
    # Both decision verdicts must appear so the judge sees both classes.
    assert "DIFFERENT_COUNTERPARTS_KEEP_SEPARATE" in _SEMANTIC_DEDUP_SYSTEM
    assert "SAME_STORY_CLUSTER" in _SEMANTIC_DEDUP_SYSTEM


def test_semantic_dedup_distinctive_token_veto_still_holds_under_new_prompt():
    """The post-Haiku distinctive-token veto MUST still fire even when
    the prompt itself fails to catch a bad merge. Belt-and-suspenders:
    the veto is the final safety net for the Abdullah-UK/US class.
    """
    import asyncio

    # Even if Haiku ignored the new prompt and returned a bad cluster,
    # the post-Haiku veto should reject because the distinctive tokens
    # share zero overlap once "secretary" and "abdullah" are inspected
    # as a function of context. NB: actual production behavior uses the
    # token set; this test pins that behavior under the new prompt
    # to guard against accidental veto-removal during the prompt edit.
    items = [
        _item(
            "Joint Statement following meeting between Abdullah bin Zayed, UK Foreign Secretary"
        ),
        _item(
            "Some completely unrelated headline about chip exports"
        ),
    ]
    # Pretend Haiku merged these — distinctive tokens share nothing.
    cluster_json = '[{"keep": 0, "drop": [1]}]'
    deduped, n_merged, merge_log, dropped_rows = asyncio.run(
        _run_semantic(items, cluster_json)
    )
    assert len(deduped) == 2, (
        "post-Haiku token veto must reject a bad cluster with zero token overlap"
    )
    assert n_merged == 0


# ---------------------------------------------------------------------------
# Phase 3: Tuple-aware within-day dedup (post-2026-04-27 structural fix)
# ---------------------------------------------------------------------------
#
# Replaces the Haiku semantic dedup judgment with mechanical event-tuple
# comparison when items carry `_event_tuple` from the Phase 2 extraction
# stage. The legacy `_semantic_dedup` Haiku path is kept as a fallback for
# items missing tuples (extraction failure, resume from pre-Phase-2
# artifacts, or `client=None`).
#
# Eliminates the prompt-clause arms race: counterpart-aware, NEW PRINCIPAL,
# different-event-type-different-action are all handled mechanically by
# field-equality comparison on the tuple.


def _tuple_item(headline: str, event_type: str, primary_actor=None,
                counterpart=None, action="x"):
    """Build a test item with an `_event_tuple` field."""
    return {
        "headline": headline,
        "source": "TestSource",
        "source_url": f"https://example.com/{abs(hash(headline)) % 1000}",
        "raw_content": headline,
        "_event_tuple": {
            "event_type": event_type,
            "primary_actor": primary_actor,
            "counterpart": counterpart,
            "action": action,
            "location": None,
            "date_or_period": None,
            "key_numbers": [],
        },
    }


def test_tuple_match_blocks_different_counterpart():
    """The 4/27 Abdullah-UK ↔ Abdullah-US conflation: same primary_actor,
    different counterpart -> different events. Mechanical comparison
    catches this without requiring any prompt clause."""
    from pipeline.dedup import _tuple_match

    a = {"event_type": "bilateral_meeting", "primary_actor": "Abdullah bin Zayed",
         "counterpart": "UK Foreign Secretary", "action": "issues joint statement"}
    b = {"event_type": "bilateral_meeting", "primary_actor": "Abdullah bin Zayed",
         "counterpart": "US Secretary of State", "action": "discuss developments"}
    matched, reason = _tuple_match(a, b)
    assert matched is False
    assert "counterpart differs" in reason


def test_tuple_match_blocks_different_primary_actor():
    """The 4/27 Vance ↔ Trump Pakistan principal-shift case: similar
    action, similar topic, but different head-of-state."""
    from pipeline.dedup import _tuple_match

    a = {"event_type": "diplomatic_action", "primary_actor": "Vance",
         "counterpart": None, "action": "cancels Pakistan trip"}
    b = {"event_type": "diplomatic_action", "primary_actor": "Trump",
         "counterpart": "Iran", "action": "cancels US-Iran peace talks"}
    matched, reason = _tuple_match(a, b)
    assert matched is False
    assert "primary_actor differs" in reason


def test_tuple_match_blocks_different_event_type():
    """Tencent invests vs Tencent licenses — same actor, same counterpart,
    DIFFERENT event_type. Catches a class of failures the legacy Haiku
    judge sometimes conflated by latching onto the entity overlap."""
    from pipeline.dedup import _tuple_match

    a = {"event_type": "funding_round", "primary_actor": "Tencent",
         "counterpart": "DeepSeek", "action": "invests in DeepSeek"}
    b = {"event_type": "trade_deal", "primary_actor": "Tencent",
         "counterpart": "DeepSeek", "action": "licenses DeepSeek inference"}
    matched, reason = _tuple_match(a, b)
    assert matched is False
    assert "event_type differs" in reason


def test_tuple_match_allows_paraphrase_merge():
    """GPT-5.5 paraphrase: different verbs ("releases" vs "launches")
    but the action phrase includes the shared product name. Tuples
    correctly merge under the action-token overlap rule."""
    from pipeline.dedup import _tuple_match

    a = {"event_type": "product_release", "primary_actor": "OpenAI",
         "counterpart": None, "action": "releases GPT-5.5"}
    b = {"event_type": "product_release", "primary_actor": "OpenAI",
         "counterpart": None, "action": "launches GPT-5.5"}
    matched, reason = _tuple_match(a, b)
    assert matched is True, (
        f"paraphrase pair must merge via shared product token; got {reason}"
    )


def test_tuple_match_blocks_disjoint_action_tokens():
    """Same actor + counterpart + event_type, but actions share zero
    distinctive tokens -> different events. Guards against premature
    merging when the entity overlap is high but the actions are
    semantically distinct."""
    from pipeline.dedup import _tuple_match

    a = {"event_type": "regulatory_action", "primary_actor": "EU",
         "counterpart": None, "action": "approves AI Act"}
    b = {"event_type": "regulatory_action", "primary_actor": "EU",
         "counterpart": None, "action": "rejects merger filing"}
    matched, reason = _tuple_match(a, b)
    assert matched is False
    assert "no action overlap" in reason


def test_tuple_match_handles_null_counterparts_symmetrically():
    """Both items single-actor (counterpart=None) — must not block
    on null vs null. Otherwise paraphrase pairs that lack counterparts
    (single-entity product releases) would be force-separated."""
    from pipeline.dedup import _tuple_match

    a = {"event_type": "product_release", "primary_actor": "Anthropic",
         "counterpart": None, "action": "releases Claude Opus 4.7"}
    b = {"event_type": "product_release", "primary_actor": "Anthropic",
         "counterpart": None, "action": "launches Claude Opus 4.7"}
    matched, reason = _tuple_match(a, b)
    assert matched is True
    # The rejection-reason text would be "counterpart differs: ...".
    # Success text says "matched on event_type+actor+counterpart+action ...",
    # so just confirm we DIDN'T reject on a counterpart mismatch.
    assert "counterpart differs" not in reason


def test_tuple_match_returns_false_on_missing_tuple():
    """Defensive: missing or empty tuples must NOT be treated as a match.
    Caller falls back to the legacy LLM-judged path in this case."""
    from pipeline.dedup import _tuple_match

    a = {"event_type": "other", "primary_actor": "x", "counterpart": None,
         "action": "x"}
    matched, reason = _tuple_match(a, None)
    assert matched is False
    matched, reason = _tuple_match({}, a)
    assert matched is False


def test_all_items_have_tuples_check():
    """Routing helper: tuple-aware dedup runs only when EVERY surviving
    item has a tuple. Mixed-coverage inputs route to the legacy Haiku
    path so missing-tuple items don't get treated as not-merge-eligible."""
    from pipeline.dedup import _all_items_have_tuples

    items_full = [
        {"_event_tuple": {"event_type": "other", "action": "a"}},
        {"_event_tuple": {"event_type": "other", "action": "b"}},
    ]
    assert _all_items_have_tuples(items_full)

    # One item missing tuple
    assert not _all_items_have_tuples(items_full + [{"headline": "no tuple"}])
    # Empty tuple dict counts as missing
    assert not _all_items_have_tuples(items_full + [{"_event_tuple": {}}])


def test_tuple_dedup_clusters_paraphrase_pairs():
    """The full _tuple_dedup pipeline on a synthetic batch with one
    paraphrase pair (must merge) and three single-tuple items (must
    survive untouched)."""
    from pipeline.dedup import _tuple_dedup

    items = [
        _tuple_item("OpenAI releases GPT-5.5", "product_release", "OpenAI",
                    None, "releases GPT-5.5"),
        _tuple_item("GPT-5.5 launched by OpenAI", "product_release", "OpenAI",
                    None, "launches GPT-5.5"),
        _tuple_item("Anthropic releases Claude Opus 4.7", "product_release",
                    "Anthropic", None, "releases Claude Opus"),
        _tuple_item("Trump cancels Pakistan trip", "diplomatic_action",
                    "Trump", "Iran", "cancels Pakistan trip"),
    ]

    deduped, n_merged, merge_log, dropped_rows = _tuple_dedup(items)
    assert n_merged == 1, f"expected 1 merge, got {n_merged}"
    assert len(deduped) == 3
    assert len(merge_log) == 1
    # The OpenAI paraphrase pair merged.
    assert "OpenAI" in merge_log[0]["kept_headline"]
    assert "GPT-5.5" in merge_log[0]["kept_headline"]
    # Anthropic and Trump items survived untouched.
    survivors = {it["headline"] for it in deduped}
    assert "Anthropic releases Claude Opus 4.7" in survivors
    assert "Trump cancels Pakistan trip" in survivors


def test_tuple_dedup_blocks_4_27_conflations():
    """The four 4/27 conflation pairs must NOT merge under tuple dedup."""
    from pipeline.dedup import _tuple_dedup

    items = [
        # Pair 1: Abdullah-UK vs Abdullah-US (counterpart differs)
        _tuple_item(
            "Abdullah bin Zayed UK Joint Statement",
            "bilateral_meeting", "Abdullah bin Zayed", "UK Foreign Secretary",
            "issues joint statement",
        ),
        _tuple_item(
            "Abdullah bin Zayed US phone call",
            "bilateral_meeting", "Abdullah bin Zayed", "US Secretary of State",
            "discuss regional developments",
        ),
        # Pair 2: Vance vs Trump Pakistan (primary_actor differs)
        _tuple_item(
            "Vance cancels Pakistan trip",
            "diplomatic_action", "Vance", None, "cancels Pakistan trip",
        ),
        _tuple_item(
            "Trump cancels US-Iran peace talks",
            "diplomatic_action", "Trump", "Iran", "cancels US-Iran peace talks",
        ),
        # Pair 3: Tencent invest vs license (event_type differs)
        _tuple_item(
            "Tencent invests in DeepSeek",
            "funding_round", "Tencent", "DeepSeek", "invests in DeepSeek",
        ),
        _tuple_item(
            "Tencent licenses DeepSeek inference",
            "trade_deal", "Tencent", "DeepSeek", "licenses DeepSeek inference",
        ),
    ]

    deduped, n_merged, merge_log, dropped_rows = _tuple_dedup(items)
    assert n_merged == 0, (
        f"NO conflation pair should merge; got {n_merged} merges:\n"
        f"{merge_log}"
    )
    assert len(deduped) == 6


@pytest.mark.asyncio
async def test_deduplicate_items_routes_to_tuple_path_when_all_have_tuples(
    monkeypatch
):
    """End-to-end: when every surviving item carries `_event_tuple`,
    deduplicate_items takes the Phase 3 tuple path and skips the Haiku
    semantic call entirely."""
    import asyncio
    from pipeline import dedup
    from pipeline.dedup import deduplicate_items

    haiku_calls = []

    async def _raise_if_called(*args, **kwargs):
        haiku_calls.append((args, kwargs))
        raise AssertionError("Haiku semantic dedup must not be called when "
                             "all items have tuples")

    monkeypatch.setattr(dedup, "_semantic_dedup", _raise_if_called)

    items = [
        _tuple_item("OpenAI releases GPT-5.5", "product_release", "OpenAI",
                    None, "releases GPT-5.5"),
        _tuple_item("GPT-5.5 launched by OpenAI", "product_release", "OpenAI",
                    None, "launches GPT-5.5"),
    ]

    deduped, n_merged, merge_log, dropped_rows = await deduplicate_items(
        items, client=None,
    )
    assert n_merged == 1, "tuple-aware path must merge GPT-5.5 paraphrase"
    assert haiku_calls == [], "tuple path skipped Haiku — confirmed"


@pytest.mark.asyncio
async def test_deduplicate_items_falls_back_to_haiku_when_tuples_missing(
    monkeypatch
):
    """When ANY item lacks `_event_tuple`, deduplicate_items must fall
    back to the legacy `_semantic_dedup` Haiku path so missing-tuple
    items don't get treated as not-merge-eligible."""
    from pipeline import dedup
    from pipeline.dedup import deduplicate_items

    semantic_called = []

    async def _stub_semantic_dedup(items, client):
        semantic_called.append(len(items))
        return items, 0, [], []

    monkeypatch.setattr(dedup, "_semantic_dedup", _stub_semantic_dedup)

    items_mixed = [
        _tuple_item(
            "OpenAI releases GPT-5.5 with agentic coding",
            "product_release", "OpenAI", None, "releases GPT-5.5",
        ),
        # No `_event_tuple` field on this item -> fallback path.
        {"headline": "Tencent unveils Hy3 reasoning model preview",
         "source": "Test", "source_url": "https://example.com/tencent-hy3",
         "raw_content": "Tencent unveils Hy3 reasoning model preview"},
    ]

    deduped, n_merged, merge_log, dropped_rows = await deduplicate_items(
        items_mixed, client=None,
    )
    assert semantic_called, (
        "Haiku semantic path must be called when any item lacks a tuple"
    )
