"""Tests for the enricher's URL-fetch fallback chain.

Covers the Phase 1 additions:
- `fetch_wam_article` — per-article WAM JSON API fetcher.
- `_fetch_via_serper` — Serper /scrape fallback.
- `fetch_source_url` — routes WAM URLs to the WAM API first, then
  falls through trafilatura → Serper → Jina.

All HTTP calls are mocked (no network, no API keys needed).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.enricher import (  # noqa: E402
    _html_to_text,
    _parse_wam_slug,
    fetch_source_url,
    fetch_wam_article,
)


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://www.wam.ae/en/article/bzrg2hy-hamriyah-municipality-launches-model-community",
            ("bzrg2hy-hamriyah-municipality-launches-model-community", "en"),
        ),
        ("https://wam.ae/ar/article/abc123-some-slug", ("abc123-some-slug", "ar")),
        ("https://www.wam.ae/en/home/main", None),  # listing page, not article
        ("https://example.com/en/article/foo", None),  # wrong host
        ("", None),
        ("not a url", None),
    ],
)
def test_parse_wam_slug(url, expected):
    assert _parse_wam_slug(url) == expected


def test_html_to_text_strips_tags_and_unescapes():
    html = (
        "<p>DUBAI, 16th April, 2026 (WAM) &mdash; H.H. Sheikh Hamdan "
        "bin Mohammed bin Rashid Al Maktoum.</p>\n"
        "<p>He &#x201C;reaffirmed&#x201D; the vision.</p>"
    )
    out = _html_to_text(html)
    assert "<p>" not in out
    assert "&mdash;" not in out
    assert "—" in out  # mdash → em dash
    assert "\u201c" in out or '"' in out.replace("\u201c", '"')  # curly quote unescaped
    assert "DUBAI, 16th April, 2026" in out
    assert "  " not in out  # whitespace collapsed


# ---------------------------------------------------------------------------
# fetch_wam_article — mocked WAM API responses
# ---------------------------------------------------------------------------


class _MockResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=None,  # type: ignore
                response=self,  # type: ignore
            )

    def json(self) -> dict:
        return self._payload


def _make_mock_client(response: _MockResponse):
    """Return an AsyncMock that mimics httpx.AsyncClient() context manager."""
    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=response)
    mock_client_instance.post = AsyncMock(return_value=response)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm, mock_client_instance


@pytest.mark.asyncio
async def test_fetch_wam_article_success():
    """Happy path: WAM API returns a body, we extract and normalise it."""
    payload = {
        "id": 123,
        "title": "Al Hamriyah Municipality launches model community farm",
        "articleDate": "2026-04-17T08:00:00+04:00",
        "body": (
            "<p>SHARJAH, 17th April, 2026 (WAM) -- Al Hamriyah Municipality "
            "launched a 20,000 m&sup2; farm.</p>"
            "<p>The project supports food security and sustainable living.</p>"
        ),
    }
    mock_cm, mock_client = _make_mock_client(_MockResponse(200, payload))

    with patch("pipeline.enricher.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_wam_article(
            "https://www.wam.ae/en/article/bzrg2hy-hamriyah-municipality-launches-model-community"
        )

    assert result is not None
    assert result["source_step"] == "wam_api"
    assert result["title"] == "Al Hamriyah Municipality launches model community farm"
    assert "SHARJAH" in result["extract"]
    assert "<p>" not in result["extract"]
    assert "&sup2;" not in result["extract"]  # HTML entity decoded

    # Confirm we called the right endpoint with the slug param
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert "GetArticleBySlug" in call_args[0][0]
    assert call_args[1]["params"]["slug"] == (
        "bzrg2hy-hamriyah-municipality-launches-model-community"
    )


@pytest.mark.asyncio
async def test_fetch_wam_article_empty_body_returns_none():
    payload = {"id": 1, "title": "x", "body": ""}
    mock_cm, _ = _make_mock_client(_MockResponse(200, payload))
    with patch("pipeline.enricher.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_wam_article(
            "https://www.wam.ae/en/article/some-slug"
        )
    assert result is None


@pytest.mark.asyncio
async def test_fetch_wam_article_non_wam_url_returns_none():
    """Non-WAM URLs short-circuit without a network call."""
    mock_cm, mock_client = _make_mock_client(_MockResponse(200, {}))
    with patch("pipeline.enricher.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_wam_article("https://example.com/article/foo")
    assert result is None
    mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_wam_article_http_error_returns_none():
    mock_cm, _ = _make_mock_client(_MockResponse(500, {}))
    with patch("pipeline.enricher.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_wam_article(
            "https://www.wam.ae/en/article/some-slug"
        )
    assert result is None


# ---------------------------------------------------------------------------
# fetch_source_url — routing order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_source_url_routes_wam_urls_to_wam_api_first(monkeypatch):
    """WAM URLs skip trafilatura/Serper/Jina entirely when the WAM API
    succeeds — the SPA shell defeats those, so this is mandatory routing."""
    mock_wam_result = {
        "url": "https://www.wam.ae/en/article/x",
        "title": "WAM article",
        "extract": "Full article body from WAM API.",
        "source_step": "wam_api",
    }
    wam_mock = AsyncMock(return_value=mock_wam_result)
    serper_mock = AsyncMock(return_value=None)
    jina_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("pipeline.enricher.fetch_wam_article", wam_mock)
    monkeypatch.setattr("pipeline.enricher._fetch_via_serper", serper_mock)
    monkeypatch.setattr("pipeline.enricher._fetch_via_jina", jina_mock)

    # Force trafilatura path to be skipped entirely — if WAM succeeds, we
    # return before trafilatura even runs.
    result = await fetch_source_url("https://www.wam.ae/en/article/x")
    assert result == mock_wam_result
    wam_mock.assert_awaited_once()
    serper_mock.assert_not_awaited()
    jina_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_source_url_falls_through_to_serper_when_trafilatura_fails(
    monkeypatch,
):
    """Non-WAM URL with trafilatura returning None should try Serper next,
    and skip Jina when Serper succeeds."""
    monkeypatch.setattr(
        "pipeline.enricher.fetch_wam_article",
        AsyncMock(return_value=None),
    )
    # Trafilatura returns nothing
    monkeypatch.setattr(
        "trafilatura.fetch_url",
        lambda url: "",  # signals no content
    )
    serper_result = {
        "url": "https://example.com/article",
        "title": "t",
        "extract": "serper content",
        "source_step": "serper_scrape",
    }
    serper_mock = AsyncMock(return_value=serper_result)
    jina_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("pipeline.enricher._fetch_via_serper", serper_mock)
    monkeypatch.setattr("pipeline.enricher._fetch_via_jina", jina_mock)

    result = await fetch_source_url("https://example.com/article")
    assert result == serper_result
    serper_mock.assert_awaited_once()
    jina_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_source_url_falls_through_to_jina_when_serper_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        "pipeline.enricher.fetch_wam_article",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr("trafilatura.fetch_url", lambda url: "")
    monkeypatch.setattr(
        "pipeline.enricher._fetch_via_serper",
        AsyncMock(return_value=None),
    )
    jina_result = {
        "url": "https://example.com/article",
        "title": "t",
        "extract": "jina content",
        "source_step": "jina_fallback",
    }
    jina_mock = AsyncMock(return_value=jina_result)
    monkeypatch.setattr("pipeline.enricher._fetch_via_jina", jina_mock)

    result = await fetch_source_url("https://example.com/article")
    assert result == jina_result
    jina_mock.assert_awaited_once()
