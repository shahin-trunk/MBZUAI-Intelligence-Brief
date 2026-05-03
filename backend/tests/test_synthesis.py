"""Phase 2 Synthesis-stage tests.

Offline tests only — they do NOT call Anthropic. The live Anthropic call is
covered by the replay script `backend/replay_china_visit_2026_04_15.py`.

What we lock here:
1. Schema validation — malformed LLM output fails loudly, not silently.
2. Annotation merging — cluster fields reach each item correctly.
3. Fail-open behavior — a failed Synthesis call does NOT drop items;
   the pipeline continues with None annotations.
4. Contract sanity — every cluster_member id must have an annotation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.schemas import SynthesisOutput  # noqa: E402
from pipeline.synthesis import (  # noqa: E402
    apply_synthesis_annotations,
    clear_synthesis_annotations,
)


# ---------------------------------------------------------------------------
# apply_synthesis_annotations — the merge function that feeds Gatekeeper
# ---------------------------------------------------------------------------


def test_apply_annotations_merges_cluster_fields_onto_items():
    items = [
        {"headline": "Crown Prince arrives in Beijing"},
        {"headline": "Xi receives Crown Prince"},
        {"headline": "Unrelated tech story"},
    ]
    syn_result = {
        "clusters": [
            {
                "cluster_id": "china-visit-2026-04-15",
                "event_key": "uae-crown-prince-china-apr-2026",
                "composite_headline": "Crown Prince state visit to China",
                "member_item_ids": [0, 1],
                "continuity_status": "continuation",
                "continuity_reference": "2026-04-13 earlier arrival",
                "significance_tier": "head_of_state",
                "rationale": "Same multi-day state visit",
            },
            {
                "cluster_id": "tech-solo",
                "event_key": "tech-solo",
                "composite_headline": "Unrelated tech story",
                "member_item_ids": [2],
                "continuity_status": "new_story",
                "significance_tier": "standard",
                "rationale": "Solo item",
            },
        ],
        "item_annotations": [
            {
                "item_id": 0,
                "cluster_id": "china-visit-2026-04-15",
                "facet": "arrival",
                "continuity_status": "continuation",
            },
            {
                "item_id": 1,
                "cluster_id": "china-visit-2026-04-15",
                "facet": "leader_bilateral",
                "continuity_status": "continuation",
            },
            {
                "item_id": 2,
                "cluster_id": "tech-solo",
                "facet": "main",
                "continuity_status": "new_story",
            },
        ],
    }

    annotated, unannotated = apply_synthesis_annotations(items, syn_result)

    assert annotated == 3
    assert unannotated == 0

    # Cluster members share cluster metadata
    assert items[0]["cluster_id"] == "china-visit-2026-04-15"
    assert items[1]["cluster_id"] == "china-visit-2026-04-15"
    assert items[0]["cluster_event_key"] == items[1]["cluster_event_key"]
    assert items[0]["cluster_significance_tier"] == "head_of_state"
    assert items[1]["cluster_significance_tier"] == "head_of_state"

    # But facets differ within the cluster
    assert items[0]["facet"] == "arrival"
    assert items[1]["facet"] == "leader_bilateral"

    # Solo item gets its own cluster metadata
    assert items[2]["cluster_id"] == "tech-solo"
    assert items[2]["cluster_significance_tier"] == "standard"


def test_apply_annotations_failopen_on_missing_annotation():
    """If the Synthesis output omits an annotation for an item, we set the
    fields to None rather than leaving them absent — Gatekeeper expects a
    consistent schema."""
    items = [{"headline": "A"}, {"headline": "B"}]
    syn_result = {
        "clusters": [],
        "item_annotations": [
            # Only item 0 is annotated; item 1 is missing.
            {
                "item_id": 0,
                "cluster_id": "solo",
                "facet": "main",
                "continuity_status": "new_story",
            },
        ],
    }
    annotated, unannotated = apply_synthesis_annotations(items, syn_result)
    assert annotated == 1
    assert unannotated == 1
    # Item 1 fields must be present (None) so the Gatekeeper sees a consistent schema.
    assert items[1]["cluster_id"] is None
    assert items[1]["facet"] is None
    assert items[1]["cluster_significance_tier"] is None


def test_clear_synthesis_annotations_sets_all_fields_to_none():
    items = [
        {
            "headline": "A",
            "cluster_id": "stale",
            "facet": "stale",
            "cluster_significance_tier": "major",
        },
    ]
    clear_synthesis_annotations(items)
    for field in (
        "cluster_id",
        "cluster_event_key",
        "cluster_composite_headline",
        "cluster_continuity",
        "cluster_continuity_reference",
        "cluster_significance_tier",
        "facet",
    ):
        assert items[0][field] is None


# ---------------------------------------------------------------------------
# SynthesisOutput Pydantic schema validation
# ---------------------------------------------------------------------------


def test_synthesis_output_rejects_invalid_continuity_status():
    payload = {
        "clusters": [
            {
                "cluster_id": "x",
                "event_key": "x",
                "composite_headline": "x",
                "member_item_ids": [0],
                # bogus — schema is Literal["new_story","continuation","restatement"]
                "continuity_status": "random_value",
                "rationale": "test",
            }
        ],
        "item_annotations": [
            {
                "item_id": 0,
                "cluster_id": "x",
                "continuity_status": "new_story",
            }
        ],
    }
    with pytest.raises(Exception):  # pydantic ValidationError
        SynthesisOutput.model_validate(payload)


def test_synthesis_output_accepts_valid_minimal_shape():
    payload = {
        "clusters": [
            {
                "cluster_id": "x",
                "event_key": "x",
                "composite_headline": "x",
                "member_item_ids": [0],
                "continuity_status": "new_story",
                "rationale": "test",
            }
        ],
        "item_annotations": [
            {
                "item_id": 0,
                "cluster_id": "x",
                "continuity_status": "new_story",
            }
        ],
    }
    out = SynthesisOutput.model_validate(payload)
    assert len(out.clusters) == 1
    assert out.clusters[0].significance_tier == "standard"  # default


def test_synthesis_output_allows_head_of_state_tier():
    """Regression: head_of_state is the tier that should preserve granularity
    — the prompt explicitly relies on this value. Lock the Literal union."""
    payload = {
        "clusters": [
            {
                "cluster_id": "x",
                "event_key": "x",
                "composite_headline": "x",
                "member_item_ids": [0],
                "continuity_status": "continuation",
                "continuity_reference": "prior",
                "significance_tier": "head_of_state",
                "rationale": "Crown Prince state visit",
            }
        ],
        "item_annotations": [
            {
                "item_id": 0,
                "cluster_id": "x",
                "facet": "leader_bilateral",
                "continuity_status": "continuation",
            }
        ],
    }
    out = SynthesisOutput.model_validate(payload)
    assert out.clusters[0].significance_tier == "head_of_state"


# ---------------------------------------------------------------------------
# Orchestrator-level contract: GATEKEEPER_KEEP_FIELDS receives cluster keys
# ---------------------------------------------------------------------------


def test_gatekeeper_keep_fields_includes_cluster_keys():
    """The Gatekeeper strips items down to GATEKEEPER_KEEP_FIELDS before
    sending them. Cluster fields MUST be in that allow-list or the
    Gatekeeper never sees Synthesis annotations."""
    from pipeline.orchestrator import GATEKEEPER_KEEP_FIELDS

    required = {
        "cluster_id",
        "cluster_event_key",
        "cluster_composite_headline",
        "cluster_continuity",
        "cluster_continuity_reference",
        "cluster_significance_tier",
        "facet",
    }
    missing = required - GATEKEEPER_KEEP_FIELDS
    assert not missing, f"GATEKEEPER_KEEP_FIELDS missing: {missing}"
