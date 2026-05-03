"""Regression tests for the hybrid Serper + Claude regional research scout.

Locks the 2026-04-21 architecture change: Serper pre-fetch for discipline
coverage (biotech, robotics, etc.) runs before Claude's evaluation step so
long-tail institutional events (e.g. AURAK Biotech) surface even though
Claude's native `web_search_20250305` tool's Brave index misses them.

These tests mock Serper responses and exercise the pure Python helpers —
no live HTTP, no Anthropic calls. A separate `pytest.mark` will gate
ANTHROPIC_API_KEY + SERPER_API_KEY integration tests for optional live
verification.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.scouts import regional_research_scout as rrs  # noqa: E402
from pipeline.collector import CollectedArticle  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serper_response(organic: list[dict], status: int = 200) -> MagicMock:
    """Build a fake httpx.Response matching the Serper /search contract."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    if status == 200:
        resp.json.return_value = {"organic": organic}
        resp.text = ""
    else:
        resp.json.return_value = {"message": "Not enough credits", "statusCode": status}
        resp.text = '{"message":"Not enough credits","statusCode":400}'
    resp.headers = {}
    return resp


def _mock_async_client(responses: list[MagicMock]) -> AsyncMock:
    """Fake httpx.AsyncClient whose .post() returns successive mock responses."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=responses)
    return client


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


def test_serper_enabled_default(monkeypatch):
    monkeypatch.delenv("REGIONAL_SCOUT_SERPER_ENABLED", raising=False)
    assert rrs._is_serper_enabled() is True


def test_serper_disabled_via_env(monkeypatch):
    for val in ("false", "FALSE", "0", "no", "No"):
        monkeypatch.setenv("REGIONAL_SCOUT_SERPER_ENABLED", val)
        assert rrs._is_serper_enabled() is False, f"should be disabled for {val!r}"


def test_serper_enabled_for_other_values(monkeypatch):
    for val in ("true", "1", "yes", "on"):
        monkeypatch.setenv("REGIONAL_SCOUT_SERPER_ENABLED", val)
        assert rrs._is_serper_enabled() is True, f"should be enabled for {val!r}"


# ---------------------------------------------------------------------------
# _serper_discipline_sweep — per-query helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spam_domains_filtered_out():
    """A domain on the spam list must be dropped from the results."""
    organic = [
        {"title": "Real AURAK news", "link": "https://aurak.ac.ae/news/biotech",
         "snippet": "s", "date": "1 day ago"},
        {"title": "Spam aggregator #1", "link": "https://conferenceindex.org/uae/biotech",
         "snippet": "s", "date": "1 day ago"},
        {"title": "Spam aggregator #2", "link": "https://magnusconferences.com/uae",
         "snippet": "s", "date": "1 day ago"},
        {"title": "Khalifa University post", "link": "https://ku.ac.ae/news",
         "snippet": "s", "date": "2 days ago"},
    ]
    client = _mock_async_client([_serper_response(organic)])
    hits, err = await rrs._serper_discipline_sweep(client, "biotech", "q", "fake-key")
    assert err == ""
    domains = {h["domain"] for h in hits}
    assert "aurak.ac.ae" in domains
    assert "ku.ac.ae" in domains
    assert "conferenceindex.org" not in domains
    assert "magnusconferences.com" not in domains


@pytest.mark.asyncio
async def test_per_discipline_top_n_cap():
    """Helper caps results at _SERPER_PER_DISCIPLINE_TOP_N, excluding spam."""
    organic = [
        {"title": f"Hit {i}", "link": f"https://real-source-{i}.ac.ae/n/{i}",
         "snippet": "", "date": ""}
        for i in range(15)
    ]
    client = _mock_async_client([_serper_response(organic)])
    hits, _ = await rrs._serper_discipline_sweep(client, "biotech", "q", "fake-key")
    assert len(hits) == rrs._SERPER_PER_DISCIPLINE_TOP_N


@pytest.mark.asyncio
async def test_credits_exhausted_returns_specific_error():
    """400 with 'Not enough credits' body is detected and surfaced as error."""
    client = _mock_async_client([_serper_response([], status=400)])
    hits, err = await rrs._serper_discipline_sweep(client, "biotech", "q", "fake-key")
    assert hits == []
    assert "credits exhausted" in err.lower()


@pytest.mark.asyncio
async def test_network_failure_is_fail_open():
    """Network errors propagate as empty result + error string, not exceptions."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    hits, err = await rrs._serper_discipline_sweep(client, "biotech", "q", "fake-key")
    assert hits == []
    assert "ConnectError" in err


@pytest.mark.asyncio
async def test_429_rate_limit_retries_then_gives_up():
    """Persistent 429s exhaust retries and return a rate-limit error."""
    # 1 initial attempt + 3 retries = 4 total responses, all 429
    responses = [_serper_response([], status=429) for _ in range(4)]
    client = _mock_async_client(responses)
    hits, err = await rrs._serper_discipline_sweep(client, "biotech", "q", "fake-key")
    assert hits == []
    assert "429" in err


# ---------------------------------------------------------------------------
# _run_discipline_sweeps — fan-out + dedup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feature_flag_off_skips_phase(monkeypatch):
    """When the flag is off, no Serper calls happen."""
    monkeypatch.setenv("REGIONAL_SCOUT_SERPER_ENABLED", "false")
    monkeypatch.setenv("SERPER_API_KEY", "fake-key")
    prefetched, stats = await rrs._run_discipline_sweeps([], 2026)
    assert prefetched == []
    assert stats["enabled"] is False
    assert stats["queries_run"] == 0


@pytest.mark.asyncio
async def test_missing_api_key_skips_phase(monkeypatch):
    monkeypatch.setenv("REGIONAL_SCOUT_SERPER_ENABLED", "true")
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    prefetched, stats = await rrs._run_discipline_sweeps([], 2026)
    assert prefetched == []
    assert "SERPER_API_KEY not set" in stats["errors"][0]


@pytest.mark.asyncio
async def test_cross_discipline_dedup_by_url(monkeypatch):
    """Same URL surfacing under multiple disciplines is kept once."""
    monkeypatch.setenv("REGIONAL_SCOUT_SERPER_ENABLED", "true")
    monkeypatch.setenv("SERPER_API_KEY", "fake-key")
    shared_url = "https://ku.ac.ae/event"
    # Mock the module-level httpx.AsyncClient to return the same hit
    # across all 6 discipline queries
    async def fake_sweep(client, discipline, query, api_key):
        return [{
            "discipline": discipline, "title": "Shared KU event",
            "url": shared_url, "snippet": "s", "date": "1 day ago",
            "source_name": "Khalifa University", "domain": "ku.ac.ae",
        }], ""
    monkeypatch.setattr(rrs, "_serper_discipline_sweep", fake_sweep)
    prefetched, stats = await rrs._run_discipline_sweeps([], 2026)
    assert len(prefetched) == 1  # deduped across 6 disciplines
    assert stats["after_cross_discipline_dedup"] == 1


@pytest.mark.asyncio
async def test_existing_headline_dedup_fuzzy(monkeypatch):
    """Serper hit whose title fuzzy-matches an existing headline is dropped.

    Near-duplicate framing: the scout title and the existing-headline
    differ by a single word — fuzzy ratio > 0.85, so dedup should fire.
    Exact-match duplicates (same URL across collectors) hit earlier URL-
    dedup stages, so this test specifically covers the fuzzy-title path.
    """
    monkeypatch.setenv("REGIONAL_SCOUT_SERPER_ENABLED", "true")
    monkeypatch.setenv("SERPER_API_KEY", "fake-key")

    async def fake_sweep(client, discipline, query, api_key):
        return [{
            "discipline": discipline,
            "title": "AURAK hosts inaugural Biotechnology Conference highlighting "
                     "intersection between biosciences and industry",
            "url": f"https://example.com/{discipline}",
            "snippet": "s", "date": "1 day ago",
            "source_name": "Example", "domain": "example.com",
        }], ""
    monkeypatch.setattr(rrs, "_serper_discipline_sweep", fake_sweep)

    # Existing headline is nearly identical but routed via a different source
    # (capitalisation variation + wording drift). Fuzzy ratio > 0.85.
    existing = [
        "AURAK Hosts Inaugural Biotechnology Conference Highlighting "
        "Intersection Between Biosciences and Industry"
    ]
    prefetched, stats = await rrs._run_discipline_sweeps(existing, 2026)
    assert prefetched == []
    assert stats["after_headline_dedup"] == 0


@pytest.mark.asyncio
async def test_per_discipline_error_does_not_kill_others(monkeypatch):
    """One discipline erroring leaves the rest intact."""
    monkeypatch.setenv("REGIONAL_SCOUT_SERPER_ENABLED", "true")
    monkeypatch.setenv("SERPER_API_KEY", "fake-key")

    call_count = {"n": 0}
    async def fake_sweep(client, discipline, query, api_key):
        call_count["n"] += 1
        if discipline == "quantum":
            return [], "quantum: HTTP 500"
        return [{
            "discipline": discipline,
            "title": f"{discipline} result",
            "url": f"https://example.com/{discipline}",
            "snippet": "", "date": "",
            "source_name": "Example", "domain": "example.com",
        }], ""
    monkeypatch.setattr(rrs, "_serper_discipline_sweep", fake_sweep)

    prefetched, stats = await rrs._run_discipline_sweeps([], 2026)
    disciplines_returned = {p["discipline"] for p in prefetched}
    assert "quantum" not in disciplines_returned
    assert len(prefetched) == 5  # 6 disciplines - 1 failed
    assert any("quantum" in e for e in stats["errors"])


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def test_normalize_serper_hit_produces_collected_article():
    hit = {
        "discipline": "biotech",
        "title": "AURAK Hosts Inaugural Biotechnology Conference",
        "url": "https://aurak.ac.ae/news/aurak-biotech",
        "snippet": "Virtual event highlights cutting-edge innovations.",
        "date": "2 days ago",
        "source_name": "AURAK",
        "domain": "aurak.ac.ae",
    }
    article = rrs._normalize_serper_hit_to_collected_article(hit)
    assert isinstance(article, CollectedArticle)
    assert article.title == "AURAK Hosts Inaugural Biotechnology Conference"
    assert article.url == "https://aurak.ac.ae/news/aurak-biotech"
    assert article.source_name == "AURAK"
    assert article.collected_via == "serper_discipline_sweep"
    assert article.scout_mapping == ["regional"]


# ---------------------------------------------------------------------------
# Prompt injection formatting
# ---------------------------------------------------------------------------


def test_format_prefetched_empty_gives_explicit_note():
    out = rrs._format_prefetched_candidates([])
    assert "No discipline pre-fetches" in out


def test_format_prefetched_renders_fields():
    items = [{
        "discipline": "biotech",
        "title": "AURAK Biotech Conf",
        "url": "https://aurak.ac.ae/news",
        "snippet": "Cutting-edge innovations in biotechnology.",
        "date": "2 days ago",
        "source_name": "AURAK",
        "domain": "aurak.ac.ae",
    }]
    out = rrs._format_prefetched_candidates(items)
    assert "[biotech]" in out
    assert "AURAK Biotech Conf" in out
    assert "https://aurak.ac.ae/news" in out
    assert "2 days ago" in out
    assert "Cutting-edge innovations" in out


def test_build_prompt_accepts_prefetched_param(monkeypatch):
    """_build_prompt should accept prefetched_candidates without crashing.

    Supabase/Config side effects aside, we just verify the signature and
    that the prefetched block shows up in the rendered prompt when passed.
    """
    # Stub out the costly config helpers that load_prompt chain depends on
    # via _build_prompt's template replacements.
    import config as _config
    monkeypatch.setattr(_config, "get_today_date", lambda: "2026-04-21")
    import datetime
    monkeypatch.setattr(_config, "get_lookback_cutoff_date",
                        lambda: datetime.datetime(2026, 4, 20, 6, 0))
    prefetched = [{
        "discipline": "biotech",
        "title": "AURAK Biotech Conf",
        "url": "https://aurak.ac.ae/news",
        "snippet": "x", "date": "2 days ago",
        "source_name": "AURAK", "domain": "aurak.ac.ae",
    }]
    rendered = rrs._build_prompt(
        entities=[],
        existing_headlines=[],
        today="2026-04-21",
        prefetched_candidates=prefetched,
    )
    assert "AURAK Biotech Conf" in rendered
    assert "[biotech]" in rendered


def test_build_prompt_backward_compatible_without_prefetched(monkeypatch):
    """Old call sites that don't pass prefetched_candidates still work."""
    import config as _config
    monkeypatch.setattr(_config, "get_today_date", lambda: "2026-04-21")
    import datetime
    monkeypatch.setattr(_config, "get_lookback_cutoff_date",
                        lambda: datetime.datetime(2026, 4, 20, 6, 0))
    rendered = rrs._build_prompt(
        entities=[],
        existing_headlines=[],
        today="2026-04-21",
    )
    assert "{prefetched_candidates}" not in rendered  # placeholder resolved
    assert "No discipline pre-fetches" in rendered
