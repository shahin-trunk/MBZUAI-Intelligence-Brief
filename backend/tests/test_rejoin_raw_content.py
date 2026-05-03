"""Regression tests for pipeline.orchestrator.rejoin_raw_content.

Pins the 2026-04-22 smart-quote fix: the Gatekeeper LLM silently rewrites
U+2019 → U+0027 when echoing scout URLs, so byte-exact URL-keyed lookup
used to miss for WAM slugs like `...world's-first-native-...`. The four
cases here cover the matching surface: single candidate, multiple-
candidates headline tiebreak, no match, and the smart-quote regression.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.orchestrator import (  # noqa: E402
    _build_raw_content_lookup,
    rejoin_raw_content,
)


def _scout_item(
    headline: str,
    url: str,
    raw_content: str,
    additional_context: str = "",
) -> dict:
    return {
        "headline": headline,
        "source_url": url,
        "raw_content": raw_content,
        "additional_context": additional_context,
        "source": "TestSource",
    }


def _gatekeeper_item(headline: str, url: str) -> dict:
    """Gatekeeper-shaped items have no raw_content — it was stripped before
    the model saw them and the rejoin step is what puts it back."""
    return {
        "headline": headline,
        "source_url": url,
        "source": "TestSource",
    }


# ---------------------------------------------------------------------------
# 1. Single candidate — URL keys match byte-exact.
# ---------------------------------------------------------------------------
def test_rejoin_single_candidate_exact_url() -> None:
    scout = [
        _scout_item(
            "Story A",
            "https://example.com/story-a",
            "full body of story A",
            "context A",
        ),
    ]
    selected = [_gatekeeper_item("Story A", "https://example.com/story-a")]

    rejoined, warnings = rejoin_raw_content(selected, _build_raw_content_lookup(scout))

    assert warnings == []
    assert rejoined[0]["raw_content"] == "full body of story A"
    assert rejoined[0]["additional_context"] == "context A"


# ---------------------------------------------------------------------------
# 2. Multiple candidates at the same URL — tiebreak by headline similarity.
# ---------------------------------------------------------------------------
def test_rejoin_multiple_candidates_headline_tiebreak() -> None:
    shared_url = "https://example.com/multi"
    scout = [
        _scout_item("Apple earnings beat expectations", shared_url, "apple body"),
        _scout_item("Microsoft earnings beat expectations", shared_url, "microsoft body"),
    ]
    selected = [
        _gatekeeper_item(
            "Microsoft earnings beat expectations",
            shared_url,
        )
    ]

    rejoined, warnings = rejoin_raw_content(selected, _build_raw_content_lookup(scout))

    assert warnings == []
    assert rejoined[0]["raw_content"] == "microsoft body"


# ---------------------------------------------------------------------------
# 3. No match — rejoin zeroes raw_content and logs a warning.
# ---------------------------------------------------------------------------
def test_rejoin_no_match_warns_and_zeroes() -> None:
    scout = [
        _scout_item(
            "Story A",
            "https://example.com/story-a",
            "full body of story A",
        ),
    ]
    selected = [_gatekeeper_item("Story B", "https://example.com/story-b")]

    rejoined, warnings = rejoin_raw_content(selected, _build_raw_content_lookup(scout))

    assert rejoined[0]["raw_content"] == ""
    assert rejoined[0]["additional_context"] == ""
    assert len(warnings) == 1
    assert "Rejoin FAILED" in warnings[0]


# ---------------------------------------------------------------------------
# 4. Smart-quote regression — the actual 2026-04-22 fix.
#    Scout URL carries U+2019; the Gatekeeper-echoed URL is U+0027. Rejoin
#    must succeed because the lookup key normalises both to ASCII.
# ---------------------------------------------------------------------------
def test_rejoin_smart_quote_to_ascii_regression() -> None:
    # Scout URL as collected (curly apostrophe) — mirrors the real
    # 2026-04-22 s003 DIFC URL shape.
    scout_url = (
        "https://www.wam.ae/en/article/"
        "bzttt2u-difc-become-world\u2019s-first-native-financial-centre"
    )
    # Gatekeeper-echoed URL (ASCII apostrophe) — what the LLM actually
    # produced in today's pipeline.
    gk_url = (
        "https://www.wam.ae/en/article/"
        "bzttt2u-difc-become-world's-first-native-financial-centre"
    )
    assert scout_url != gk_url, "test premise: these must differ byte-wise"

    scout = [
        _scout_item(
            "DIFC to become world\u2019s first AI Native financial centre",
            scout_url,
            "DIFC raw body " * 200,  # plausible ~2.6k-char body
            "",
        ),
    ]
    selected = [
        _gatekeeper_item(
            "DIFC to become world's first AI Native financial centre",
            gk_url,
        ),
    ]

    rejoined, warnings = rejoin_raw_content(selected, _build_raw_content_lookup(scout))

    assert warnings == [], f"expected no warnings, got: {warnings}"
    assert rejoined[0]["raw_content"].startswith("DIFC raw body")
    assert len(rejoined[0]["raw_content"]) > 0
