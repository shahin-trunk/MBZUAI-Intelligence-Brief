"""Shared fixtures and helpers for exhibit/model-release tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

OUTPUT_DIR = BACKEND_DIR / "output"


# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

def _has_api_keys() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _has_serper_key() -> bool:
    return bool(os.getenv("SERPER_API_KEY"))


def _has_cached_file(filename: str) -> bool:
    return (OUTPUT_DIR / filename).exists()


skip_no_anthropic = pytest.mark.skipif(
    not _has_api_keys(),
    reason="ANTHROPIC_API_KEY not set",
)

skip_no_serper = pytest.mark.skipif(
    not _has_serper_key(),
    reason="SERPER_API_KEY not set",
)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_json_file(filename: str) -> dict:
    path = OUTPUT_DIR / filename
    if not path.exists():
        pytest.skip(f"Cached file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_gatekeeper_items(date: str) -> list[dict]:
    data = load_json_file(f"gatekeeper_output_{date}.json")
    return data.get("selected", [])


def load_brief(date: str) -> dict:
    return load_json_file(f"brief_{date}.json")


def load_brief_items(date: str) -> list[dict]:
    brief = load_brief(date)
    return brief.get("items", [])


def find_model_release_items(items: list[dict]) -> list[dict]:
    return [
        item for item in items
        if "model release" in item.get("brief_section", "").lower()
        or item.get("is_model_release") is True
    ]


def all_cached_brief_dates() -> list[str]:
    """Return sorted list of dates for which brief_*.json exists."""
    dates = []
    for path in OUTPUT_DIR.glob("brief_*.json"):
        stem = path.stem  # brief_2026-04-09
        date = stem.replace("brief_", "")
        if date and len(date) == 10:
            dates.append(date)
    return sorted(dates)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def anthropic_client():
    """Create an async Anthropic client (requires ANTHROPIC_API_KEY)."""
    import anthropic
    return anthropic.AsyncAnthropic()
