"""Post-gatekeeper web search date verification.

For newsletter-origin items that have no ``_verified_date`` (because they
lack a source URL for ``date_verify`` to fetch), searches the headline via
Serper (Google) and extracts publication dates from result URL paths.

Items whose median search-result date is older than the cutoff are dropped.
This is a best-effort, fail-open stage: search failures -> item is kept.

Previously backed by DuckDuckGo's HTML endpoint, which started returning
HTTP 202 (rate-limit / anti-scraping) for 80%+ of requests, silently
bypassing the filter. Serper provides a stable JSON API at our volume.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 8.0

SERPER_URL = "https://google.serper.dev/search"
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
# Serper rate-limits bursty traffic; with the pre-Gatekeeper placement we
# search ~200 items per run, so keep the fan-out modest and let the retry
# logic below absorb any 429s that slip through.
MAX_CONCURRENT_SEARCHES = 3
# Exponential backoff schedule for 429s and transient network errors.
_RETRY_DELAYS = [1.0, 2.0, 4.0]

# Date patterns found in news article URLs (fallback when Serper omits `date`)
_URL_DATE_PATTERNS = [
    re.compile(r"/(\d{4})/(\d{2})/(\d{2})/"),    # /2026/03/11/
    re.compile(r"/(\d{4})-(\d{2})-(\d{2})/"),     # /2026-03-11/
    re.compile(r"/(\d{4})-(\d{2})-(\d{2})[-_]"),   # /2026-03-11-article
    re.compile(r"[/_](\d{4})(\d{2})(\d{2})[/_]"),  # /20260311/
]

# Serper's relative-date field: "17 hours ago", "3 days ago", "2 weeks ago",
# "1 month ago", "1 year ago". Used when no absolute date is present.
_RELATIVE_DATE_RE = re.compile(
    r"^(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago$",
    re.IGNORECASE,
)


def _extract_dates_from_url(url: str) -> list[date]:
    """Extract publication dates from URL path patterns."""
    dates = []
    for pattern in _URL_DATE_PATTERNS:
        for m in pattern.finditer(url):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if 2025 <= d.year <= 2027:
                    dates.append(d)
            except ValueError:
                pass
    return dates


def _parse_serper_date(value: str, today: date) -> Optional[date]:
    """Parse a Serper organic `date` string into an absolute date.

    Handles two formats Serper emits:
      - Absolute: ``"Mar 11, 2026"``, ``"April 3, 2026"``, ``"2026-04-17"``
      - Relative: ``"17 hours ago"``, ``"3 days ago"``, ``"2 weeks ago"``

    Returns ``None`` for anything we don't recognize so the caller can
    fall back to URL-path extraction.
    """
    if not value or not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None

    m = _RELATIVE_DATE_RE.match(trimmed)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        # Relative offsets from today's GST date. Approximate months/years
        # as 30/365 days — good enough for a "stale vs fresh" gate with a
        # 48-hour buffer downstream.
        days = {
            "minute": 0,
            "hour": 1 if amount >= 24 else 0,
            "day": amount,
            "week": amount * 7,
            "month": amount * 30,
            "year": amount * 365,
        }[unit]
        return today - timedelta(days=days)

    # Try absolute parsers.
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            parsed = datetime.strptime(trimmed, fmt).date()
            if 2024 <= parsed.year <= 2027:
                return parsed
        except ValueError:
            continue
    return None


async def _search_headline(
    client: httpx.AsyncClient,
    headline: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, Optional[date], list[date], Optional[int]]:
    """Search a headline via Serper and return the median URL-path date.

    Returns ``(headline, median_date_or_None, all_dates, http_status)``.
    ``http_status`` is the Serper response code, or ``None`` if the call
    never completed (network error). The caller uses it to tell
    "filter ran and found no evidence to drop" from "filter never ran" —
    the latter warrants a batch-level WARNING so silent bypass (the DDG
    202 regression) can't recur undetected.
    """
    async with semaphore:
        resp = None
        last_exc: Optional[Exception] = None
        for attempt, delay in enumerate([0.0, *_RETRY_DELAYS]):
            if delay:
                await asyncio.sleep(delay)
            try:
                resp = await client.post(
                    SERPER_URL,
                    json={"q": headline, "num": 10},
                    headers={"X-API-KEY": SERPER_API_KEY},
                    timeout=FETCH_TIMEOUT,
                )
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
                last_exc = e
                if attempt < len(_RETRY_DELAYS):
                    continue
                logger.warning(
                    "Web search verify: Serper fetch failed for %s after %d "
                    "attempts - %s",
                    headline[:60], attempt + 1, type(e).__name__,
                )
                return headline, None, [], None

            if resp.status_code == 429:
                # Rate-limited. Respect Retry-After if present; otherwise
                # fall through to the next delay in _RETRY_DELAYS.
                if attempt < len(_RETRY_DELAYS):
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            hint = float(retry_after)
                            await asyncio.sleep(min(hint, 8.0))
                        except ValueError:
                            pass
                    continue
                logger.warning(
                    "Web search verify: Serper 429 for: %s (exhausted %d retries)",
                    headline[:60], attempt,
                )
                return headline, None, [], 429

            if resp.status_code != 200:
                logger.warning(
                    "Web search verify: Serper %d for: %s",
                    resp.status_code, headline[:60],
                )
                return headline, None, [], resp.status_code

            # 200 OK — break out and parse below.
            break
        else:
            # Loop exhausted without a 200 or explicit return. Shouldn't
            # happen but guard anyway.
            if last_exc:
                return headline, None, [], None
            return headline, None, [], resp.status_code if resp else None

        try:
            data = resp.json()
            organic = data.get("organic", []) if isinstance(data, dict) else []
            today = datetime.now().date()

            # Prefer Serper's explicit `date` field per organic result —
            # URL-path regex extraction misses most modern news URLs. Fall
            # back to URL-path dates when Serper doesn't provide one.
            all_dates: list[date] = []
            for r in organic[:8]:
                if not isinstance(r, dict):
                    continue
                parsed = _parse_serper_date(r.get("date", ""), today)
                if parsed is None:
                    link = r.get("link", "")
                    if isinstance(link, str) and link:
                        url_dates = _extract_dates_from_url(link)
                        if url_dates:
                            parsed = url_dates[0]
                if parsed is not None:
                    all_dates.append(parsed)

            if all_dates:
                # Median: robust against a single old/new outlier article.
                sorted_dates = sorted(all_dates)
                median = sorted_dates[len(sorted_dates) // 2]
                logger.info(
                    "Web search verify: %s -> median %s (dates: %s, %d results)",
                    headline[:60], median,
                    [d.isoformat() for d in sorted_dates],
                    len(organic),
                )
                return headline, median, sorted_dates, resp.status_code

            logger.info(
                "Web search verify: %s -> no dates in %d results",
                headline[:60], len(organic),
            )
            return headline, None, [], resp.status_code

        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
            logger.warning(
                "Web search verify: Serper fetch failed for %s - %s",
                headline[:60], type(e).__name__,
            )
            return headline, None, [], None
        except Exception as e:
            logger.warning(
                "Web search verify: Serper error for %s - %s", headline[:60], e,
            )
            return headline, None, [], None


async def verify_dates_via_search(
    items: list[dict],
    cutoff: datetime,
) -> tuple[list[dict], list[dict]]:
    """Web-search newsletter items without verified dates to catch stale news.

    Searches newsletter-origin items that have no ``_verified_date``.
    Items whose median search-result date is before ``cutoff - 48h`` are
    dropped (48h buffer avoids edge cases with late-day publications).

    Returns (kept_items, dropped_items).
    """
    from pipeline.orchestrator import is_newsletter_origin

    if not items:
        return items, []

    cutoff_date = (cutoff - timedelta(hours=48)).date()

    # Identify items needing search: newsletter-origin without verified date.
    needs_search: dict[int, str] = {}
    for i, item in enumerate(items):
        if item.get("_verified_date"):
            continue
        if not is_newsletter_origin(item):
            continue
        headline = (item.get("headline") or "").strip()
        if headline:
            needs_search[i] = headline

    if not needs_search:
        logger.info("Web search verify: no items need searching")
        return items, []

    if not SERPER_API_KEY:
        logger.warning(
            "Web search verify: SERPER_API_KEY not set — %d newsletter items "
            "passing through unverified (filter effectively disabled)",
            len(needs_search),
        )
        return items, []

    logger.info(
        "Web search verify: searching %d newsletter items via Serper",
        len(needs_search),
    )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
    async with httpx.AsyncClient(http2=False) as client:
        tasks = [
            _search_headline(client, headline, semaphore)
            for headline in needs_search.values()
        ]
        results = await asyncio.gather(*tasks)

    headline_results: dict[str, tuple[Optional[date], list[date]]] = {}
    unverified = 0  # searches that did not produce a usable response
    non_200_count = 0
    for headline, median, all_dates, status in results:
        headline_results[headline] = (median, all_dates)
        if status != 200:
            unverified += 1
            if status is not None:
                non_200_count += 1

    if unverified:
        logger.warning(
            "Web search verify: %d of %d searches did not complete "
            "successfully (Serper non-200: %d, transport errors: %d) — "
            "those items are passing through unchecked",
            unverified, len(needs_search),
            non_200_count, unverified - non_200_count,
        )

    # Split into kept and dropped
    kept = []
    dropped = []
    for i, item in enumerate(items):
        if i not in needs_search:
            kept.append(item)
            continue

        headline = needs_search[i]
        median, all_dates = headline_results.get(headline, (None, []))

        if median and median < cutoff_date:
            logger.info(
                "Web search verify: DROPPING (median=%s < cutoff=%s): %s",
                median, cutoff_date, headline[:80],
            )
            dropped.append({
                "headline": headline,
                "source": item.get("source", ""),
                "claimed_date": item.get("date", ""),
                "web_search_median_date": median.isoformat(),
                "web_search_all_dates": [d.isoformat() for d in all_dates],
                "cutoff_date": cutoff_date.isoformat(),
                "drop_reason": "web_search_date_before_cutoff",
            })
        else:
            kept.append(item)

    return kept, dropped
