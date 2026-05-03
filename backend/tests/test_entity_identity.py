"""Tests for entity_identity sanitization helpers."""

from __future__ import annotations

import pytest

from pipeline.entity_identity import _is_noisy_entity_label, resolve_story_identity


NOISY_LABELS = [
    "ASML and TSMC",
    "US-Iran",
    "MENA Startup",
    "GCC Market",
    "Apple & Meta",
    "supply TEST",
    "Saudi-Israel",
    "US, Iran",
    "APAC Funding",
]

CLEAN_LABELS = [
    "ASML",
    "TSMC",
    "Abu Dhabi",
    "Khalifa University",
    "Al-Maktoum",
    "G42",
    "OpenAI",
    "United Arab Emirates",
    "Mohamed bin Zayed",
    "Saudi Arabia",
    "Mohammed bin Rashid Al Maktoum",
]


@pytest.mark.parametrize("label", NOISY_LABELS)
def test_noisy_entity_labels_detected(label: str) -> None:
    assert _is_noisy_entity_label(label), f"Expected noisy: {label!r}"


@pytest.mark.parametrize("label", CLEAN_LABELS)
def test_clean_entity_labels_pass(label: str) -> None:
    assert not _is_noisy_entity_label(label), f"Expected clean: {label!r}"


def test_noisy_label_nulls_badge_subject() -> None:
    """When primary_entity is noisy, badge_subject and primary_subject null out."""
    item = {
        "primary_entity": "ASML and TSMC",
        "headline": "ASML and TSMC raise forecasts",
        "section": "International Business & Technology",
        "source_name": "Bloomberg",
        "source_domain": "bloomberg.com",
    }
    identity = resolve_story_identity(item)
    assert identity["primary_subject"] is None
    assert identity["badge_subject"] is None


def test_clean_label_preserved() -> None:
    item = {
        "primary_entity": "ASML",
        "headline": "ASML raises forecast",
        "section": "International Business & Technology",
        "source_name": "Bloomberg",
        "source_domain": "bloomberg.com",
    }
    identity = resolve_story_identity(item)
    assert identity["primary_subject"] == "ASML"
    assert identity["badge_subject"] == "ASML"


def test_model_release_developer_survives_noisy_entity() -> None:
    """If primary_entity is noisy but model_release_data has a clean developer,
    the developer is used."""
    item = {
        "primary_entity": "OpenAI and Anthropic",
        "is_model_release": True,
        "model_release_data": {
            "developer": "OpenAI",
            "model_name": "GPT-5",
        },
        "headline": "GPT-5 released",
        "section": "Model Releases & Technical Developments",
    }
    identity = resolve_story_identity(item)
    assert identity["badge_subject"] == "OpenAI"


def test_empty_label() -> None:
    assert not _is_noisy_entity_label("")
    assert not _is_noisy_entity_label(None)


def test_noisy_entity_with_country_in_headline_promotes_to_country() -> None:
    """When primary_entity is sanitized but headline unambiguously mentions
    a country, badge_subject should be promoted to that country so the
    frontend can render a flag instead of a generic icon."""
    item = {
        "primary_entity": "US-Iran",
        "headline": "Trump signals Iran deal close as markets hit new records",
        "section": "International Politics & Policy",
        "source_name": "Bloomberg",
        "source_domain": "bloomberg.com",
    }
    identity = resolve_story_identity(item)
    assert identity["badge_subject"] == "Iran"
    assert identity["badge_subject_category"] == "country"


def test_noisy_entity_without_country_leaves_badge_null() -> None:
    """When primary_entity is sanitized and no single country is named in
    the headline, badge_subject stays None so the frontend falls through
    to the section-themed icon."""
    item = {
        "primary_entity": "MENA Startup",
        "headline": "MENA startup funding fell 37% year-on-year in Q1 to a five-year low",
        "section": "International Business & Technology",
        "source_name": "Wamda",
        "source_domain": "wamda.com",
    }
    identity = resolve_story_identity(item)
    assert identity["badge_subject"] is None
    assert identity["badge_subject_category"] is None
