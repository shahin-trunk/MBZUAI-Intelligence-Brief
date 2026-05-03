"""URL-based publication date extraction.

Fetches source_url HTML (in parallel) and parses the publication date from
standard meta tags and JSON-LD structured data. Attaches the verified date
as ``_verified_date`` (YYYY-MM-DD string) on each item dict.

This is a best-effort enrichment step:
  - Items whose URL is unreachable, paywalled, or missing date metadata
    simply don't get a ``_verified_date`` (no items are dropped here).
  - The downstream ``filter_items_by_date()`` uses ``_verified_date`` as
    the strongest signal for staleness when available.

Runs in ~2-5 seconds for ~50 items (parallel fetches, 8s timeout per URL).
"""

import asyncio
import json
import logging
import re
from datetime import datetime, date
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Timeout per URL fetch (seconds). Short — we don't want to stall the pipeline.
FETCH_TIMEOUT = 8.0

# Max concurrent fetches (polite to target servers + avoid local socket exhaustion)
MAX_CONCURRENT = 20

# How much HTML to read before stopping (bytes). Needs to cover <head> section
# including inline CSS/JS. 100KB is still tiny to process but catches JSON-LD
# on sites with heavy <head> content.
MAX_BYTES = 100_000

# Common date meta-tag patterns, ordered by reliability.
# Each is (attr_name, attr_value, content_is_date).
_META_PATTERNS = [
    # Open Graph / article
    ("property", "article:published_time"),
    ("property", "og:article:published_time"),
    # Dublin Core
    ("name", "dcterms.date"),
    ("name", "DC.date.issued"),
    ("name", "dc.date"),
    # Generic
    ("name", "publication_date"),
    ("name", "date"),
    ("name", "publish-date"),
    ("name", "sailthru.date"),
    ("itemprop", "datePublished"),
]

# Regex to extract content="..." from a <meta> tag string
_CONTENT_RE = re.compile(r'content\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

# Regex to find <meta ...> tags in raw HTML (lazy, non-greedy)
_META_TAG_RE = re.compile(r'<meta\s[^>]+>', re.IGNORECASE)

# JSON-LD datePublished extractor
_JSONLD_RE = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

# ISO 8601 date parser (handles YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, with/without TZ)
_ISO_DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def _parse_date_string(raw: str) -> Optional[date]:
    """Extract a date from a raw string (ISO 8601 variants)."""
    m = _ISO_DATE_RE.search(raw)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _extract_date_from_meta(html: str) -> Optional[date]:
    """Try standard <meta> tags for publication date."""
    # Lower-case for matching but keep original for content extraction
    html_lower = html.lower()

    for attr_name, attr_value in _META_PATTERNS:
        # Build a search pattern like: property="article:published_time"
        pattern = f'{attr_name}="{attr_value.lower()}"'
        alt_pattern = f"{attr_name}='{attr_value.lower()}'"
        pos = html_lower.find(pattern)
        if pos == -1:
            pos = html_lower.find(alt_pattern)
        if pos == -1:
            continue

        # Find the enclosing <meta> tag
        tag_start = html_lower.rfind('<meta', max(0, pos - 200), pos + 1)
        if tag_start == -1:
            continue
        tag_end = html_lower.find('>', tag_start)
        if tag_end == -1:
            continue

        # Extract content from original (not lowered) HTML
        tag_str = html[tag_start:tag_end + 1]
        content_match = _CONTENT_RE.search(tag_str)
        if content_match:
            d = _parse_date_string(content_match.group(1))
            if d:
                return d

    return None


def _extract_date_from_jsonld(html: str) -> Optional[date]:
    """Try JSON-LD structured data for datePublished."""
    for m in _JSONLD_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            continue

        # Handle both single objects and arrays
        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            # Direct datePublished
            for key in ("datePublished", "dateCreated", "uploadDate"):
                val = obj.get(key)
                if val:
                    d = _parse_date_string(str(val))
                    if d:
                        return d
            # Nested @graph array
            for graph_item in obj.get("@graph", []):
                if isinstance(graph_item, dict):
                    for key in ("datePublished", "dateCreated"):
                        val = graph_item.get(key)
                        if val:
                            d = _parse_date_string(str(val))
                            if d:
                                return d

    return None


def _extract_date_from_time_tag(html: str) -> Optional[date]:
    """Fallback: look for <time datetime="..."> tags."""
    pattern = re.compile(r'<time[^>]+datetime\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    for m in pattern.finditer(html):
        d = _parse_date_string(m.group(1))
        if d:
            return d
    return None


def extract_date_from_html(html: str) -> Optional[date]:
    """Extract publication date from HTML using multiple strategies.

    Priority: meta tags > JSON-LD > <time> tags.
    """
    d = _extract_date_from_meta(html)
    if d:
        return d

    d = _extract_date_from_jsonld(html)
    if d:
        return d

    d = _extract_date_from_time_tag(html)
    if d:
        return d

    return None


async def _fetch_and_extract(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
) -> tuple[str, Optional[date]]:
    """Fetch a URL and extract its publication date.

    Returns (url, date_or_None).
    """
    if not url or not url.startswith("http"):
        return url, None

    async with semaphore:
        try:
            resp = await client.get(
                url,
                follow_redirects=True,
                timeout=FETCH_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.debug(f"Date verify: {resp.status_code} for {url[:80]}")
                return url, None

            # Read only the first MAX_BYTES (covers <head> + JSON-LD)
            html = resp.text[:MAX_BYTES]
            d = extract_date_from_html(html)
            if d:
                logger.info(f"Date verify: {url[:80]} -> {d}")
            else:
                logger.info(f"Date verify: {url[:80]} -> no date found")
            return url, d

        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
            logger.info(f"Date verify fetch failed: {url[:80]} - {type(e).__name__}")
            return url, None
        except Exception as e:
            logger.info(f"Date verify unexpected error: {url[:80]} - {e}")
            return url, None


async def verify_dates(items: list[dict]) -> tuple[int, int]:
    """Fetch source_url for all items and attach _verified_date where found.

    Runs all fetches in parallel (bounded by MAX_CONCURRENT).

    Returns (num_verified, num_failed).
    """
    if not items:
        return 0, 0

    # Deduplicate URLs (many items may share the same source)
    url_to_indices: dict[str, list[int]] = {}
    for i, item in enumerate(items):
        url = (item.get("source_url") or "").strip()
        if url and url.startswith("http"):
            url_to_indices.setdefault(url, []).append(i)

    if not url_to_indices:
        return 0, 0

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(
        headers={
            # Real browser UA — many news sites serve stripped HTML to bot UAs,
            # omitting JSON-LD and meta tags that contain publication dates.
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        # Disable HTTP/2 to avoid compatibility issues with some servers
        http2=False,
    ) as client:
        tasks = [
            _fetch_and_extract(client, semaphore, url)
            for url in url_to_indices.keys()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    num_verified = 0
    num_failed = 0

    for result in results:
        if isinstance(result, Exception):
            num_failed += 1
            continue

        url, extracted_date = result
        if extracted_date:
            # Attach to all items with this URL
            for idx in url_to_indices.get(url, []):
                items[idx]["_verified_date"] = extracted_date.isoformat()
            num_verified += 1
        else:
            num_failed += 1

    return num_verified, num_failed
