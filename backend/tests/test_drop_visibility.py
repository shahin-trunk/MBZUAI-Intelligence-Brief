"""Phase 1 drop-visibility tests.

Covers the audit-trail changes that make every dropped candidate visible in
the admin Drops view (and therefore in the curation workspace Filtered
Candidates panel). These tests do NOT hit the Anthropic API — they operate on
synthetic JSON files and the orchestrator/ingest helpers directly.

Why these tests exist: before Phase 1, four drop classes were silently lost
(triage, pre-Gatekeeper previous-brief overlap, post-Gatekeeper overlap,
Gatekeeper implicit). Today's Crown Prince/China visit failure slipped through
this exact gap. These tests lock the new visibility guarantees so they cannot
silently regress again.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import config  # noqa: E402
from ingest_brief import _parse_dropped_items  # noqa: E402
from pipeline.orchestrator import flag_previous_brief_overlaps  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_output(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def tmp_output_dir(tmp_path, monkeypatch):
    """Swap config.OUTPUT_DIR (and the OUTPUT_DIR imported into ingest_brief)
    for a scratch directory so we can exercise _parse_dropped_items without
    touching the real output/ folder."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    import ingest_brief

    monkeypatch.setattr(ingest_brief, "OUTPUT_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# _parse_dropped_items — reads the new stage files
# ---------------------------------------------------------------------------


def test_parse_dropped_items_reads_triage(tmp_output_dir):
    date = "2026-04-15"
    _write_output(
        tmp_output_dir,
        f"dropped_by_triage_{date}.json",
        {
            "dropped_count": 2,
            "dropped": [
                {
                    "headline": "Company A opens new office",
                    "source": "WAM",
                    "source_url": "https://example.com/a",
                    "drop_reason": "Triage: not relevant to MBZUAI brief",
                },
                {
                    "headline": "Company B hosts community event",
                    "source": "ADMO",
                    "source_url": "https://example.com/b",
                    "drop_reason": "Triage: not relevant to MBZUAI brief",
                },
            ],
        },
    )

    rows = _parse_dropped_items(date)
    triage_rows = [r for r in rows if r["dropped_at_stage"] == "triage"]
    assert len(triage_rows) == 2
    assert all(r["drop_reason"].startswith("Triage:") for r in triage_rows)
    assert {r["source_name"] for r in triage_rows} == {"WAM", "ADMO"}


def test_parse_dropped_items_reads_previous_brief_overlap(tmp_output_dir):
    date = "2026-04-15"
    _write_output(
        tmp_output_dir,
        f"dropped_by_previous_brief_overlap_{date}.json",
        {
            "dropped_count": 1,
            "dropped": [
                {
                    "headline": "Crown Prince meets chairmen of leading Chinese companies",
                    "source": "Abu Dhabi Media Office",
                    "source_url": "https://example.com/meets",
                    "composite_score": 7.5,
                    "drop_reason": "Previous brief repeat — matches ...",
                }
            ],
        },
    )

    rows = _parse_dropped_items(date)
    overlap_rows = [
        r for r in rows if r["dropped_at_stage"] == "previous_brief_overlap"
    ]
    assert len(overlap_rows) == 1
    assert overlap_rows[0]["composite_score"] == 7.5
    assert overlap_rows[0]["source_name"] == "Abu Dhabi Media Office"


def test_parse_dropped_items_reads_history_dedup(tmp_output_dir):
    date = "2026-04-17"
    _write_output(
        tmp_output_dir,
        f"dropped_by_history_dedup_{date}.json",
        {
            "dropped_count": 2,
            "dropped": [
                {
                    "headline": "UAE signs AI compute partnership with Japan",
                    "source": "WAM",
                    "source_url": "https://example.com/jp",
                    "composite_score": 7.2,
                    "drop_reason": (
                        'History dedup (semantic) — matches '
                        '"UAE-Japan AI compute MOU" from 2026-04-15 (same event)'
                    ),
                    "_matched_brief_date": "2026-04-15",
                    "_matched_headline": "UAE-Japan AI compute MOU",
                },
                {
                    "headline": "G42 expands data-centre footprint",
                    "source": "Abu Dhabi Media Office",
                    "source_url": "https://example.com/g42",
                    "composite_score": None,
                    "drop_reason": "History dedup (semantic) — duplicate of earlier coverage",
                    "_matched_brief_date": None,
                    "_matched_headline": None,
                },
            ],
        },
    )

    rows = _parse_dropped_items(date)
    history_dedup_rows = [r for r in rows if r["dropped_at_stage"] == "history_dedup"]
    assert len(history_dedup_rows) == 2
    assert all(
        r["drop_reason"].startswith("History dedup") for r in history_dedup_rows
    )
    assert history_dedup_rows[0]["composite_score"] == 7.2
    assert history_dedup_rows[1]["composite_score"] is None
    assert {r["source_name"] for r in history_dedup_rows} == {
        "WAM",
        "Abu Dhabi Media Office",
    }


def test_parse_dropped_items_reads_gatekeeper_implicit(tmp_output_dir):
    date = "2026-04-15"
    _write_output(
        tmp_output_dir,
        f"dropped_by_gatekeeper_{date}.json",
        {
            "gatekeeper_model_dropped": [
                {
                    "headline": "Model drop A",
                    "composite_score": 3.0,
                    "drop_reason": "Not significant",
                }
            ],
            "implicit_dropped": [
                {
                    "headline": "Implicit drop X",
                    "source": "WAM",
                    "source_url": "https://example.com/x",
                    "drop_reason": "Gatekeeper implicit (not returned in selected or dropped)",
                }
            ],
            "final_dropped": [],
        },
    )

    rows = _parse_dropped_items(date)
    model = [r for r in rows if r["dropped_at_stage"] == "gatekeeper"]
    implicit = [r for r in rows if r["dropped_at_stage"] == "gatekeeper_implicit"]
    assert len(model) == 1
    assert len(implicit) == 1
    assert "implicit" in implicit[0]["drop_reason"].lower()


def test_parse_dropped_items_reclassifies_post_gatekeeper_overlap(tmp_output_dir):
    """Drops tagged with _stage=post_gatekeeper_overlap must NOT show up as
    generic gatekeeper drops. They get their own stage label."""
    date = "2026-04-15"
    _write_output(
        tmp_output_dir,
        f"dropped_by_gatekeeper_{date}.json",
        {
            "gatekeeper_model_dropped": [
                {
                    "headline": "Regular drop A",
                    "composite_score": 3.0,
                    "drop_reason": "Not significant",
                },
                {
                    "headline": "Crown Prince China visit",
                    "composite_score": 8.0,
                    "drop_reason": "Post-Gatekeeper overlap: headline similarity 0.46 ...",
                    "_stage": "post_gatekeeper_overlap",
                    "source": "Abu Dhabi Media Office",
                },
            ],
            "implicit_dropped": [],
            "final_dropped": [],
        },
    )

    rows = _parse_dropped_items(date)
    gatekeeper_rows = [r for r in rows if r["dropped_at_stage"] == "gatekeeper"]
    overlap_rows = [
        r for r in rows if r["dropped_at_stage"] == "post_gatekeeper_overlap"
    ]
    assert len(gatekeeper_rows) == 1
    assert gatekeeper_rows[0]["headline"] == "Regular drop A"
    assert len(overlap_rows) == 1
    assert overlap_rows[0]["headline"] == "Crown Prince China visit"


def test_parse_dropped_items_no_double_write(tmp_output_dir):
    """If a post_gatekeeper_overlap drop appears in both gatekeeper_model_dropped
    (reclassified via _stage) and final_dropped, we must write exactly one row."""
    date = "2026-04-15"
    drop = {
        "headline": "Dup headline",
        "composite_score": 8.0,
        "drop_reason": "Post-Gatekeeper overlap: ...",
        "_stage": "post_gatekeeper_overlap",
    }
    _write_output(
        tmp_output_dir,
        f"dropped_by_gatekeeper_{date}.json",
        {
            "gatekeeper_model_dropped": [drop],
            "implicit_dropped": [],
            "final_dropped": [drop],  # same row, also in final_dropped
        },
    )
    rows = _parse_dropped_items(date)
    overlap_rows = [
        r for r in rows if r["dropped_at_stage"] == "post_gatekeeper_overlap"
    ]
    assert len(overlap_rows) == 1


# ---------------------------------------------------------------------------
# flag_previous_brief_overlaps — drop records now carry source + source_url
# ---------------------------------------------------------------------------


def test_flag_previous_brief_overlaps_preserves_source(monkeypatch):
    """Phase 1 enrichment: drop records for overlap must include source and
    source_url so the Drops admin view has enough info to display them."""
    # Mock get_recent_history_headlines to return a matching headline so
    # flag_previous_brief_overlaps produces a hard drop. (The function
    # now reads from the merged published + pending history loader; see
    # config.get_recent_history_headlines for details.)
    import pipeline.orchestrator as orch

    fake_prev = json.dumps([
        {
            "brief_date": "2026-04-13",
            "headline": "Crown Prince of Abu Dhabi arrives in Beijing on official state visit",
            "section": "UAE",
            "entities": ["Khaled bin Mohamed bin Zayed", "China", "Beijing"],
            "main_bullet": (
                "H.H. Sheikh Khaled bin Mohamed bin Zayed Al Nahyan arrived in "
                "Beijing at the head of a high-level delegation."
            ),
        }
    ])
    monkeypatch.setattr(orch, "get_recent_history_headlines", lambda: fake_prev)

    items = [
        {
            "headline": (
                "Crown Prince of Abu Dhabi arrives in Beijing on official state visit"
            ),
            "summary": "Arrival in Beijing at the head of a delegation.",
            "source": "Abu Dhabi Media Office",
            "source_url": "https://example.com/arrives",
            "entities": ["Khaled", "China", "Beijing"],
            "composite_score": 8.0,
        }
    ]

    kept, hard, soft = flag_previous_brief_overlaps(items)
    assert len(hard) == 1
    drop = hard[0]
    # These are the new fields added by Phase 1:
    assert drop["source"] == "Abu Dhabi Media Office"
    assert drop["source_url"] == "https://example.com/arrives"
    # Pre-existing fields should still be populated.
    assert drop["composite_score"] == 8.0
    assert "Previous brief repeat" in drop["drop_reason"]


# ---------------------------------------------------------------------------
# Implicit drops — headline diff logic
# ---------------------------------------------------------------------------


def test_implicit_drop_detection_normalized_headlines():
    """The orchestrator diffs input vs output headlines using normalized
    (lowercased + stripped) comparison to tolerate minor Gatekeeper edits.
    This is a pure-python smoke test of that normalization to protect it."""
    def _norm(h: str) -> str:
        return (h or "").strip().lower()

    inputs = {
        _norm("President of the People's Republic of China receives Crown Prince"),
        _norm("Anthropic launches Claude Mythos"),
        _norm("G42 signs partnership with Microsoft"),
    }
    # Gatekeeper returns only 2 of 3; third is silently lost.
    outputs = {
        _norm("  Anthropic Launches Claude Mythos  "),  # case + whitespace
        _norm("G42 signs partnership with Microsoft"),
    }
    implicit = inputs - outputs
    assert len(implicit) == 1
    assert "president" in next(iter(implicit))
