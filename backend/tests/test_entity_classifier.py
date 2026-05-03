"""Entity Classifier stage tests.

Offline tests only — they do NOT call Anthropic. The live Haiku call is
exercised by `backend/replay_entity_classifier.py` against captured
`ghostwriter_output_*.json` artifacts.

Locks the three contracts the frontend depends on:
1. Schema validation — malformed category → loud failure.
2. Merge logic — the orchestrator's helper writes primary_entity_category
   onto each item by id and sets None for items with no classification.
3. Fail-open — a failed classifier call must NOT break the pipeline; every
   item still has the field set (to None).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.schemas import EntityClassificationOutput  # noqa: E402
from pipeline.entity_classifier import (  # noqa: E402
    apply_entity_classifications,
    build_classifier_input_items,
)
from pipeline.entity_category import infer_entity_category  # noqa: E402


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_schema_accepts_minimal_valid_output():
    payload = {
        "classifications": [
            {"id": "a", "primary_entity_category": "university"},
            {
                "id": "b",
                "primary_entity_category": "country",
                "rationale": "UAE is a sovereign state",
            },
        ]
    }
    out = EntityClassificationOutput.model_validate(payload)
    assert len(out.classifications) == 2
    assert out.classifications[0].primary_entity_category == "university"
    assert out.classifications[1].rationale.startswith("UAE")


def test_schema_rejects_unknown_category():
    payload = {
        "classifications": [
            {"id": "a", "primary_entity_category": "conglomerate"},  # not in enum
        ]
    }
    with pytest.raises(Exception):  # pydantic ValidationError
        EntityClassificationOutput.model_validate(payload)


def test_schema_accepts_all_ten_categories():
    """Regression: every category in the plan must be valid. If anyone
    narrows the Literal, this test fails loudly."""
    cats = [
        "company",
        "university",
        "government",
        "energy",
        "finance",
        "defense",
        "org",
        "model",
        "country",
        "other",
    ]
    payload = {
        "classifications": [
            {"id": f"i{i}", "primary_entity_category": c}
            for i, c in enumerate(cats)
        ]
    }
    out = EntityClassificationOutput.model_validate(payload)
    assert [c.primary_entity_category for c in out.classifications] == cats


# ---------------------------------------------------------------------------
# apply_entity_classifications — merge logic
# ---------------------------------------------------------------------------


def test_apply_merges_by_id_and_sets_missing_to_none():
    items = [
        {"id": "a", "primary_entity": "MBZUAI", "headline": "MBZUAI launches center", "section": "Regional Research & Academic Events"},
        {"id": "b", "primary_entity": "Alibaba", "headline": "Alibaba expands cloud offer", "section": "International Business & Technology"},
        {"id": "c", "primary_entity": None},  # no entity → classifier skipped it
    ]
    result = {
        "classifications": [
            {"id": "a", "primary_entity_category": "university"},
            {"id": "b", "primary_entity_category": "company"},
        ]
    }
    annotated, unannotated = apply_entity_classifications(items, result)

    assert annotated == 2
    assert unannotated == 1
    assert items[0]["primary_entity_category"] == "university"
    assert items[0]["primary_subject"] == "MBZUAI"
    assert items[0]["primary_subject_type"] == "organization"
    assert items[1]["primary_entity_category"] == "company"
    assert items[1]["primary_subject"] == "Alibaba"
    assert items[1]["primary_subject_type"] == "organization"
    assert items[0]["badge_subject"] == "MBZUAI"
    assert items[0]["badge_subject_type"] == "organization"
    assert items[0]["badge_subject_category"] == "university"
    assert items[1]["badge_subject"] == "Alibaba"
    assert items[1]["badge_subject_type"] == "organization"
    assert items[1]["badge_subject_category"] == "company"
    # Item c had no entity and no strong fallback signal, so the field is
    # still explicitly present for schema consistency.
    assert items[2]["primary_entity_category"] is None
    assert items[2]["primary_subject"] is None
    assert items[2]["primary_subject_type"] is None
    assert items[2]["badge_subject"] is None
    assert items[2]["badge_subject_type"] is None
    assert items[2]["badge_subject_category"] is None


def test_apply_handles_none_result_as_failopen():
    """When the classifier stage fails, deterministic fallback should still
    classify the items it can, without breaking the pipeline."""
    items = [
        {
            "id": "a",
            "primary_entity": "CENTCOM",
            "headline": "US blockade of Iranian ports holds through first 24 hours",
            "section": "International Politics & Policy",
            "entities": ["CENTCOM", "Iran"],
        },
        {"id": "b", "primary_entity": "Y"},
    ]
    annotated, unannotated = apply_entity_classifications(items, None)
    assert annotated == 1
    assert unannotated == 1
    assert items[0]["primary_entity_category"] == "defense"
    assert items[0]["primary_subject"] == "CENTCOM"
    assert items[0]["primary_subject_type"] == "organization"
    assert items[0]["badge_subject"] == "United States"
    assert items[0]["badge_subject_type"] == "country"
    assert items[0]["badge_subject_category"] == "country"
    assert items[1]["primary_entity_category"] is None
    assert items[1]["primary_subject"] is None
    assert items[1]["primary_subject_type"] is None
    assert items[1]["badge_subject"] is None
    assert items[1]["badge_subject_type"] is None
    assert items[1]["badge_subject_category"] is None


def test_apply_is_idempotent():
    """Running the merge twice with the same result yields the same state."""
    items = [{"id": "a", "primary_entity": "MBZUAI"}]
    result = {
        "classifications": [{"id": "a", "primary_entity_category": "university"}]
    }
    apply_entity_classifications(items, result)
    apply_entity_classifications(items, result)
    assert items[0]["primary_entity_category"] == "university"


def test_apply_ignores_classifications_for_unknown_ids():
    """If the classifier returns an id that's not in our item list (can
    happen if Haiku hallucinates an id), we ignore it silently."""
    items = [{"id": "a", "primary_entity": "X"}]
    result = {
        "classifications": [
            {"id": "a", "primary_entity_category": "company"},
            {"id": "ghost", "primary_entity_category": "company"},
        ]
    }
    annotated, _ = apply_entity_classifications(items, result)
    assert annotated == 1
    assert items[0]["primary_entity_category"] == "company"


def test_apply_uses_heuristic_when_item_missing_from_classifier_output():
    items = [
        {
            "id": "a",
            "primary_entity": "Mubadala Capital",
            "headline": "Mubadala Capital joins strategic funding round",
            "section": "International Business & Technology",
        }
    ]
    annotated, unannotated = apply_entity_classifications(items, {"classifications": []})
    assert annotated == 1
    assert unannotated == 0
    assert items[0]["primary_entity_category"] == "finance"
    assert items[0]["primary_subject"] == "Mubadala Capital"
    assert items[0]["primary_subject_type"] == "organization"
    assert items[0]["badge_subject"] == "Mubadala Capital"
    assert items[0]["badge_subject_type"] == "organization"
    assert items[0]["badge_subject_category"] == "finance"


def test_apply_preserves_person_subject_and_country_badge():
    items = [
        {
            "id": "a",
            "primary_entity": "H.H. Sheikh Khaled bin Mohamed bin Zayed Al Nahyan",
            "headline": "President meets delegation in Abu Dhabi",
            "section": "UAE",
        }
    ]
    annotated, unannotated = apply_entity_classifications(items, {"classifications": []})
    assert annotated == 1
    assert unannotated == 0
    assert items[0]["primary_subject"] == "H.H. Sheikh Khaled bin Mohamed bin Zayed Al Nahyan"
    assert items[0]["primary_subject_type"] == "person"
    assert items[0]["badge_subject"] == "United Arab Emirates"
    assert items[0]["badge_subject_type"] == "country"
    assert items[0]["badge_subject_category"] == "country"


# ---------------------------------------------------------------------------
# build_classifier_input_items — input projection
# ---------------------------------------------------------------------------


def test_build_input_items_skips_items_without_primary_entity():
    items = [
        {"id": "a", "primary_entity": "MBZUAI", "headline": "h1", "section": "UAE"},
        {"id": "b", "primary_entity": None, "headline": "h2", "section": "UAE"},
        {"id": "c", "primary_entity": "", "headline": "h3", "section": "UAE"},
        {"id": "d", "primary_entity": "Rapidus", "headline": "h4", "section": "Tech"},
    ]
    input_items = build_classifier_input_items(items)
    assert len(input_items) == 2
    assert [i["id"] for i in input_items] == ["a", "d"]


def test_build_input_items_projects_only_needed_fields():
    items = [
        {
            "id": "a",
            "primary_entity": "MBZUAI",
            "headline": "h",
            "section": "UAE",
            "analysis": "This should NOT be in the classifier input",
            "key_bullets": ["x", "y"],
            "raw_content": {"big": "blob"},
        }
    ]
    projected = build_classifier_input_items(items)[0]
    assert set(projected.keys()) == {"id", "primary_entity", "headline", "section"}


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (
            {
                "primary_entity": "CENTCOM",
                "headline": "US blockade of Iranian ports holds through first 24 hours",
                "section": "International Politics & Policy",
                "entities": ["CENTCOM", "Iran"],
            },
            "defense",
        ),
        (
            {
                "primary_entity": "H.H. Sheikh Khaled bin Mohamed bin Zayed Al Nahyan",
                "headline": "President meets delegation in Abu Dhabi",
                "section": "UAE",
            },
            "government",
        ),
        (
            {
                "primary_entity": "Khalifa University",
                "headline": "Khalifa University opens new AI center",
                "section": "Regional Research & Academic Events",
                "source_domain": "ku.ac.ae",
            },
            "university",
        ),
        (
            {
                "primary_entity": "Mubadala Capital",
                "headline": "Mubadala Capital joins strategic funding round",
                "section": "International Business & Technology",
            },
            "finance",
        ),
        (
            {
                "primary_entity": "Iran",
                "headline": "Iran says talks will continue next week",
                "section": "International Politics & Policy",
            },
            "country",
        ),
        (
            {
                "headline": "Anthropic launches new reasoning model",
                "section": "Model Releases & Technical Developments",
                "is_model_release": True,
            },
            "model",
        ),
    ],
)
def test_infer_entity_category(item, expected):
    assert infer_entity_category(item) == expected


def test_infer_entity_category_returns_none_without_enough_signal():
    assert infer_entity_category({"primary_entity": "Y"}) is None
