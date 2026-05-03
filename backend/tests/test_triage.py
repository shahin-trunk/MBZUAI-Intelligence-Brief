"""Regression tests for pipeline triage.

Locks the 2026-04-20 fix: the Semafor Flagship headline "China's humanoid
robot completes half marathon" was dropped by triage as a sports result
when it is actually a directly on-topic robotics capability demonstration.
The fix moved the prompt to `prompts/triage_prompt.md`, added explicit
AI/robotics protection rules, and started sending a summary snippet to
Haiku alongside each headline. These tests pin that shape without
requiring a live Haiku call.

The `test_triage_live_behavior_on_curated_fixture` test DOES hit Haiku
and is skipped when `ANTHROPIC_API_KEY` is not set.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from prompts.loader import load_prompt  # noqa: E402
from pipeline.orchestrator import _build_triage_line  # noqa: E402


# ---------------------------------------------------------------------------
# Prompt-file plumbing
# ---------------------------------------------------------------------------


def test_triage_prompt_loads():
    """The prompt file must exist and parse out of its code fence. Catches
    accidental file moves or broken ``` fence formatting."""
    prompt = load_prompt("triage_prompt.md")
    assert prompt, "triage_prompt.md loaded as empty"
    assert "DROP" in prompt, "prompt missing its DROP section"
    assert "KEEP" in prompt, "prompt missing its KEEP section"


def test_triage_prompt_protects_robotics_and_ai():
    """The protective AI/robotics language must survive future edits.
    Without it the 2026-04-20 humanoid-marathon bug will recur."""
    prompt = load_prompt("triage_prompt.md").lower()
    for required in ("robot", "humanoid", "autonomous", "ai"):
        assert required in prompt, (
            f"triage prompt must mention '{required}' to keep AI/robotics protection"
        )
    # The critical anti-pattern clause — a robot competition is NOT a
    # sports result. Re-phrase OK, but the concept must stay.
    assert "marathon" in prompt or "competition" in prompt or "race" in prompt, (
        "prompt lost its robot-competition anti-pattern clause"
    )


def test_triage_prompt_is_output_format_terse():
    """The prompt must still ask for a bare JSON array of indices —
    anything else breaks `_parse_triage_keep_indices`."""
    prompt = load_prompt("triage_prompt.md")
    assert "JSON array" in prompt or "json array" in prompt.lower()
    assert "indices" in prompt.lower() or "index" in prompt.lower()


# ---------------------------------------------------------------------------
# _build_triage_line — summary plumbing
# ---------------------------------------------------------------------------


def test_build_triage_line_includes_summary_when_available():
    """The line builder must attach a summary slice so Haiku can resolve
    ambiguous headlines (robotics vs sports, etc.)."""
    item = {
        "headline": "China's humanoid robot completes half marathon",
        "summary": (
            "A bipedal humanoid robot made by Chinese company Honor finished a "
            "half marathon in Beijing in under 51 minutes. The robot crashed "
            "during the race and required human assistance."
        ),
    }
    line = _build_triage_line(0, item)
    assert line.startswith("1. "), f"expected 1-based numbering, got: {line}"
    assert "humanoid robot completes half marathon" in line
    assert "bipedal humanoid robot" in line, (
        "summary snippet missing — Haiku won't see the robotics context"
    )
    assert " — " in line, "summary separator missing"


def test_build_triage_line_falls_back_to_raw_content_when_no_summary():
    item = {
        "headline": "Some headline",
        "summary": "",
        "raw_content": "Detailed body text explaining what this is about",
    }
    line = _build_triage_line(2, item)
    assert "Detailed body text" in line
    assert line.startswith("3. ")


def test_build_triage_line_headline_only_when_no_body():
    """Graceful when there's nothing but a headline."""
    item = {"headline": "Bare headline"}
    line = _build_triage_line(0, item)
    assert line == "1. Bare headline"


def test_build_triage_line_truncates_long_summaries():
    """Long summaries must be clipped so a 600-item run stays under
    Haiku's context budget."""
    long_body = "A" * 5000
    item = {"headline": "H", "summary": long_body}
    line = _build_triage_line(0, item)
    # 1-based prefix ("1. ") + headline + em-dash + up to
    # _TRIAGE_SUMMARY_SNIPPET_CHARS chars of summary. Constant is 300 today.
    assert len(line) < 350


def test_build_triage_line_handles_missing_headline():
    item = {"summary": "body only"}
    line = _build_triage_line(0, item)
    assert "(no headline)" in line


# ---------------------------------------------------------------------------
# Drop-reason wording — no more false "MBZUAI relevance" claim
# ---------------------------------------------------------------------------


def test_drop_reason_no_longer_claims_mbzuai_relevance():
    """The old drop reason ('Triage: not relevant to MBZUAI brief') lied
    about what triage does. Verify it's gone from the orchestrator."""
    orchestrator_src = (BACKEND_DIR / "pipeline" / "orchestrator.py").read_text(
        encoding="utf-8"
    )
    assert "not relevant to MBZUAI brief" not in orchestrator_src, (
        "old misleading drop reason is back — remove it"
    )
    assert "Triage: removed as obvious non-news junk" in orchestrator_src, (
        "new honest drop reason missing"
    )


# ---------------------------------------------------------------------------
# Offline behavioral check — real Haiku call, small curated fixture
# ---------------------------------------------------------------------------


pytestmark_live = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live Haiku behavior test",
)


@pytestmark_live
@pytest.mark.asyncio
async def test_triage_live_behavior_on_curated_fixture():
    """Feed 4 junk + 4 AI/robotics items through the real
    `triage_collected_items` and assert all AI/robotics items survive.
    Gated on ANTHROPIC_API_KEY so it only runs when explicitly enabled."""
    import anthropic

    from pipeline.orchestrator import triage_collected_items

    items = [
        # --- AI / robotics — all must be KEPT ---
        {
            "headline": "China's humanoid robot completes half marathon",
            "summary": (
                "A bipedal humanoid robot made by Chinese company Honor finished "
                "a half marathon in Beijing in under 51 minutes. Nearly half of "
                "the robot entrants navigated autonomously."
            ),
            "source": "Semafor Flagship",
        },
        {
            "headline": "Humanoid robot shatters human half-marathon world record in Beijing",
            "summary": (
                "A humanoid robot competing against flesh-and-blood runners has "
                "broken the world record at a Beijing half-marathon, showcasing "
                "rapid advances from Chinese makers."
            ),
            "source": "WAM",
        },
        {
            "headline": "Alibaba open-sources Qwen3.6-35B-A3B sparse MoE model",
            "summary": "First open-weight model in the Qwen3.6 series, positioned for coding and agentic workflows.",
            "source": "TLDR AI",
        },
        {
            "headline": "Cerebras files for IPO as AI chip demand continues",
            "summary": "Cerebras filed publicly for an IPO, reporting a swing to profitability in 2025.",
            "source": "Bloomberg Briefing",
        },
        # --- Junk — expected DROPS ---
        {
            "headline": "UAE national judo team raises its tally to 4 medals at Asian Championship in China",
            "summary": "UAE judo athletes continued their strong performance at the Asian Championship.",
            "source": "WAM",
        },
        {
            "headline": "Fujairah hotels record peak occupancy in early 2026",
            "summary": "Hotel occupancy in Fujairah reached its highest level in years during the first quarter.",
            "source": "WAM",
        },
        {
            "headline": "Dubai Police mountain rescue units extract stranded hikers in Hatta",
            "summary": "Police rescue teams assisted a group of hikers who became stranded overnight.",
            "source": "WAM",
        },
        {
            "headline": "UAE sailing team departs for Asian Beach Games in China",
            "summary": "The UAE sailing squad left for the Asian Beach Games.",
            "source": "WAM",
        },
    ]

    client = anthropic.AsyncAnthropic()
    kept = await triage_collected_items(items, client)
    kept_headlines = {k["headline"] for k in kept}

    must_keep = {
        "China's humanoid robot completes half marathon",
        "Humanoid robot shatters human half-marathon world record in Beijing",
        "Alibaba open-sources Qwen3.6-35B-A3B sparse MoE model",
        "Cerebras files for IPO as AI chip demand continues",
    }
    missing = must_keep - kept_headlines
    assert not missing, (
        f"triage wrongly dropped AI/robotics items: {missing}"
    )


# ---------------------------------------------------------------------------
# Chunked-triage plumbing — _triage_single_call wiring + global-index merge
# ---------------------------------------------------------------------------


def test_triage_module_exposes_chunking_constants():
    """The chunked rewrite must publish its tunables for the eval harness
    and prod tests. Lock the names so renames break loudly."""
    from pipeline import orchestrator
    for name in (
        "TRIAGE_SINGLE_CALL_THRESHOLD",
        "TRIAGE_CHUNK_SIZE",
        "TRIAGE_CONCURRENCY",
        "TRIAGE_SANITY_SAMPLE_SIZE",
        "TRIAGE_SANITY_ALERT_THRESHOLD",
    ):
        assert hasattr(orchestrator, name), (
            f"orchestrator must export {name} (chunked triage constants)"
        )


@pytest.mark.asyncio
async def test_triage_single_call_returns_global_indices(monkeypatch):
    """`_triage_single_call` must offset its 1-based local indices back
    to 0-based GLOBAL indices before returning. Without this, a chunk
    starting at offset=120 that emits `[1, 3]` would wrongly imply
    items 0 and 2 in the global pool instead of items 120 and 122."""
    from pipeline.orchestrator import _triage_single_call

    class _FakeContent:
        def __init__(self, text):
            self.text = text

    class _FakeResponse:
        def __init__(self, text):
            self.content = [_FakeContent(text)]

    class _FakeClient:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                # Local 1-based: keep items 1 and 3 (the first and third).
                return _FakeResponse("[1, 3]")

    chunk = [
        {"headline": f"item {i}", "summary": ""} for i in range(5)
    ]
    keep_set, log = await _triage_single_call(
        chunk, _FakeClient(), label="test", offset=120
    )
    # Local indices [1, 3] → 0-based [0, 2] → global [120, 122].
    assert keep_set == {120, 122}, (
        f"global-index mapping broken: {keep_set} (expected {{120, 122}})"
    )
    assert log["status"] == "ok"
    assert log["kept_count"] == 2
    assert log["dropped_count"] == 3


@pytest.mark.asyncio
async def test_triage_single_call_fails_open_on_request_error():
    """Per-chunk fail-open: an API error must NOT drop the chunk's items.
    Returns ALL global indices for the chunk so legitimate items survive
    a transient connectivity glitch in one shard."""
    from pipeline.orchestrator import _triage_single_call

    class _BoomClient:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                raise RuntimeError("simulated network failure")

    chunk = [{"headline": f"x {i}", "summary": ""} for i in range(4)]
    keep_set, log = await _triage_single_call(
        chunk, _BoomClient(), label="boom", offset=10
    )
    assert keep_set == {10, 11, 12, 13}, (
        f"fail-open must keep ALL chunk items globally; got {keep_set}"
    )
    assert log["status"] == "request_failed_open"
    assert log["kept_count"] == 4


@pytest.mark.asyncio
async def test_triage_single_call_fails_open_after_two_parse_failures():
    """If both attempts produce un-parseable JSON, the chunk fails open
    so the pipeline doesn't drop a whole batch on a model glitch."""
    from pipeline.orchestrator import _triage_single_call

    class _Content:
        text = "not json at all, sorry"

    class _Response:
        content = [_Content()]

    class _BadJsonClient:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                return _Response()

    chunk = [{"headline": f"y {i}", "summary": ""} for i in range(3)]
    keep_set, log = await _triage_single_call(
        chunk, _BadJsonClient(), label="bad-json", offset=5
    )
    assert keep_set == {5, 6, 7}, (
        f"two-parse-failure fail-open must keep ALL chunk items; got {keep_set}"
    )
    assert log["status"] == "parse_failed_open"
    assert len(log["attempts"]) == 2


@pytest.mark.asyncio
async def test_triage_collected_items_chunks_and_merges(tmp_path, monkeypatch):
    """End-to-end chunked path: 150 synthetic items split into 3 chunks
    of 60 (last chunk has 30), each returning a slice of keep indices.
    The wrapper must merge globally and preserve original item order."""
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_collected_items

    # Force chunking even at small N (default threshold is 60).
    monkeypatch.setattr(orchestrator, "TRIAGE_SINGLE_CALL_THRESHOLD", 30)
    monkeypatch.setattr(orchestrator, "TRIAGE_CHUNK_SIZE", 50)
    monkeypatch.setattr(orchestrator, "TRIAGE_CONCURRENCY", 3)
    # Disable the sanity check sub-pass to keep this test focused.
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "false")
    # Redirect save_intermediate target to the test tmp dir.
    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)

    items = [
        {"headline": f"item-{i}", "summary": "x", "source": "src"}
        for i in range(150)
    ]

    class _Content:
        def __init__(self, text):
            self.text = text

    class _Response:
        def __init__(self, text):
            self.content = [_Content(text)]

    class _DeterministicClient:
        """Returns 1-based indices [1, 5, 10] for every chunk regardless
        of size. So global-kept becomes {0, 4, 9} from chunk-0,
        {50, 54, 59} from chunk-50, {100, 104, 109} from chunk-100."""
        class messages:
            @staticmethod
            async def create(**_kwargs):
                return _Response("[1, 5, 10]")

    kept = await triage_collected_items(items, _DeterministicClient())
    kept_indices = sorted(items.index(k) for k in kept)
    expected = [0, 4, 9, 50, 54, 59, 100, 104, 109]
    assert kept_indices == expected, (
        f"chunked merge wrong; got {kept_indices} expected {expected}"
    )

    # Verify the saved triage_output JSON shape.
    today = orchestrator.get_today_date()
    triage_log_path = tmp_path / f"triage_output_{today}.json"
    assert triage_log_path.exists(), "triage_output_{date}.json not saved"
    triage_log = __import__("json").loads(triage_log_path.read_text())
    assert triage_log["chunked"] is True
    assert triage_log["chunk_count"] == 3
    assert triage_log["chunk_size"] == 50
    assert triage_log["concurrency"] == 3
    assert triage_log["kept"] == 9
    assert triage_log["dropped"] == 141


@pytest.mark.asyncio
async def test_triage_collected_items_preserves_input_order(monkeypatch, tmp_path):
    """The chunked path must return kept items in their ORIGINAL input
    order (not chunk order, not response order). Critical because
    downstream stages assume the items list ordering."""
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_collected_items

    monkeypatch.setattr(orchestrator, "TRIAGE_SINGLE_CALL_THRESHOLD", 5)
    monkeypatch.setattr(orchestrator, "TRIAGE_CHUNK_SIZE", 5)
    monkeypatch.setattr(orchestrator, "TRIAGE_CONCURRENCY", 5)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "false")
    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)

    items = [{"headline": f"H{i}", "summary": ""} for i in range(20)]

    class _Response:
        class _C:
            def __init__(self, t):
                self.text = t
        def __init__(self, t):
            self.content = [self._C(t)]

    class _KeepAllClient:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                # Keep all items in this chunk: [1, 2, 3, 4, 5]
                return _Response("[1, 2, 3, 4, 5]")

    kept = await triage_collected_items(items, _KeepAllClient())
    kept_headlines = [k["headline"] for k in kept]
    expected = [f"H{i}" for i in range(20)]
    assert kept_headlines == expected, (
        f"input order broken; got {kept_headlines}"
    )


# ---------------------------------------------------------------------------
# Sanity-check pass — alert-only, surfaces suspected false-positive drops
# ---------------------------------------------------------------------------


def test_triage_sanity_check_prompt_loads():
    """The new inverse-stance prompt must exist and parse. Catches
    accidental file moves or broken fence formatting."""
    prompt = load_prompt("triage_sanity_check_prompt.md")
    assert prompt, "triage_sanity_check_prompt.md loaded as empty"
    assert "could be news" in prompt, (
        "sanity-check prompt missing its 'could be news' verdict label"
    )
    assert "definitely noise" in prompt, (
        "sanity-check prompt missing its 'definitely noise' verdict label"
    )
    assert "keep_indices" in prompt, (
        "sanity-check prompt must specify keep_indices output shape"
    )


def test_parse_sanity_check_verdicts_accepts_dict_shape():
    """The documented prompt shape is `{"keep_indices": [1, 2]}`."""
    from pipeline.orchestrator import _parse_sanity_check_verdicts
    result = _parse_sanity_check_verdicts({"keep_indices": [1, 3, 5]})
    assert result == [1, 3, 5]


def test_parse_sanity_check_verdicts_accepts_bare_list():
    """Defensive: also accept a bare integer array, same as the primary
    triage parser. Sonnet/Haiku occasionally drop the dict wrapper."""
    from pipeline.orchestrator import _parse_sanity_check_verdicts
    result = _parse_sanity_check_verdicts([1, 2, 4])
    assert result == [1, 2, 4]


def test_parse_sanity_check_verdicts_rejects_garbage():
    """Bad payloads must raise ValueError so the caller can fail-open."""
    from pipeline.orchestrator import _parse_sanity_check_verdicts
    with pytest.raises(ValueError):
        _parse_sanity_check_verdicts(42)
    with pytest.raises(ValueError):
        _parse_sanity_check_verdicts({"foo": "bar"})


@pytest.mark.asyncio
async def test_triage_sanity_check_alerts_above_threshold(
    monkeypatch, tmp_path, caplog
):
    """When the secondary call flags >10% of the sampled drops as 'could
    be news', triage_sanity_check must log a warning and persist the
    suspected_false_positives audit JSON. ALERT-ONLY: it must not modify
    the kept set."""
    import logging
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_sanity_check

    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "true")

    # 50 items: indices 0..14 kept, 15..49 dropped (35 in sample pool >
    # sample_size=20 so the function actually runs).
    items = [{"headline": f"H{i}", "source": "src"} for i in range(50)]
    keep_set = set(range(15))

    class _Content:
        text = '{"keep_indices": [1, 2, 3, 4, 5]}'  # 5 of 20 = 25% disagreement

    class _Response:
        content = [_Content()]

    class _AlertingClient:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                return _Response()

    caplog.set_level(logging.WARNING, logger="pipeline.orchestrator")
    await triage_sanity_check(
        items, keep_set, _AlertingClient(),
        today="2026-04-23", sample_size=20,
    )

    audit_path = tmp_path / "triage_sanity_check_2026-04-23.json"
    assert audit_path.exists(), "sanity check did not save audit JSON"
    audit = __import__("json").loads(audit_path.read_text())
    assert audit["sample_size"] == 20
    assert audit["disagreement_count"] == 5
    assert audit["disagreement_rate"] == 0.25
    assert audit["alerted"] is True
    assert len(audit["suspected_false_positives"]) == 5

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("Triage sanity check" in r.message for r in warnings), (
        "expected a 'Triage sanity check' warning above threshold"
    )


@pytest.mark.asyncio
async def test_triage_sanity_check_silent_when_disabled(
    monkeypatch, tmp_path
):
    """The TRIAGE_SANITY_CHECK_ENABLED=false env var must short-circuit
    the call entirely (no API call, no audit JSON)."""
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_sanity_check

    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "false")

    api_calls = []

    class _Tracking:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                api_calls.append(True)
                raise AssertionError("API should not be called when disabled")

    items = [{"headline": f"H{i}"} for i in range(30)]
    keep_set = set(range(15))
    await triage_sanity_check(
        items, keep_set, _Tracking(),
        today="2026-04-23", sample_size=20,
    )

    assert not api_calls, "API was called even though sanity check is disabled"
    assert not (tmp_path / "triage_sanity_check_2026-04-23.json").exists()


@pytest.mark.asyncio
async def test_triage_sanity_check_skips_when_too_few_drops(
    monkeypatch, tmp_path
):
    """When the dropped pool is smaller than `sample_size`, the check
    skips entirely — no warning, no API call, no audit file (the sample
    would be statistically meaningless)."""
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_sanity_check

    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "true")

    api_calls = []

    class _Tracking:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                api_calls.append(True)
                raise AssertionError("API should not be called with few drops")

    # 25 items, 20 kept → only 5 dropped. sample_size=20 → must skip.
    items = [{"headline": f"H{i}"} for i in range(25)]
    keep_set = set(range(20))
    await triage_sanity_check(
        items, keep_set, _Tracking(),
        today="2026-04-23", sample_size=20,
    )

    assert not api_calls
    assert not (tmp_path / "triage_sanity_check_2026-04-23.json").exists()


# ---------------------------------------------------------------------------
# 2026-04-24 Meta layoff incident — source-aware bypass + stratified rescue
# ---------------------------------------------------------------------------
#
# On 2026-04-24 the chunked Haiku triage dropped a TechCrunch Meta layoff
# headline ("Meta to cut 10% of jobs, or 8,000 employees"), three copies
# of the Dubai $9B Metro Gold Line expansion, and three copies of the
# DOJ marijuana reclassification — all from paid editorial wires, all
# hard-news. Two complementary fixes:
#
#   1. Source-aware floor: items where source ∈ TRIAGE_BYPASS_SOURCES
#      AND headline matches TRIAGE_BYPASS_HEADLINE_PATTERN skip triage
#      entirely (deterministic, no LLM call).
#   2. Stratified sanity-check + auto-rescue: editorial-source drops
#      are sampled disproportionately by the inverse-prompt secondary
#      verdict, and high-confidence inverse-KEEPs from those sources
#      are auto-rescued back into the kept set when
#      `TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL=true` (default).


def test_inverted_default_or_override_keeps_missed_hard_news_headlines():
    """The hard-news headlines that died at triage on 2026-04-24 AND
    2026-04-27 must all auto-keep — either via the inverted default
    (no junk match) or via the hard-news override (junk match plus
    hard-news markers). Both buckets skip the LLM call.

    Phase 1.5 cleanup: previously this test asserted regex match on
    the wide v3 `TRIAGE_BYPASS_HEADLINE_PATTERN`, which was retired in
    favour of the narrower `_TRIAGE_HARD_NEWS_OVERRIDE` (only used to
    override junk drops). Now the assertion is end-to-end: the
    classifier returns ANY auto-keep bucket. Decoupling the test from
    the regex shape means future failure modes that don't enumerate
    a verb pattern still pass as long as the inverted default keeps
    the item.
    """
    from pipeline.orchestrator import _triage_classify

    must_keep_buckets = {"bypass_keep", "default_keep"}
    must_keep = [
        # === 2026-04-24 corpus (Meta-class hard news) ===
        ("TechCrunch", "Meta to cut 10% of jobs, or 8,000 employees"),
        ("The National", "Dubai announces $9 billion metro Gold Line expansion project"),
        ("Semafor Gulf", "Dubai greenlights $9 billion metro expansion amid Iran war"),
        ("Bloomberg Briefing", "DOJ Reclassifies Marijuana as Less Dangerous Drug"),
        ("Semafor Flagship", "Trump administration reclassifies marijuana as less harmful"),
        # === 2026-04-27 corpus (diplomacy / military / sovereignty) ===
        ("WSJ Briefing", "Trump cancels envoys' Pakistan trip over Iran negotiations"),
        ("Bloomberg Briefing", "US Sends Envoys to Pakistan to Meet Iran Officials"),
        ("Reuters Daily Briefing", "Witkoff and Kushner dispatched to Islamabad for Iran talks"),
        ("Semafor Flagship", "Trump cancels US-Iran peace talks in Pakistan"),
        ("WSJ Briefing", "White House confirms US President's envoys heading to Pakistan tomorrow"),
        ("FT Briefing", "Joint Statement following meeting between Abdullah bin Zayed, UK Foreign Secretary"),
        ("Axios AM/PM", "Israel deployed Iron Dome battery with troops to UAE during Iran war"),
        ("The National", "US Navy seizes Iranian-flagged cargo vessel near Hormuz"),
        ("Reuters", "Three US carriers now operating in Middle East for first time since 2003"),
    ]
    for source, headline in must_keep:
        bucket = _triage_classify({"source": source, "headline": headline})
        assert bucket in must_keep_buckets, (
            f"hard-news headline must auto-keep, got {bucket!r}: "
            f"[{source}] {headline!r}"
        )


def test_inverted_default_drops_obvious_junk():
    """Editorial-source junk (lifestyle, sports, ceremonial) must
    route to default_drop. The inverted default + bounded JUNK
    pattern handle this without any regex enumeration.

    Includes the 2026-04-27 ceasefire-in-quotes edge case to confirm
    the JUNK pattern (post-Phase-1) doesn't FP on it."""
    from pipeline.orchestrator import _triage_classify

    must_drop = [
        ("Axios AM/PM", "Boston Marathon showcases human spirit and resilience"),
        ("FT Briefing", "Beyond Marrakech — and into the Atlas on horseback"),
        ("WSJ Briefing", "Average cocktail price hits $13.61 nationally"),
        ("Reuters", "UAE judo team raises tally to 4 medals at Asian Championship"),
    ]
    for source, headline in must_drop:
        bucket = _triage_classify({"source": source, "headline": headline})
        assert bucket == "default_drop", (
            f"junk headline must default_drop, got {bucket!r}: "
            f"[{source}] {headline!r}"
        )


def test_hard_news_override_beats_junk_pattern():
    """The narrow override case: a headline that matches BOTH a hard-
    news pattern (≥million $/€/£ amount, percentage, or layoffs/
    acquisition/sanction/indict) AND the junk pattern routes to
    bypass_keep. The override is the ONLY remaining bypass surface
    after the Phase 1.5 cleanup."""
    from pipeline.orchestrator import _triage_classify

    cases = [
        # Marathon (junk) + $500M (override) -> bypass_keep
        ("Bloomberg Briefing", "Marathon Pharma raises $500 million Series F"),
        # Marathon (junk) + $10 billion (override) -> bypass_keep
        ("WSJ Briefing", "Boston Marathon canceled after $10 billion sponsor pulls out"),
        # Hotel occupancy (junk) + layoffs (override) -> bypass_keep
        ("FT Briefing", "Hotel occupancy layoffs cascade across chain"),
        # Judo (junk) + sanction (override) -> bypass_keep
        ("Reuters", "Judo federation sanction blocks Olympic-qualifying meet"),
    ]
    for source, headline in cases:
        bucket = _triage_classify({"source": source, "headline": headline})
        assert bucket == "bypass_keep", (
            f"hard-news override must beat junk match, got {bucket!r}: "
            f"[{source}] {headline!r}"
        )


def test_hard_news_override_does_not_fire_on_pure_junk():
    """The override is narrow by design — sub-million dollar amounts,
    fractional percentages of sports stats, etc. must NOT match. Pure
    junk without a real hard-news marker stays default_drop.
    """
    from pipeline.orchestrator import _triage_classify

    cases = [
        # $13.61 isn't a million-scale amount — override must not fire.
        ("WSJ Briefing", "Average cocktail price hits $13.61 nationally"),
        # Charity raise of ≤thousands — override deliberately doesn't
        # match (only billion/million-scale amounts qualify).
        ("Axios AM/PM", "Boston Marathon raises $13,000 for charity"),
        # Marathon-only — no hard-news marker.
        ("Bloomberg Briefing", "Boston Marathon showcases human spirit"),
    ]
    for source, headline in cases:
        bucket = _triage_classify({"source": source, "headline": headline})
        assert bucket == "default_drop", (
            f"pure junk must default_drop (override should not fire), got "
            f"{bucket!r}: [{source}] {headline!r}"
        )


# ---------------------------------------------------------------------------
# Phase 1: inverted triage default for editorial wires (post-2026-04-27)
# ---------------------------------------------------------------------------
#
# The bypass regex was whack-a-mole — every observed failure required a new
# verb pattern. The structural fix: for editorial sources, default to KEEP
# unless headline matches a small bounded JUNK pattern. Stops the regex
# maintenance loop and asymmetrically tilts toward recall (FP-on-drop costs
# more than FN-on-drop for paid wires).
#
# 4-bucket classifier:
#   bypass_keep   — editorial source + hard-news pattern -> auto-keep
#   default_keep  — editorial source + no junk pattern -> auto-keep (NEW)
#   default_drop  — editorial source + junk pattern -> auto-drop
#   needs_triage  — non-editorial source -> existing Haiku path


def test_triage_classify_routes_editorial_hard_news_to_auto_keep():
    """Hard-news editorial items must auto-keep — Phase 1.5 cleanup
    means most route via default_keep (no junk overlap) instead of
    bypass_keep, but both buckets skip the LLM call. The test checks
    end-to-end auto-keep behavior, not which specific bucket fired."""
    from pipeline.orchestrator import _triage_classify

    auto_keep_buckets = {"bypass_keep", "default_keep"}
    # All from the 4/24 + 4/27 must-rescue corpus.
    cases = [
        ("WSJ Briefing", "Trump cancels envoys' Pakistan trip over Iran negotiations"),
        ("Bloomberg Briefing", "DOJ Reclassifies Marijuana as Less Dangerous Drug"),
        ("Reuters Daily Briefing", "Witkoff and Kushner dispatched to Islamabad for Iran talks"),
        ("TechCrunch", "Meta to cut 10% of jobs, or 8,000 employees"),
        ("The National", "Dubai announces $9 billion metro Gold Line expansion project"),
    ]
    for source, headline in cases:
        bucket = _triage_classify({"source": source, "headline": headline})
        assert bucket in auto_keep_buckets, (
            f"hard-news editorial item must auto-keep: "
            f"got {bucket!r} for [{source}] {headline!r}"
        )


def test_triage_classify_routes_editorial_quiet_to_default_keep():
    """The 2026-04-27 inverted-default fix: editorial-source items that
    DON'T match a hard-news pattern AND DON'T match the junk pattern
    must auto-keep under the inverted default."""
    from pipeline.orchestrator import _triage_classify

    # Quiet editorial commentary / analysis / market-color pieces — the
    # class that previously got dropped by Haiku flakiness.
    cases = [
        ("Bloomberg Briefing", "IBM and ServiceNow results reignite AI disruption fears"),
        ("FT Briefing", "Eurozone business activity contracts for first time in 16 months"),
        ("Axios AI+", "AI labs ignore consumer skepticism despite impending IPOs"),
        ("WSJ Briefing", "Chip stocks rally led by Texas Instruments surge"),
        ("Semafor Flagship", "Polish PM Tusk publicly questions US readiness on NATO Article 5"),
    ]
    for source, headline in cases:
        bucket = _triage_classify({"source": source, "headline": headline})
        assert bucket == "default_keep", (
            f"quiet editorial item must route to default_keep under inverted default: "
            f"got {bucket!r} for [{source}] {headline!r}"
        )


def test_triage_classify_routes_editorial_junk_to_default_drop():
    """Editorial items matching the bounded JUNK pattern auto-drop with
    a distinct drop_reason (no Haiku call needed for unambiguous junk)."""
    from pipeline.orchestrator import _triage_classify, TRIAGE_JUNK_PATTERN

    cases = [
        ("Axios AM/PM", "Boston Marathon showcases human spirit"),
        ("WSJ Briefing", "Average cocktail price hits $13.61 nationally"),
        ("FT Briefing", "Beyond Marrakech — and into the Atlas on horseback"),
        ("WSJ Briefing", "Burned-out U.S. doctors discuss horseback retreats"),
    ]
    for source, headline in cases:
        # Sanity check: the junk pattern itself fires on these.
        assert TRIAGE_JUNK_PATTERN.search(headline), (
            f"junk pattern must match {headline!r}"
        )
        bucket = _triage_classify({"source": source, "headline": headline})
        assert bucket == "default_drop", (
            f"editorial junk must route to default_drop: "
            f"got {bucket!r} for [{source}] {headline!r}"
        )


def test_triage_classify_routes_non_editorial_to_needs_triage():
    """Non-editorial sources still go through the Haiku triage path —
    the inverted-default policy doesn't apply to noisy WAM / social
    feeds where most content is genuinely ceremonial."""
    from pipeline.orchestrator import _triage_classify

    cases = [
        ("WAM", "Joint Statement following meeting between Abdullah bin Zayed, UK Foreign Secretary"),
        ("WAM", "Abu Dhabi Police hold workshop on safe school transport"),
        ("AINews (Latent Space)", "DeepSeek V4 KV cache measured at 9.62 GiB"),
        ("Middle East AI News", "Saudi Arabia to co-host UNESCO AI Forum"),
        ("X / @hhtbzayed", "I met with Varun Chandra, UK PM Special Adviser..."),
    ]
    for source, headline in cases:
        bucket = _triage_classify({"source": source, "headline": headline})
        assert bucket == "needs_triage", (
            f"non-editorial item must route to needs_triage: "
            f"got {bucket!r} for [{source}] {headline!r}"
        )


def test_triage_classify_protects_robotics_marathons():
    """Critical anti-pattern carryover from triage_prompt.md: a robotics
    marathon must NOT classify as default_drop. The robotics override
    operates at the `_triage_classify` function level (Python `re` doesn't
    support variable-width lookbehind, and the robotics keyword can
    appear before OR after the marathon mention in the headline)."""
    from pipeline.orchestrator import _triage_classify

    # Robot/humanoid marathons from editorial wires are capability demos,
    # not sports — must default_keep, not default_drop.
    keep = [
        "Humanoid robot completes Beijing half-marathon in record time",
        "China's robot marathon shows autonomous-locomotion advances",
        "Honor humanoid robot finishes Beijing half marathon in 51 minutes",
    ]
    for h in keep:
        bucket = _triage_classify({"source": "Bloomberg Briefing", "headline": h})
        assert bucket == "default_keep", (
            f"robotics-marathon must default_keep, got {bucket!r}: {h!r}"
        )

    # But a human marathon from the same wire is junk → default_drop.
    drop = [
        "Boston Marathon showcases human spirit and resilience",
        "London Marathon raises millions for charity",
    ]
    for h in drop:
        bucket = _triage_classify({"source": "Bloomberg Briefing", "headline": h})
        assert bucket == "default_drop", (
            f"human marathon must default_drop, got {bucket!r}: {h!r}"
        )


def test_partition_triage_buckets_4_way_split():
    """The 4-bucket partition is the production code path under the
    inverted-default fix. Confirm all four buckets populate correctly
    on a mixed input.

    Phase 1.5 cleanup: bypass_keep is now reserved for the narrow
    "junk match + hard-news override" case. Items that previously
    routed via the wide v3 regex (Meta layoffs, Trump cancels, etc.)
    now route to default_keep because no junk pattern fires.
    """
    from pipeline.orchestrator import _partition_triage_buckets

    items = [
        # 0: bypass_keep — Marathon (junk) + $500M (hard-news override)
        {"source": "Bloomberg Briefing",
         "headline": "Marathon Pharma raises $500 million Series F"},
        # 1: default_keep — no junk, no override needed
        {"source": "Bloomberg Briefing",
         "headline": "Meta to cut 10% of jobs, or 8,000 employees"},
        # 2: default_drop — pure junk
        {"source": "Axios AM/PM", "headline": "Boston Marathon showcases human spirit"},
        # 3: needs_triage — non-editorial
        {"source": "WAM", "headline": "Abu Dhabi Police hold workshop on safe school transport"},
        # 4: bypass_keep again — Judo (junk) + sanction (hard-news override)
        {"source": "Reuters",
         "headline": "Judo federation sanction blocks Olympic-qualifying meet"},
        # 5: default_keep — quiet analysis
        {"source": "FT Briefing", "headline": "European tech results reflect AI uncertainty"},
    ]
    bypass, default_keep, default_drop, triage_items, l2g = (
        _partition_triage_buckets(items)
    )
    assert bypass == {0, 4}
    assert default_keep == {1, 5}
    assert default_drop == {2}
    assert [it["headline"] for it in triage_items] == [items[3]["headline"]]
    assert l2g == {0: 3}


@pytest.mark.asyncio
async def test_triage_collected_items_inverted_default_keeps_quiet_editorial(
    monkeypatch, tmp_path
):
    """End-to-end: editorial items that don't match hard-news AND don't
    match junk must SURVIVE even when the (mocked) LLM drops everything.

    This is the core 2026-04-27 inverted-default invariant: paid wires
    don't get silently lost to Haiku flakiness on borderline-shaped
    headlines.
    """
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_collected_items

    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "false")
    monkeypatch.setattr(orchestrator, "TRIAGE_SINGLE_CALL_THRESHOLD", 1)
    monkeypatch.setattr(orchestrator, "TRIAGE_CHUNK_SIZE", 5)

    items = [
        # default_keep — must survive
        {"source": "Bloomberg Briefing", "headline": "Eurozone business activity contracts"},
        {"source": "FT Briefing", "headline": "Some quiet AI infrastructure analysis piece"},
        # default_keep (Phase 1.5: was bypass_keep under v3 regex; now
        # default_keep because the headline doesn't trigger junk and
        # the inverted default keeps it)
        {"source": "WSJ Briefing", "headline": "Meta to cut 10% of jobs, or 8,000 employees"},
        # bypass_keep — junk (marathon) + hard-news override ($500M)
        {"source": "Bloomberg Briefing",
         "headline": "Marathon Pharma raises $500 million Series F"},
        # default_drop — must NOT survive
        {"source": "Axios AM/PM", "headline": "Boston Marathon showcases human spirit"},
        # needs_triage — at mercy of mocked LLM (drops everything)
        {"source": "WAM", "headline": "Abu Dhabi Police hold workshop on safe school transport"},
    ]

    class _Resp:
        def __init__(self, t):
            class _C:
                def __init__(self, s): self.text = s
            self.content = [_C(t)]

    class _DropAllClient:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                return _Resp("[]")

    kept = await triage_collected_items(items, _DropAllClient())
    kept_headlines = {k["headline"] for k in kept}

    must_keep = {
        "Eurozone business activity contracts",
        "Some quiet AI infrastructure analysis piece",
        "Meta to cut 10% of jobs, or 8,000 employees",
        "Marathon Pharma raises $500 million Series F",
    }
    missing = must_keep - kept_headlines
    assert not missing, (
        f"inverted default failed to save quiet editorial: {missing}"
    )

    # default_drop and the WAM item (LLM dropped it) should be gone.
    must_drop = {
        "Boston Marathon showcases human spirit",
        "Abu Dhabi Police hold workshop on safe school transport",
    }
    bad_keeps = must_drop & kept_headlines
    assert not bad_keeps, f"items wrongly kept: {bad_keeps}"

    # Telemetry: triage_output JSON must record the new bucket counts.
    # Marathon Pharma (junk + override) -> bypass_keep (1).
    # Eurozone, quiet AI piece, Meta layoffs -> default_keep (3).
    # Boston Marathon -> default_drop (1).
    today = orchestrator.get_today_date()
    log = __import__("json").loads(
        (tmp_path / f"triage_output_{today}.json").read_text()
    )
    assert log.get("bypassed_count") == 1
    assert log.get("default_keep_count") == 3
    assert log.get("default_drop_count") == 1


@pytest.mark.asyncio
async def test_triage_save_drops_distinguishes_default_drop_reason(
    monkeypatch, tmp_path
):
    """The default_drop set carries a distinct drop_reason so /admin/drops
    can tell junk-pattern auto-drops apart from Haiku-judged drops.
    Useful for tuning the JUNK pattern without sifting Haiku noise.
    """
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_collected_items

    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "false")

    items = [
        # default_drop
        {"source": "Axios AM/PM", "headline": "Boston Marathon showcases human spirit"},
        # bypass_keep
        {"source": "WSJ Briefing", "headline": "Meta to cut 10% of jobs, or 8,000 employees"},
        # default_keep — kept, not in drops
        {"source": "Bloomberg Briefing", "headline": "Some quiet analysis"},
    ]

    class _Resp:
        def __init__(self, t):
            class _C:
                def __init__(self, s): self.text = s
            self.content = [_C(t)]

    class _AnyClient:
        class messages:
            @staticmethod
            async def create(**_kwargs):
                return _Resp("[]")

    await triage_collected_items(items, _AnyClient())

    today = orchestrator.get_today_date()
    drops = __import__("json").loads(
        (tmp_path / f"dropped_by_triage_{today}.json").read_text()
    )
    drop_rows = drops["dropped"]
    assert len(drop_rows) == 1
    assert drop_rows[0]["headline"] == "Boston Marathon showcases human spirit"
    assert drop_rows[0]["drop_reason"] == (
        "Triage: editorial-source junk-pattern match"
    ), (
        f"default_drop must use distinct drop_reason; got {drop_rows[0]['drop_reason']!r}"
    )


def test_source_is_editorial_prefix_match_covers_newsletter_variants():
    """The 2026-04-27 fix migrates from exact-match `frozenset` to
    prefix matching so newsletter variants like "Reuters Daily Briefing"
    or "Bloomberg Markets Briefing" count as editorial without needing
    each variant listed explicitly."""
    from pipeline.orchestrator import _source_is_editorial

    # Existing strict-match sources still match.
    assert _source_is_editorial("Bloomberg Briefing")
    assert _source_is_editorial("WSJ Briefing")
    assert _source_is_editorial("FT Briefing")
    assert _source_is_editorial("FT Edit")
    assert _source_is_editorial("Reuters")
    assert _source_is_editorial("Semafor Flagship")
    assert _source_is_editorial("Semafor Gulf")
    assert _source_is_editorial("Axios AM/PM")
    assert _source_is_editorial("Axios AI+")
    assert _source_is_editorial("TechCrunch")
    assert _source_is_editorial("The National")

    # NEW: variants that the strict-match frozenset missed.
    assert _source_is_editorial("Reuters Daily Briefing"), (
        "the 2026-04-27 'Reuters Daily Briefing' Witkoff-Kushner copy "
        "must be recognised as editorial"
    )
    assert _source_is_editorial("Bloomberg Markets Briefing")
    assert _source_is_editorial("Financial Times")  # raw FT name

    # MUST NOT bleed into non-editorial sources.
    assert not _source_is_editorial("WAM")
    assert not _source_is_editorial("AINews (Latent Space)")
    assert not _source_is_editorial("AlphaSignal")
    assert not _source_is_editorial("TLDR AI")
    assert not _source_is_editorial("The Deep View")
    assert not _source_is_editorial("Middle East AI News")
    assert not _source_is_editorial("X / @hhtbzayed")
    # Trailing-space anchor on "FT " must avoid matching "FTSE".
    assert not _source_is_editorial("FTSE 100")
    # Defensive: empty/None.
    assert not _source_is_editorial("")
    assert not _source_is_editorial(None)


def test_is_triage_bypass_eligible_narrow_override_semantics():
    """Phase 1.5: `_is_triage_bypass_eligible` returns True only for the
    narrow `bypass_keep` bucket — junk match + hard-news override. Items
    that route to `default_keep` (most editorial hard news) return False
    here; the broader auto-keep status is reflected by `_triage_classify`
    returning a value in {bypass_keep, default_keep}."""
    from pipeline.orchestrator import _is_triage_bypass_eligible, _triage_classify

    # bypass_keep — junk + hard-news override.
    assert _is_triage_bypass_eligible({
        "source": "Bloomberg Briefing",
        "headline": "Marathon Pharma raises $500 million Series F",
    }) is True

    # default_keep (NOT bypass_keep) — Meta layoffs no longer match the
    # narrow override surface; they auto-keep via inverted default.
    meta_item = {
        "source": "TechCrunch",
        "headline": "Meta to cut 10% of jobs, or 8,000 employees",
    }
    assert _is_triage_bypass_eligible(meta_item) is False
    assert _triage_classify(meta_item) == "default_keep"  # still auto-kept

    # Editorial source, soft-news headline → default_keep (auto-kept,
    # but not via the bypass surface).
    puff_item = {
        "source": "TechCrunch",
        "headline": "Some random TechCrunch puff piece",
    }
    assert _is_triage_bypass_eligible(puff_item) is False
    assert _triage_classify(puff_item) == "default_keep"

    # Non-editorial source → no bypass regardless of headline content.
    assert _is_triage_bypass_eligible({
        "source": "WAM",
        "headline": "WAM ministry announces $5 billion fund",
    }) is False

    # Empty headline → no bypass.
    assert _is_triage_bypass_eligible({
        "source": "Bloomberg Briefing",
        "headline": "",
    }) is False

    # Missing source field → no bypass (defensive).
    assert _is_triage_bypass_eligible({
        "headline": "Some company raises $1 billion",
    }) is False


def test_partition_triage_bypass_returns_combined_auto_keep():
    """Backward-compat shape: `_partition_triage_bypass` is a thin wrapper
    that returns (auto_keep, needs_triage_items, local_to_global).

    Under the post-2026-04-27 inverted-default fix, the auto_keep set
    contains BOTH `bypass_keep` (editorial+hard-news) AND `default_keep`
    (editorial+no-junk). The Bloomberg "Dubai Home Prices" item now
    auto-keeps via inverted default rather than going through Haiku.
    Items 2 ("Bloomberg Home Prices") and 4 ("TechCrunch puff piece")
    are now in auto_keep, not triage_items. WAM (item 1) is the only
    survivor that still needs Haiku triage.
    """
    from pipeline.orchestrator import _partition_triage_bypass

    items = [
        {"source": "TechCrunch", "headline": "Meta to cut 10% of jobs, or 8,000 employees"},  # 0: bypass_keep
        {"source": "WAM", "headline": "Abu Dhabi Police hold workshop on safe school transport"},  # 1: needs_triage
        {"source": "Bloomberg Briefing", "headline": "Dubai Home Prices Post First Declines After Boom"},  # 2: default_keep
        {"source": "Semafor Gulf", "headline": "Dubai greenlights $9 billion metro expansion"},  # 3: bypass_keep
        {"source": "TechCrunch", "headline": "Some random TechCrunch puff piece"},  # 4: default_keep
    ]

    auto_keep, triage_items, local_to_global = _partition_triage_bypass(items)

    assert auto_keep == {0, 2, 3, 4}, (
        "auto_keep must combine bypass_keep + default_keep under "
        "inverted-default policy"
    )
    assert [it["headline"] for it in triage_items] == [items[1]["headline"]]
    assert local_to_global == {0: 1}


def test_partition_triage_bypass_handles_empty_input():
    """Defensive: empty items list returns three empty containers."""
    from pipeline.orchestrator import _partition_triage_bypass

    bypass_set, triage_items, local_to_global = _partition_triage_bypass([])

    assert bypass_set == set()
    assert triage_items == []
    assert local_to_global == {}


@pytest.mark.asyncio
async def test_triage_collected_items_auto_keeps_editorial_hard_news(
    monkeypatch, tmp_path
):
    """End-to-end: the orchestrator wrapper must auto-keep editorial
    hard-news items even when the (mocked) LLM drops EVERYTHING. The
    Meta/Dubai/DOJ class of failure cannot recur.

    Phase 1.5 cleanup: most editorial hard news routes via default_keep
    (inverted default), not bypass_keep. The end-to-end behavior
    (auto-keep without LLM call) is unchanged."""
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_collected_items

    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "false")
    # Force chunked path so the 'chunked' branch is exercised too.
    monkeypatch.setattr(orchestrator, "TRIAGE_SINGLE_CALL_THRESHOLD", 1)
    monkeypatch.setattr(orchestrator, "TRIAGE_CHUNK_SIZE", 5)

    items = [
        # Auto-kept (default_keep under inverted default — no junk match).
        {"source": "TechCrunch", "headline": "Meta to cut 10% of jobs, or 8,000 employees"},
        {"source": "Semafor Gulf", "headline": "Dubai greenlights $9 billion metro expansion amid Iran war"},
        {"source": "Bloomberg Briefing", "headline": "DOJ Reclassifies Marijuana as Less Dangerous Drug"},
        # Junk — should be dropped by the LLM (non-editorial source).
        {"source": "WAM", "headline": "Boston Marathon showcases human spirit"},
        {"source": "WAM", "headline": "Average cocktail price hits $13.61 nationally"},
        {"source": "WAM", "headline": "Dubai Police hold workshop on safe school transport"},
    ]

    class _Content:
        def __init__(self, t):
            self.text = t

    class _Resp:
        def __init__(self, t):
            self.content = [_Content(t)]

    class _DropAllClient:
        """Mocked LLM that drops everything sent to it (returns empty
        keep-list). The bypass items NEVER reach this mock."""
        class messages:
            @staticmethod
            async def create(**_kwargs):
                return _Resp("[]")

    kept = await triage_collected_items(items, _DropAllClient())
    kept_headlines = {k["headline"] for k in kept}

    must_keep = {
        "Meta to cut 10% of jobs, or 8,000 employees",
        "Dubai greenlights $9 billion metro expansion amid Iran war",
        "DOJ Reclassifies Marijuana as Less Dangerous Drug",
    }
    missing = must_keep - kept_headlines
    assert not missing, (
        f"auto-keep failed to save 2026-04-24 hard-news headlines: {missing}"
    )
    # Junk items must NOT be in kept (LLM dropped them; auto-keep didn't apply).
    must_drop = {
        "Boston Marathon showcases human spirit",
        "Average cocktail price hits $13.61 nationally",
        "Dubai Police hold workshop on safe school transport",
    }
    bad_keeps = must_drop & kept_headlines
    assert not bad_keeps, (
        f"non-editorial junk wrongly auto-kept: {bad_keeps}"
    )

    # The triage_output JSON must record the new bucket counts.
    # Phase 1.5: hard-news editorial items now route via default_keep
    # (inverted default) since they don't match the junk pattern; the
    # narrow override only fires on junk-overlap headlines.
    today = orchestrator.get_today_date()
    log = __import__("json").loads(
        (tmp_path / f"triage_output_{today}.json").read_text()
    )
    assert log.get("bypassed_count") == 0, (
        f"no items match BOTH junk + override here, so bypassed_count "
        f"should be 0; got {log.get('bypassed_count')}"
    )
    assert log.get("default_keep_count") == 3, (
        f"3 hard-news editorial items must auto-keep via default_keep; "
        f"got {log.get('default_keep_count')}"
    )


@pytest.mark.asyncio
async def test_triage_sanity_check_auto_rescues_editorial_drops(
    monkeypatch, tmp_path
):
    """When TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL=true (default) and the
    inverse prompt rescues an editorial-source drop, the keep_set
    must be mutated in-place to include that index."""
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_sanity_check

    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "true")
    monkeypatch.setenv("TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL", "true")

    # 20 items, 0..14 kept, 15..19 dropped. 15 is editorial (Bloomberg);
    # the rest are WAM. The inverse prompt rescues local-1 (== global 15).
    items = []
    for i in range(15):
        items.append({"source": "WAM", "headline": f"K{i}"})
    items.append({"source": "Bloomberg Briefing", "headline": "Editorial-source drop"})  # 15
    for i in range(16, 20):
        items.append({"source": "WAM", "headline": f"D{i}"})
    keep_set = set(range(15))

    class _Content:
        def __init__(self, t): self.text = t

    class _Resp:
        def __init__(self, t): self.content = [_Content(t)]

    rescue_target_global = 15
    captured_payload = {}

    class _RescueOneClient:
        class messages:
            @staticmethod
            async def create(**kwargs):
                # Capture the prompt so we know which local index points
                # to the editorial item, then rescue it.
                msg = kwargs["messages"][0]["content"]
                captured_payload["prompt"] = msg
                # Find which line is "Editorial-source drop"
                for line in msg.splitlines():
                    if "Editorial-source drop" in line:
                        local_1 = int(line.split(".", 1)[0])
                        return _Resp(f'{{"keep_indices": [{local_1}]}}')
                return _Resp('{"keep_indices": []}')

    await triage_sanity_check(
        items, keep_set, _RescueOneClient(),
        today="2026-04-24", sample_size=5,
    )

    assert rescue_target_global in keep_set, (
        "auto-rescue must add the editorial-source drop back to keep_set "
        "(it was the only inverse-prompt rescue)"
    )

    # Audit artifact must record the rescue.
    log = __import__("json").loads(
        (tmp_path / "triage_sanity_check_2026-04-24.json").read_text()
    )
    assert log["auto_rescue_enabled"] is True
    assert log["rescued_count"] == 1
    rescued = [fp for fp in log["suspected_false_positives"] if fp.get("rescued")]
    assert len(rescued) == 1
    assert rescued[0]["source"] == "Bloomberg Briefing"


@pytest.mark.asyncio
async def test_triage_sanity_check_does_not_rescue_when_disabled(
    monkeypatch, tmp_path
):
    """When TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL=false, suspected FPs
    are still logged but keep_set is NOT mutated — preserving the old
    alert-only contract for callers that don't want auto-rescue."""
    from pipeline import orchestrator
    from pipeline.orchestrator import triage_sanity_check

    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("TRIAGE_SANITY_CHECK_ENABLED", "true")
    monkeypatch.setenv("TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL", "false")

    items = []
    for i in range(15):
        items.append({"source": "WAM", "headline": f"K{i}"})
    items.append({"source": "Bloomberg Briefing", "headline": "Editorial-source drop"})  # 15
    for i in range(16, 20):
        items.append({"source": "WAM", "headline": f"D{i}"})
    keep_set = set(range(15))
    pre = set(keep_set)

    class _Content:
        def __init__(self, t): self.text = t
    class _Resp:
        def __init__(self, t): self.content = [_Content(t)]

    class _RescueOneClient:
        class messages:
            @staticmethod
            async def create(**kwargs):
                msg = kwargs["messages"][0]["content"]
                for line in msg.splitlines():
                    if "Editorial-source drop" in line:
                        local_1 = int(line.split(".", 1)[0])
                        return _Resp(f'{{"keep_indices": [{local_1}]}}')
                return _Resp('{"keep_indices": []}')

    await triage_sanity_check(
        items, keep_set, _RescueOneClient(),
        today="2026-04-24", sample_size=5,
    )

    assert keep_set == pre, (
        "auto_rescue=false must leave keep_set unchanged"
    )
    log = __import__("json").loads(
        (tmp_path / "triage_sanity_check_2026-04-24.json").read_text()
    )
    assert log["auto_rescue_enabled"] is False
    assert log["rescued_count"] == 0
    # The FP itself should still be recorded with rescued=false.
    rescued_flags = [
        fp.get("rescued") for fp in log["suspected_false_positives"]
    ]
    assert rescued_flags == [False]


def test_sanity_check_sample_indices_floors_editorial_share():
    """When editorial-source drops exist, the stratified sample must
    pick at least `floor * sample_size` of them (rounded down, min 1)."""
    from pipeline.orchestrator import (
        _build_sanity_check_sample_indices,
        TRIAGE_SANITY_EDITORIAL_SAMPLE_FLOOR,
    )

    # 20 items dropped: 4 editorial, 16 other. sample_size=10, floor=0.5
    # → 5 editorial + 5 other; but only 4 editorial exist, so all 4
    # are sampled and 6 from `other` to total 10.
    pool = (
        [{"global_index": i, "is_editorial": True} for i in range(4)]
        + [{"global_index": 100 + i, "is_editorial": False} for i in range(16)]
    )

    indices = _build_sanity_check_sample_indices(pool, sample_size=10)

    assert len(indices) == 10
    editorial_in_sample = [i for i in indices if i < 100]
    other_in_sample = [i for i in indices if i >= 100]
    # All 4 editorial drops must be sampled (they're scarce).
    assert sorted(editorial_in_sample) == [0, 1, 2, 3], (
        f"all 4 editorial drops should be in sample; got {editorial_in_sample}"
    )
    # The remaining 6 slots come from `other`.
    assert len(other_in_sample) == 6


def test_sanity_check_sample_indices_uniform_when_no_editorial():
    """When no editorial-source drops exist, the sample is a plain
    uniform pick from the full pool (no stratification needed)."""
    from pipeline.orchestrator import _build_sanity_check_sample_indices

    pool = [{"global_index": i, "is_editorial": False} for i in range(50)]

    indices = _build_sanity_check_sample_indices(pool, sample_size=10)

    assert len(indices) == 10
    assert all(isinstance(i, int) and 0 <= i < 50 for i in indices)
    # No duplicates.
    assert len(set(indices)) == 10
