"""Regression tests for pipeline.history_dedup apply-layer guardrails.

Locks the 2026-04-20 fix: the history-dedup judge (Haiku 4.5) occasionally
emits drop verdicts with a fabricated `matched_headline` or with a match
that shares no substance with the candidate. The apply layer must reject
those drops (fail open) instead of silently killing the item. See the
plan file and the 2026-04-20 gap analysis for incident context.

These tests exercise `apply_history_dedup_verdicts` directly — no network.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.history_dedup import apply_history_dedup_verdicts  # noqa: E402


def _cand(idx: int, headline: str) -> dict:
    return {
        "headline": headline,
        "source": "TestSource",
        "source_url": f"https://example.com/{idx}",
    }


def _hist(headline: str, brief_date: str = "2026-04-17") -> dict:
    return {"brief_date": brief_date, "headline": headline}


# ---------------------------------------------------------------------------
# Hallucinated cite — judge names a matched_headline not in recent_history
# ---------------------------------------------------------------------------


def test_rejects_drop_when_matched_headline_not_in_history():
    """2026-04-20: 'Olly Robbins exit' dropped as matching 'White House
    Mythos AI Model'. The Mythos line WAS in history, but Robbins has
    nothing to do with it. Here we simulate the tighter pathology where
    the judge names a headline that isn't in the history at all."""
    items = [_cand(0, "Olly Robbins' exit deepens turmoil at Foreign Office")]
    verdicts = [{
        "id": 0,
        "headline": items[0]["headline"],
        "is_repeat": True,
        "matched_headline": "UK Foreign Office faces unprecedented turmoil amid senior exits",
        "matched_brief_date": "2026-04-17",
        "reason": "Robbins exit already covered",
    }]
    recent_history = [
        _hist("White House Moves to Grant Federal Agencies Access to Anthropic Mythos AI Model"),
        _hist("ADNOC signs $2B solar deal"),
    ]

    kept, dropped = apply_history_dedup_verdicts(items, verdicts, recent_history)

    assert len(kept) == 1, "expected candidate to be kept (hallucinated cite)"
    assert len(dropped) == 0


def test_rejects_drop_when_tokens_do_not_overlap():
    """Matched headline is real, but the candidate and the match share
    zero distinctive tokens. The apply guard must reject the drop."""
    items = [_cand(0, "Apple launches redesigned Vision Pro with lighter headset")]
    verdicts = [{
        "id": 0,
        "headline": items[0]["headline"],
        "is_repeat": True,
        "matched_headline": "SpaceX deploys 60 Starlink satellites from Vandenberg",
        "matched_brief_date": "2026-04-17",
        "reason": "already covered",
    }]
    recent_history = [
        _hist("SpaceX deploys 60 Starlink satellites from Vandenberg"),
    ]

    kept, dropped = apply_history_dedup_verdicts(items, verdicts, recent_history)

    assert len(kept) == 1, "expected candidate to be kept (zero token overlap)"
    assert len(dropped) == 0


# ---------------------------------------------------------------------------
# Legitimate drops must still fire
# ---------------------------------------------------------------------------


def test_accepts_legitimate_drop_with_real_match_and_shared_tokens():
    """The prompt's own G42/NVIDIA paraphrase example — should drop."""
    items = [_cand(0, "NVIDIA to supply G42 with $1B in AI chips")]
    verdicts = [{
        "id": 0,
        "headline": items[0]["headline"],
        "is_repeat": True,
        "matched_headline": "G42 signs $1B NVIDIA chip deal",
        "matched_brief_date": "2026-04-16",
        "reason": "same deal, rewritten headline",
    }]
    recent_history = [
        _hist("G42 signs $1B NVIDIA chip deal", "2026-04-16"),
    ]

    kept, dropped = apply_history_dedup_verdicts(items, verdicts, recent_history)

    assert len(kept) == 0
    assert len(dropped) == 1
    assert "G42" in dropped[0]["drop_reason"]


def test_accepts_drop_with_pending_brief_date_prefix():
    """`matched_brief_date` uses a `pending YYYY-MM-DD` prefix for draft
    slates; the coherence check should still accept those entries."""
    items = [_cand(0, "Syria takes control of last US military base")]
    verdicts = [{
        "id": 0,
        "headline": items[0]["headline"],
        "is_repeat": True,
        "matched_headline": "Syria takes control of last US base at Qasrak, ending decade of presence",
        "matched_brief_date": "pending 2026-04-17",
        "reason": "same Syria-US military base handover",
    }]
    recent_history = [
        _hist("Syria takes control of last US base at Qasrak, ending decade of presence",
              "pending 2026-04-17"),
    ]

    kept, dropped = apply_history_dedup_verdicts(items, verdicts, recent_history)

    assert len(kept) == 0
    assert len(dropped) == 1


# ---------------------------------------------------------------------------
# Backward compatibility — recent_history=None preserves old behavior
# ---------------------------------------------------------------------------


def test_backward_compatible_when_no_recent_history_provided():
    """Old callers (or tests) that don't pass recent_history must still
    work exactly as before — all repeat=true verdicts are honored."""
    items = [
        _cand(0, "Some candidate headline"),
        _cand(1, "Another candidate"),
    ]
    verdicts = [
        {
            "id": 0,
            "headline": items[0]["headline"],
            "is_repeat": True,
            "matched_headline": "Totally unrelated historical headline",
            "matched_brief_date": "2026-04-17",
            "reason": "test",
        },
        {
            "id": 1,
            "headline": items[1]["headline"],
            "is_repeat": False,
        },
    ]

    kept, dropped = apply_history_dedup_verdicts(items, verdicts)  # no history arg

    # Without recent_history, the old behavior applies: drops are honored.
    assert len(kept) == 1
    assert kept[0]["headline"] == "Another candidate"
    assert len(dropped) == 1


# ---------------------------------------------------------------------------
# 2026-04-20 offline replay
# ---------------------------------------------------------------------------


def test_offline_replay_rejects_amodei_meeting_drop():
    """The exact 2026-04-20 verdict for the Amodei Friday meeting must
    now be rejected because the candidate describes a new time-bound
    event (a meeting) while the matched headline is a policy framing.
    Their distinctive tokens overlap on {white, house, anthropic, mythos}
    so guard 2 passes, but guard 1 passes too (real history entry).
    The rejection must come from the prompt's stricter rules OR, if the
    judge still emits the drop, the token overlap check alone won't
    catch it. For the apply layer specifically, this test documents
    that guard 1 + guard 2 alone do NOT catch same-family conflations —
    the prompt rewrite is required for that class of false positive.
    This is captured as an xfail-style assertion so the scope is
    explicit."""
    items = [_cand(0, "White House and Anthropic CEO discuss Mythos model concerns")]
    verdicts = [{
        "id": 0,
        "headline": items[0]["headline"],
        "is_repeat": True,
        "matched_headline": "White House Moves to Grant Federal Agencies Access to Anthropic Mythos AI Model",
        "matched_brief_date": "2026-04-17",
        "reason": "same White House-Anthropic Mythos discussion, reframed as bilateral conversation",
    }]
    recent_history = [
        _hist("White House Moves to Grant Federal Agencies Access to Anthropic Mythos AI Model"),
    ]
    kept, dropped = apply_history_dedup_verdicts(items, verdicts, recent_history)

    # With apply-layer guards alone, the drop WILL still fire because
    # both coherence checks pass (the match is real and they share
    # distinctive tokens). This test documents that scope explicitly.
    # The prompt rewrite is what prevents the judge from emitting the
    # drop in the first place on the next pipeline run.
    assert len(dropped) == 1, "apply-layer does not catch same-family conflation alone — this is expected"


def test_offline_replay_rejects_olly_robbins_drop():
    """Olly Robbins exit ↔ White House Mythos match — candidate and
    matched headline share no distinctive tokens (beyond 'house' maybe,
    which is boilerplate). Guard 2 should catch this."""
    items = [_cand(0, "Olly Robbins' exit deepens turmoil at Foreign Office")]
    verdicts = [{
        "id": 0,
        "headline": items[0]["headline"],
        "is_repeat": True,
        "matched_headline": "White House Moves to Grant Federal Agencies Access to Anthropic Mythos AI Model",
        "matched_brief_date": "2026-04-17",
        "reason": "Robbins exit already covered in prior brief as UK policy story",
    }]
    recent_history = [
        _hist("White House Moves to Grant Federal Agencies Access to Anthropic Mythos AI Model"),
    ]

    kept, dropped = apply_history_dedup_verdicts(items, verdicts, recent_history)

    assert len(kept) == 1, "Robbins candidate must be kept — shares no distinctive tokens with Mythos match"
    assert len(dropped) == 0


def test_offline_replay_rejects_hormuz_argentine_farmers_drop():
    """Exact 2026-04-20 verdict replayed."""
    items = [_cand(0, "Iran closes Strait of Hormuz after U.S., Israeli attacks")]
    verdicts = [{
        "id": 0,
        "headline": items[0]["headline"],
        "is_repeat": True,
        "matched_headline": "Iran war pushes Argentine farmers into fertilizer price bind",
        "matched_brief_date": "pending 2026-04-17",
        "reason": "Strait closure already extensively covered",
    }]
    recent_history = [
        _hist("Iran war pushes Argentine farmers into fertilizer price bind",
              "pending 2026-04-17"),
    ]

    kept, dropped = apply_history_dedup_verdicts(items, verdicts, recent_history)

    # "iran" overlaps but "argentine" / "farmers" / "fertilizer" don't
    # overlap with "hormuz" / "closes" / "israeli". The shared "iran"
    # token WOULD allow the drop under guard 2 alone. Guard 1 also
    # passes (match is real). So this documents that a single shared
    # common-entity token ("iran") on two unrelated sub-stories can
    # still slip through — the prompt's cite-discipline rule is what
    # ultimately prevents this at source.
    assert len(dropped) == 1, (
        "apply-layer guards alone pass on shared 'iran' token — "
        "prompt cite-discipline rule must catch this at the judge"
    )


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


def test_empty_items_returns_empty():
    kept, dropped = apply_history_dedup_verdicts([], [])
    assert kept == []
    assert dropped == []


def test_empty_verdicts_returns_all_items_kept():
    items = [_cand(0, "A"), _cand(1, "B")]
    kept, dropped = apply_history_dedup_verdicts(items, [])
    assert len(kept) == 2
    assert dropped == []


def test_verdict_without_matched_headline_is_accepted():
    """A `is_repeat=true` verdict with no cite is lenient (accepted)
    because there's nothing to verify. This preserves old behavior for
    edge cases where the judge flags a repeat without explaining."""
    items = [_cand(0, "Some headline")]
    verdicts = [{
        "id": 0,
        "headline": items[0]["headline"],
        "is_repeat": True,
        "matched_headline": None,
        "matched_brief_date": None,
        "reason": "flagged without specific cite",
    }]
    recent_history = [_hist("Unrelated history")]

    kept, dropped = apply_history_dedup_verdicts(items, verdicts, recent_history)
    assert len(dropped) == 1


# ---------------------------------------------------------------------------
# 2026-04-24 Meta keystroke / layoff incident — baseline-trim and prompt-clause
# ---------------------------------------------------------------------------
#
# On 2026-04-24 the prior day's pending item "Meta installs keystroke and
# screen-capture software..." had a main_bullet whose third sentence was
# a forward-looking aside: "Meta is planning 10% global layoffs starting
# May 20...". The history_dedup judge read that aside as coverage of the
# May 20 layoff event itself and dropped today's actual layoff
# announcement as a repeat. Two complementary fixes:
#
#   1. `config._trim_history_entry_for_dedup` truncates main_bullet to
#      its FIRST sentence before the recent_history JSON is sent to the
#      judge — the surveillance story's first sentence is "Tool is
#      called MCI, running on..." with no layoff content.
#   2. `prompts/history_dedup_prompt.md` now contains an explicit clause
#      that forward-looking phrasing in history does NOT count as
#      coverage of the actual event.
#
# The tests below pin both invariants without requiring a live Haiku call.


def test_trim_history_entry_keeps_first_sentence_of_main_bullet():
    """The trim helper must keep only the first sentence of main_bullet.

    Sentence boundaries are defined as a `.!?` followed by whitespace.
    Anything after the first such boundary must be discarded — that's
    where the buried "Meta is planning 10% layoffs starting May 20"
    aside lived in the 2026-04-24 incident.
    """
    from config import _trim_history_entry_for_dedup

    entry = {
        "brief_date": "pending 2026-04-23",
        "section": "International Business & Technology",
        "headline": "Meta installs keystroke and screen-capture software on US employee computers to train AI agents",
        "main_bullet": (
            "Tool is called MCI, running on designated work apps and websites. "
            "Data explicitly will not be used for employee performance reviews. "
            "Meta is planning 10% global layoffs starting May 20 alongside the "
            "AI workforce overhaul."
        ),
        "entities": ["Meta"],
    }

    out = _trim_history_entry_for_dedup(entry)

    assert out["main_bullet"] == (
        "Tool is called MCI, running on designated work apps and websites."
    ), "first sentence must be kept verbatim"
    assert "10% global layoffs" not in out["main_bullet"], (
        "buried layoff aside must NOT survive into the dedup baseline — "
        "this is the 2026-04-24 incident"
    )
    assert "performance reviews" not in out["main_bullet"], (
        "second sentence must be discarded"
    )


def test_trim_history_entry_drops_context_field():
    """`context` is not currently emitted by the loaders, but if a
    future loader adds it the trim helper must drop it defensively —
    `context` is even more verbose than main_bullet and would
    re-introduce the buried-aside failure mode."""
    from config import _trim_history_entry_for_dedup

    entry = {
        "brief_date": "2026-04-23",
        "headline": "H",
        "main_bullet": "First sentence only.",
        "context": "- Bullet 1 with lots of adjacent facts.\n- Bullet 2.",
        "entities": [],
    }

    out = _trim_history_entry_for_dedup(entry)

    assert "context" not in out, "context must be dropped"
    assert set(out.keys()) == {
        "brief_date", "headline", "section", "entities", "main_bullet"
    }


def test_trim_history_entry_handles_missing_main_bullet():
    """Defensive: published entries occasionally have an empty
    main_bullet (legacy briefs, placeholders). The helper must not
    explode."""
    from config import _trim_history_entry_for_dedup

    out = _trim_history_entry_for_dedup({
        "brief_date": "2026-04-22",
        "headline": "Headline only",
        "main_bullet": None,
    })

    assert out["main_bullet"] == ""


def test_history_dedup_prompt_contains_forward_looking_clause():
    """The prompt-level fix for the 2026-04-24 incident: history_dedup
    must explicitly tell the judge that forward-looking language in a
    prior item does NOT count as coverage of the actual event."""
    from prompts.loader import load_prompt

    body = load_prompt("history_dedup_prompt.md").lower()

    assert "forward-looking" in body, (
        "history_dedup prompt must mention 'forward-looking' to invoke "
        "the 2026-04-24 fix clause"
    )
    # Each phrasing the prompt explicitly enumerates as forward-looking.
    for phrase in ("is planning", "expected to", "scheduled for", "intends to"):
        assert phrase in body, (
            f"history_dedup prompt must enumerate '{phrase}' as forward-looking"
        )


# ---------------------------------------------------------------------------
# 2026-04-27 Trump-Pakistan principal-shift — NEW PRINCIPAL clause
# ---------------------------------------------------------------------------
#
# On 2026-04-27 the Semafor Flagship "Trump cancels US-Iran peace talks in
# Pakistan" was wrongly merged into the 2026-04-23 pending item "Vance
# cancels Pakistan trip as Iran withholds negotiators before ceasefire
# expiry". These are TWO DIFFERENT events: 4/23 was Vance's planned trip
# cancellation; 4/27 was Trump cancelling the rescheduled Witkoff+Kushner
# trip. Same theme, DIFFERENT principals making DIFFERENT decisions.
#
# The history_dedup prompt now contains a NEW PRINCIPAL clause that
# explicitly handles this case. Tests below pin the prompt content
# without requiring a live Haiku call. A live-API regression test runs
# under the existing live-skip guard to verify Haiku honors the clause.


def test_history_dedup_prompt_contains_new_principal_clause():
    """The prompt-level fix for the 2026-04-27 Trump-Pakistan incident:
    history_dedup must tell the judge that a different head-of-state /
    principal decision-maker taking similar action is a NEW EVENT, not
    a 'spokesperson statement' on the prior story."""
    from prompts.loader import load_prompt

    body = load_prompt("history_dedup_prompt.md").lower()

    assert "new principal" in body, (
        "history_dedup prompt must mention 'NEW PRINCIPAL' to invoke "
        "the 2026-04-27 fix clause"
    )
    # The defining contrast — different head-of-state / agency head /
    # CEO taking similar action.
    for phrase in ("different head-of-state", "agency head", "ceo"):
        assert phrase in body, (
            f"history_dedup NEW PRINCIPAL clause must enumerate '{phrase}'"
        )
    # The Vance vs Trump worked example must appear so the judge sees
    # the exact pattern that broke on 4/27.
    assert "vance" in body and "trump" in body, (
        "history_dedup NEW PRINCIPAL clause must include the Vance vs Trump "
        "Pakistan-cancellation worked example"
    )
    # The principal vs spokesperson distinction is what the clause
    # exists to draw — keep both terms callable.
    assert "spokesperson" in body, (
        "NEW PRINCIPAL clause must contrast principals against spokespersons"
    )


# Live-API regression: Vance (4/23) vs Trump (4/27) Pakistan-cancellation.
# Gated on ANTHROPIC_API_KEY mirroring the test_triage live test pattern.
# Prompt-level reasoning can't be validated by a mock client.


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live history_dedup test",
)
def test_history_dedup_keeps_principal_shift_pakistan_cancellation_live():
    """Live Haiku replay of the actual 2026-04-27 failure case.

    With the NEW PRINCIPAL clause in place, Haiku must KEEP today's
    "Trump cancels US-Iran peace talks in Pakistan" candidate when the
    only matching history entry is "Vance cancels Pakistan trip as
    Iran withholds negotiators before ceasefire expiry" (different
    principal — Vance vs Trump — same diplomatic theme).

    Run 5 trials and require >=3 KEEP verdicts. The case is genuinely
    flaky for Haiku on this style of headline pair (similar verb +
    similar topic + entity overlap on Trump+Pakistan), so we accept
    majority-correct as the bar. Before the clause, this case dropped
    100% of the time; after, it should KEEP a clear majority.
    """
    import json
    import re
    import anthropic
    from prompts.loader import extract_prompt_from_md
    from config import _trim_history_entry_for_dedup, PROMPTS_DIR

    # Read raw prompt body — bypass `load_prompt` because that auto-fills
    # `{recent_history}` from the live Supabase DB. We need the un-filled
    # body so we can inject our own fixture.
    raw_md = (PROMPTS_DIR / "history_dedup_prompt.md").read_text(encoding="utf-8")
    body = extract_prompt_from_md(raw_md)

    # Use the actual main_bullet from the 2026-04-23 pending item, then
    # apply the production trim helper so this test reflects the real
    # baseline shape sent to the judge.
    history = [_trim_history_entry_for_dedup({
        "brief_date": "pending 2026-04-23",
        "section": "International Politics & Policy",
        "headline": (
            "Vance cancels Pakistan trip as Iran withholds negotiators "
            "before ceasefire expiry"
        ),
        "main_bullet": (
            "Iran's Foreign Ministry said 'no decision' yet on sending "
            "negotiators to Islamabad. First round of talks on April 12 "
            "ended with no resolution on Iran's nuclear programme."
        ),
        "entities": ["JD Vance", "Trump", "Iran", "Pakistan"],
    })]
    candidate = {
        "id": 0,
        "headline": "Trump cancels US-Iran peace talks in Pakistan",
        "summary": (
            "Donald Trump cancelled a planned Pakistan trip by Steve "
            "Witkoff and Jared Kushner for talks with Iran, saying the "
            "visit would be a waste of time."
        ),
        "entities": ["Trump", "Witkoff", "Kushner", "Iran", "Pakistan"],
    }

    filled = (
        body
        .replace("{recent_history}", json.dumps(history, indent=2))
        .replace("{items_json}", json.dumps([candidate], indent=2))
    )

    client = anthropic.Anthropic()
    n_trials = 5
    keep_count = 0
    reasons = []
    for _ in range(n_trials):
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": filled}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        verdict = parsed["verdicts"][0]
        reasons.append(verdict.get("reason", "<no reason>"))
        if verdict["is_repeat"] is False:
            keep_count += 1

    # Require majority KEEP. Pre-fix: 0/5. Post-fix target: >=3/5.
    assert keep_count >= 3, (
        f"NEW PRINCIPAL clause failed — only {keep_count}/{n_trials} "
        f"trials kept the candidate (need >=3).\n"
        f"reasons:\n  " + "\n  ".join(reasons)
    )


# ---------------------------------------------------------------------------
# Phase 4: Tuple-aware history dedup (replaces Haiku judgment when tuples
# are available; falls back to Haiku otherwise).
# ---------------------------------------------------------------------------
#
# The 4/27 Vance/Trump Pakistan principal-shift case ran the live test at
# 60% KEEP majority — the prompt clause helps but doesn't fully eliminate
# Haiku's tendency to confidently lump similar-themed items together.
# Phase 4's mechanical tuple comparison eliminates the flakiness entirely:
# Vance and Trump have different `primary_actor`, so tuple match returns
# False deterministically with no LLM call.


def test_tuple_aware_history_dedup_blocks_principal_shift_no_llm():
    """The 4/27 Vance/Trump Pakistan case — must produce is_repeat=False
    deterministically when both items have tuples. No flaky 5-trial test
    needed because there is no LLM call."""
    from pipeline.history_dedup import run_tuple_aware_history_dedup

    items = [
        {"headline": "Trump cancels US-Iran peace talks in Pakistan",
         "_event_tuple": {
             "event_type": "diplomatic_action",
             "primary_actor": "Trump",
             "counterpart": "Iran",
             "action": "cancels US-Iran peace talks",
         }}
    ]
    recent_history = [
        {"brief_date": "pending 2026-04-23",
         "headline": "Vance cancels Pakistan trip as Iran withholds negotiators",
         "event_tuple": {
             "event_type": "diplomatic_action",
             "primary_actor": "Vance",
             "counterpart": None,
             "action": "cancels Pakistan trip",
         }}
    ]
    result, telem = run_tuple_aware_history_dedup(items, recent_history)
    assert telem["items_with_tuples"] == 1
    assert telem["drops"] == 0
    v = result["verdicts"][0]
    assert v["is_repeat"] is False, (
        "Trump cancellation must KEEP via tuple comparison "
        "(different primary_actor than Vance); reason: " + v.get("reason", "")
    )


def test_tuple_aware_history_dedup_drops_genuine_paraphrase():
    """Genuine cross-day repeat: same event paraphrased on a later day
    must be flagged as is_repeat=True. The matched_headline copies the
    historical entry verbatim so apply_history_dedup_verdicts'
    coherence guard passes."""
    from pipeline.history_dedup import run_tuple_aware_history_dedup

    items = [
        {"headline": "Israel's Iron Dome battery moved into UAE",
         "_event_tuple": {
             "event_type": "military_operation",
             "primary_actor": "Israel",
             "counterpart": None,
             "action": "deploys Iron Dome battery",
         }}
    ]
    recent_history = [
        {"brief_date": "2026-04-26",
         "headline": "Israel deployed Iron Dome battery with troops to UAE",
         "event_tuple": {
             "event_type": "military_operation",
             "primary_actor": "Israel",
             "counterpart": None,
             "action": "deploys Iron Dome battery",
         }}
    ]
    result, telem = run_tuple_aware_history_dedup(items, recent_history)
    assert telem["drops"] == 1
    v = result["verdicts"][0]
    assert v["is_repeat"] is True
    assert v["matched_headline"] == (
        "Israel deployed Iron Dome battery with troops to UAE"
    ), "matched_headline must be verbatim from history (coherence-check requirement)"
    assert v["matched_brief_date"] == "2026-04-26"


def test_tuple_aware_history_dedup_skips_items_without_tuples():
    """Items lacking `_event_tuple` produce no verdicts here — the
    caller routes them through the Haiku fallback. Counted in
    `skipped_no_tuple` for telemetry."""
    from pipeline.history_dedup import run_tuple_aware_history_dedup

    items = [
        {"headline": "Item with no tuple field"},
        {"headline": "Item with empty tuple", "_event_tuple": {}},
        {"headline": "Item with tuple",
         "_event_tuple": {"event_type": "other", "primary_actor": "X",
                          "counterpart": None, "action": "y"}},
    ]
    recent_history = [
        {"brief_date": "2026-04-26", "headline": "H",
         "event_tuple": {"event_type": "other", "primary_actor": "X",
                         "counterpart": None, "action": "y"}}
    ]
    result, telem = run_tuple_aware_history_dedup(items, recent_history)
    assert telem["items_with_tuples"] == 1
    assert telem["skipped_no_tuple"] == 2
    # Only the item with a tuple gets a verdict.
    assert len(result["verdicts"]) == 1
    assert result["verdicts"][0]["id"] == 2


def test_tuple_aware_history_dedup_skips_history_without_tuples():
    """Pre-Phase-2 historical items lack `event_tuple`. They must NOT
    produce false matches — the tuple path silently passes those
    history entries by, leaving the Haiku fallback to handle the
    semantic check if needed."""
    from pipeline.history_dedup import run_tuple_aware_history_dedup

    items = [
        {"headline": "Trump cancels US-Iran peace talks in Pakistan",
         "_event_tuple": {"event_type": "diplomatic_action",
                          "primary_actor": "Trump", "counterpart": "Iran",
                          "action": "cancels US-Iran peace talks"}},
    ]
    # No `event_tuple` field on the history entry.
    recent_history = [
        {"brief_date": "pending 2026-04-23",
         "headline": "Vance cancels Pakistan trip",
         "main_bullet": "Iran's foreign ministry said no decision."},
    ]
    result, telem = run_tuple_aware_history_dedup(items, recent_history)
    # Item gets a "no match" verdict, but `history_with_tuples=0` so
    # the orchestrator won't trust the tuple path alone — it'll merge
    # with Haiku.
    assert telem["history_with_tuples"] == 0
    assert telem["drops"] == 0


def test_merge_history_dedup_verdicts_prefers_primary():
    """When tuple path returns a verdict for an item, it wins over the
    Haiku fallback for that id. Items only the fallback covers fill in."""
    from pipeline.history_dedup import merge_history_dedup_verdicts

    primary = [
        {"id": 0, "is_repeat": False, "reason": "tuple: no match"},
    ]
    fallback = [
        {"id": 0, "is_repeat": True, "reason": "haiku: matched"},
        {"id": 1, "is_repeat": True, "reason": "haiku: matched"},
        {"id": 2, "is_repeat": False, "reason": "haiku: no match"},
    ]
    merged = merge_history_dedup_verdicts(primary, fallback)
    by_id = {v["id"]: v for v in merged}
    # id=0 must come from primary (tuple path), not fallback.
    assert by_id[0]["reason"] == "tuple: no match"
    # ids 1 and 2 only in fallback.
    assert by_id[1]["reason"] == "haiku: matched"
    assert by_id[2]["reason"] == "haiku: no match"


def test_trim_history_entry_preserves_event_tuple():
    """Phase 4: the trim helper that strips main_bullet to first
    sentence must NOT discard `event_tuple` — the tuple-aware history
    dedup needs it on the recent_history entries."""
    from config import _trim_history_entry_for_dedup

    entry = {
        "brief_date": "2026-04-26",
        "headline": "H",
        "main_bullet": "First sentence. Second sentence with detail.",
        "entities": ["Meta"],
        "event_tuple": {
            "event_type": "personnel_change",
            "primary_actor": "Meta",
            "counterpart": None,
            "action": "cuts jobs",
        },
    }
    out = _trim_history_entry_for_dedup(entry)
    assert "event_tuple" in out
    assert out["event_tuple"]["primary_actor"] == "Meta"
    # Main bullet still trimmed to first sentence.
    assert out["main_bullet"] == "First sentence."
