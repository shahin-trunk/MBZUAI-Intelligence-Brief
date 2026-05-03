"""Collection Layer — Deterministic news collection from institutional sources.

Deterministic HTTP scrapers and API calls for 9 sources:
UAE institutional sites, Gmail newsletters, MBZUAI events, and X API.

Each collector:
  - Is wrapped in try/except — one failing collector never breaks the others
  - Returns [] on failure
  - Logs: source name, status, article count, duration

Usage:
    cd backend && python3 pipeline/collector.py
"""

from __future__ import annotations

import asyncio
import base64
import email.utils
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure config is importable when run directly (project runs from backend/)
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import requests
from bs4 import BeautifulSoup

from config import OUTPUT_DIR, get_today_date, get_lookback_cutoff_date
from pipeline.json_utils import safe_parse_json
from pipeline.seen_cache import (
    CACHED_COLLECTORS,
    load_cache,
    save_cache,
    filter_new_items,
    update_cache_entry,
)

logger = logging.getLogger(__name__)
DUBAI_TZ = ZoneInfo("Asia/Dubai")

# HTTP request defaults
DEFAULT_TIMEOUT = 15  # seconds
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class CollectedArticle:
    title: str
    snippet: str                # First ~300 chars of body
    url: str
    source_name: str
    collected_via: str          # "scraper", "api", "wordpress_api"
    raw_text: str               # Body text (up to ~3000 chars)
    published_date: str         # YYYY-MM-DD or "" if unknown
    category: str               # Category if available, else ""
    published_at: str = ""      # ISO 8601 timestamp when available
    scout_mapping: list[str] = field(default_factory=list)


class CollectorSkipped(RuntimeError):
    """Raised when a collector is intentionally skipped, not failed."""


# ── Shared utilities ────────────────────────────────────────────────────────

def _parse_date(text: str) -> str:
    """Parse common date formats into YYYY-MM-DD.

    Handles:
      - "26 February 2026"   (day month year)
      - "February 26, 2026"  (month day, year)
      - "26 Feb 2026"        (abbreviated month)
      - "27 Feb, 2026"       (abbreviated month with comma)
    """
    text = text.strip().replace(",", "")
    for fmt in ("%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


# Regex for finding dates in free text (e.g. "26 February 2026" or "April 02 2026")
_DATE_RE = re.compile(
    r"\d{1,2}\s+\w+,?\s+\d{4}"    # day-first:  "26 February 2026"
    r"|"
    r"\w+\s+\d{1,2},?\s+\d{4}"    # month-first: "April 02 2026", "February 26, 2026"
)


def _get(url: str, timeout: int = DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
    """GET request with default headers and timeout."""
    headers = dict(DEFAULT_HEADERS)
    headers.update(kwargs.pop("headers", {}))
    return requests.get(url, headers=headers, timeout=timeout, **kwargs)


def _strip_html(html_str: str) -> str:
    """Strip HTML tags from a string (for WordPress rendered fields)."""
    if not html_str:
        return ""
    return unescape(re.sub(r"<[^>]+>", "", html_str)).strip()


def _ensure_aware_datetime(dt: datetime | None) -> datetime | None:
    """Attach UTC to naive datetimes so comparisons are stable."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_dubai_published_fields(dt: datetime | None) -> tuple[str, str]:
    """Convert a datetime to the published_date/published_at fields."""
    aware_dt = _ensure_aware_datetime(dt)
    if aware_dt is None:
        return "", ""
    dubai_dt = aware_dt.astimezone(DUBAI_TZ)
    return dubai_dt.strftime("%Y-%m-%d"), dubai_dt.isoformat()


def _is_before_cutoff(dt: datetime | None, cutoff: datetime) -> bool:
    """Return True when a datetime falls before the configured cutoff."""
    aware_dt = _ensure_aware_datetime(dt)
    return bool(aware_dt and aware_dt.astimezone(DUBAI_TZ) < cutoff)


# ── 1. WAM — Google News Sitemap + JSON API (highest priority, highest volume) ─

WAM_SITEMAP_URL = "https://www.wam.ae/en/sitemap/news.xml"
WAM_API_URL = "https://www.wam.ae/api/app/views/GetViewByUrl"


def _collect_wam_sitemap() -> list[CollectedArticle]:
    """Fetch WAM articles from the Google News sitemap.

    The sitemap at /en/sitemap/news.xml contains ~89 articles covering
    the last ~3 days, with full title, publication date, and URL.
    This is far more complete than the JSON API (which is capped at 20
    due to broken pagination).
    """
    resp = _get(WAM_SITEMAP_URL, headers={"Accept": "application/xml"})
    resp.raise_for_status()
    text = resp.text

    # Parse XML with regex (no lxml dependency needed)
    locs = re.findall(r"<loc>(.*?)</loc>", text)
    titles = re.findall(r"<news:title>(.*?)</news:title>", text)
    pub_dates = re.findall(r"<news:publication_date>(.*?)</news:publication_date>", text)

    if len(locs) != len(titles) or len(locs) != len(pub_dates):
        logger.warning(
            "WAM sitemap: array length mismatch — locs=%d, titles=%d, dates=%d. "
            "Truncating to shortest.",
            len(locs), len(titles), len(pub_dates),
        )

    articles: list[CollectedArticle] = []
    seen_urls: set[str] = set()
    cutoff = get_lookback_cutoff_date()

    for i, loc in enumerate(locs):
        title = titles[i] if i < len(titles) else ""
        date_str = pub_dates[i] if i < len(pub_dates) else ""

        if not title:
            continue

        # Normalise URL: sitemap uses /en/article/ID-slug, API uses /en/article/slug
        url = loc.strip()
        url_key = url.lower().rstrip("/")
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)

        # Parse ISO date
        published_date = ""
        published_at = ""
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                published_date, published_at = _to_dubai_published_fields(dt)
                if _is_before_cutoff(dt, cutoff):
                    continue  # Skip articles older than the lookback cutoff
            except ValueError:
                pass

        articles.append(CollectedArticle(
            title=unescape(title),
            snippet=unescape(title)[:300],
            url=url,
            source_name="WAM",
            collected_via="sitemap",
            raw_text=unescape(title),
            published_date=published_date,
            category="",
            published_at=published_at,
            scout_mapping=["uae"],
        ))

    return articles


def _collect_wam_api() -> list[CollectedArticle]:
    """Fetch WAM latest news via JSON API (fallback, returns ~20 articles).

    The API pagination is broken (returns same 20 articles on every page),
    so this only fetches page 0. Used as fallback if sitemap fails, and
    also merged to pick up subtitle/category data.
    """
    params: dict = {"url": "en/list/latest-news"}
    resp = _get(WAM_API_URL, headers={"Accept": "application/json"}, params=params)
    resp.raise_for_status()
    data = resp.json()

    sections = data.get("sections", [])
    if not sections:
        return []

    items = sections[0].get("articlesResult", {}).get("items", [])
    articles: list[CollectedArticle] = []
    cutoff = get_lookback_cutoff_date()

    for item in items:
        slug = item.get("slug", "")
        article_date_str = item.get("articleDate", "")
        published_date = ""
        published_at = ""
        if article_date_str:
            try:
                dt = datetime.fromisoformat(article_date_str)
                published_date, published_at = _to_dubai_published_fields(dt)
                if _is_before_cutoff(dt, cutoff):
                    continue
            except ValueError:
                pass

        url = f"https://www.wam.ae/en/article/{slug}" if slug else ""
        badge = item.get("badge", {})
        category = badge.get("text", "") if isinstance(badge, dict) else ""
        title = item.get("title", "")
        subtitle = item.get("subTitle", "")

        articles.append(CollectedArticle(
            title=title,
            snippet=subtitle[:300] if subtitle else title[:300],
            url=url,
            source_name="WAM",
            collected_via="api",
            raw_text=subtitle if subtitle else title,
            published_date=published_date,
            category=category,
            published_at=published_at,
            scout_mapping=["uae"],
        ))

    return articles


# WAM API listing pages that return articles with subTitles.
# The home page has ~70 articles across 11 sections; the category pages
# add ~30 each with significant non-overlap.  Together they cover most of
# what the sitemap carries, giving the pipeline real summaries instead of
# headline-only content.
_WAM_SUBTITLE_PAGES = [
    "en/home/main",
    "en/list/latest-news",
    "en/list/world",
    "en/list/business",
    "en/list/culture",
    "en/list/emirates-news",
    "en/list/international",
    "en/list/tolerance",
    "en/list/year-of-family",
]


def _normalize_wam_title(title: str) -> str:
    """Normalize a WAM title for fuzzy lookup.

    Collapses whitespace and strips anything that isn't a letter or digit
    (including diacritics like smart-quotes/ellipses, hyphens, punctuation),
    then lowercases. This lets us recover from minor formatting differences
    between the sitemap HTML and the API listing JSON (e.g., one carrying
    an ellipsis the other doesn't, or curly vs straight quotes).
    """
    return "".join(ch for ch in title.lower() if ch.isalnum())


def _find_wam_subtitle(title: str, lookup: dict[str, dict]) -> dict | None:
    """Resolve a sitemap title to a subtitle-lookup entry with fallbacks.

    Strategy:
      1. Exact lowercase match (original behaviour).
      2. Alphanumeric-only match — same title with punctuation/spacing
         differences (covers the WAM-headline-only false-drop case that
         caused 2 UAE items to be content-filtered on 2026-04-15).
      3. Prefix match on first 60 alphanumeric chars — handles titles
         where one source appends an ellipsis or trailing qualifier.

    Returns the matched entry dict or None.
    """
    if not title:
        return None
    key = title.strip().lower()
    match = lookup.get(key)
    if match:
        return match

    alnum_key = _normalize_wam_title(title)
    if not alnum_key:
        return None

    # Pass 2: alphanumeric-equal
    for candidate_key, entry in lookup.items():
        if _normalize_wam_title(candidate_key) == alnum_key:
            return entry

    # Pass 3: first-60-char prefix match (only when both are >= 60 chars
    # so we don't over-match tiny headlines).
    if len(alnum_key) < 60:
        return None
    prefix = alnum_key[:60]
    for candidate_key, entry in lookup.items():
        cand_alnum = _normalize_wam_title(candidate_key)
        if len(cand_alnum) >= 60 and cand_alnum[:60] == prefix:
            return entry

    return None


def _build_wam_subtitle_lookup() -> tuple[dict[str, dict], list[CollectedArticle]]:
    """Fetch multiple WAM API listing pages and build a title → subtitle lookup.

    Sitemap slugs and API slugs use different formats, so matching by slug
    is unreliable.  We match by normalised title instead.

    Also returns supplementary CollectedArticle objects for any articles
    found on the listing pages — these catch articles that haven't been
    indexed in the sitemap yet.
    """
    lookup: dict[str, dict] = {}
    supplementary: list[CollectedArticle] = []
    seen_slugs: set[str] = set()
    cutoff = get_lookback_cutoff_date()

    for page in _WAM_SUBTITLE_PAGES:
        try:
            resp = _get(WAM_API_URL, params={"url": page})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"WAM subtitle page '{page}' failed: {e}")
            continue
        for section in data.get("sections", []):
            for item in section.get("articlesResult", {}).get("items", []):
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                subtitle = (item.get("subTitle") or "").strip()
                badge = item.get("badge", {})
                category = badge.get("text", "") if isinstance(badge, dict) else ""

                # Build subtitle lookup (existing behaviour)
                if subtitle or category:
                    key = title.lower()
                    existing = lookup.get(key)
                    if not existing or len(subtitle) > len(existing.get("subtitle", "")):
                        lookup[key] = {"subtitle": subtitle, "category": category}

                # Also collect as supplementary article
                slug = (item.get("slug") or "").strip()
                if not slug or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)

                date_str = item.get("articleDate", "")
                published_date = ""
                published_at = ""
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str)
                        published_date, published_at = _to_dubai_published_fields(dt)
                        if _is_before_cutoff(dt, cutoff):
                            continue
                    except ValueError:
                        pass

                url = f"https://www.wam.ae/en/article/{slug}" if slug else ""
                body = subtitle or title
                supplementary.append(CollectedArticle(
                    title=title,
                    snippet=body[:300],
                    url=url,
                    source_name="WAM",
                    collected_via="api_listing",
                    raw_text=body[:3000],
                    published_date=published_date,
                    published_at=published_at,
                    category=category,
                    scout_mapping=["uae"],
                ))

    return lookup, supplementary


def collect_wam() -> list[CollectedArticle]:
    """Collect WAM articles from sitemap (primary) + API (enrichment).

    Strategy:
      1. Fetch sitemap (~100+ articles, 3 days) — gives us URL + title + date
      2. Fetch API page 0 (~20 articles) — gives us subtitle + category
      3. Fetch multiple API listing pages (home, world, business, culture —
         ~120 articles total) to build a title-keyed subtitle lookup
      4. Merge: enrich sitemap entries with subtitle/category data wherever
         available, so downstream stages get real summaries instead of
         headline-only content
    """
    # Primary: sitemap
    try:
        sitemap_articles = _collect_wam_sitemap()
        logger.info(f"WAM sitemap: {len(sitemap_articles)} articles")
    except Exception as e:
        logger.warning(f"WAM sitemap failed: {e}, falling back to API only")
        sitemap_articles = []

    # Secondary: API (for enrichment + fallback)
    try:
        api_articles = _collect_wam_api()
        logger.info(f"WAM API: {len(api_articles)} articles")
    except Exception as e:
        logger.warning(f"WAM API failed: {e}")
        api_articles = []

    # Tertiary: subtitle lookup from multiple API listing pages (title-keyed)
    # Also returns supplementary articles for items not yet in the sitemap
    subtitle_lookup: dict[str, dict] = {}
    listing_articles: list[CollectedArticle] = []
    try:
        subtitle_lookup, listing_articles = _build_wam_subtitle_lookup()
        logger.info(f"WAM subtitle lookup: {len(subtitle_lookup)} entries, {len(listing_articles)} listing articles")
    except Exception as e:
        logger.warning(f"WAM subtitle lookup failed: {e}")

    if not sitemap_articles:
        return api_articles

    # Build lookup from API articles by slug for enrichment
    # Sitemap URLs: /en/article/ID-slug  |  API URLs: /en/article/slug
    api_by_slug: dict[str, CollectedArticle] = {}
    for a in api_articles:
        # Extract slug from URL
        slug = a.url.rstrip("/").rsplit("/", 1)[-1] if a.url else ""
        if slug:
            api_by_slug[slug] = a

    # Enrich sitemap articles with API data where available
    enriched_count = 0
    for article in sitemap_articles:
        # Sitemap URL has ID prefix: /en/article/bz0nkf9-slug → extract "slug"
        url_slug = article.url.rstrip("/").rsplit("/", 1)[-1]
        # Remove the ID prefix (everything before first dash-word)
        # e.g. "bz0nkf9-uae-president-receives-phone-call" → "uae-president-receives-phone-call"
        parts = url_slug.split("-", 1)
        clean_slug = parts[1] if len(parts) > 1 else url_slug

        # Try latest-news API first by slug (most recent data)
        api_match = api_by_slug.get(clean_slug)
        if api_match:
            if api_match.raw_text and len(api_match.raw_text) > len(article.raw_text):
                article.raw_text = api_match.raw_text
                article.snippet = api_match.snippet
                enriched_count += 1
            if api_match.category:
                article.category = api_match.category

        # If still headline-only, try the title-keyed subtitle lookup
        # (with fuzzy fallbacks for formatting drift between sources).
        if article.raw_text == article.title or len(article.raw_text) < 50:
            sub_match = _find_wam_subtitle(article.title, subtitle_lookup)
            if sub_match and sub_match["subtitle"]:
                article.raw_text = sub_match["subtitle"][:3000]
                article.snippet = sub_match["subtitle"][:300]
                enriched_count += 1
            if sub_match and sub_match.get("category") and not article.category:
                article.category = sub_match["category"]

    logger.info(f"WAM enrichment: {enriched_count}/{len(sitemap_articles)} articles got subtitles")

    # Add any API / listing-page articles not already in sitemap
    sitemap_url_slugs = set()
    for a in sitemap_articles:
        slug = a.url.rstrip("/").rsplit("/", 1)[-1]
        parts = slug.split("-", 1)
        sitemap_url_slugs.add(parts[1] if len(parts) > 1 else slug)

    added_from_api = 0
    for a in api_articles + listing_articles:
        slug = a.url.rstrip("/").rsplit("/", 1)[-1] if a.url else ""
        if slug and slug not in sitemap_url_slugs:
            sitemap_url_slugs.add(slug)
            sitemap_articles.append(a)
            added_from_api += 1

    if added_from_api:
        logger.info(f"WAM: added {added_from_api} articles from API/listing pages not in sitemap")

    return sitemap_articles


# ── 2. ADMO — HTML Scraper (Abu Dhabi Media Office) ─────────────────────────

ADMO_BASE_URL = "https://www.mediaoffice.abudhabi"
ADMO_LISTING_URL = f"{ADMO_BASE_URL}/en/latest-news/"


def _admo_scrape_listing() -> list[dict]:
    """Fetch ADMO listing page and extract headline/url/category."""
    resp = _get(ADMO_LISTING_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items: list[dict] = []
    for link in soup.select("a[href^='/en/']"):
        headline_tag = link.find(["h3", "h2"])
        if not headline_tag:
            continue

        title = headline_tag.get_text(strip=True)
        href = link["href"]

        # Skip non-article links (sections, topic pages)
        if href.count("/") < 4:
            continue

        # Extract category from URL path: /en/transport/... → Transport
        parts = href.strip("/").split("/")
        category = parts[1].replace("-", " ").title() if len(parts) >= 3 else ""

        items.append({
            "title": title,
            "url": f"{ADMO_BASE_URL}{href}",
            "category": category,
        })

    # Deduplicate by URL
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            deduped.append(item)
    return deduped


def _admo_scrape_article(url: str) -> dict:
    """Fetch an ADMO article page and extract date + body text."""
    try:
        resp = _get(url)
        resp.raise_for_status()
    except Exception as e:
        return {"published_date": "", "raw_text": "", "error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- Extract publication date ---
    published_date = ""
    for text_node in soup.find_all(string=_DATE_RE):
        match = _DATE_RE.search(text_node.strip())
        if match:
            parsed = _parse_date(match.group())
            if parsed:
                published_date = parsed
                break

    # --- Extract body text ---
    body_paragraphs: list[str] = []
    h1 = soup.find("h1")
    if h1:
        collecting = False
        for tag in soup.find_all(["h1", "p", "h3"]):
            if tag.name == "h1":
                collecting = True
                continue
            if not collecting:
                continue
            tag_text = tag.get_text(strip=True)
            if tag.name == "h3" and tag_text in ("More on this Topic", "Related Stories"):
                break
            if tag.name == "p" and len(tag_text) > 20:
                body_paragraphs.append(tag_text)

    raw_text = "\n\n".join(body_paragraphs)
    return {"published_date": published_date, "raw_text": raw_text[:3000]}


def collect_admo() -> list[CollectedArticle]:
    """Scrape Abu Dhabi Media Office listing + article pages."""
    listing = _admo_scrape_listing()
    articles: list[CollectedArticle] = []
    cutoff = get_lookback_cutoff_date()

    for item in listing:
        article_data = _admo_scrape_article(item["url"])
        if article_data.get("error"):
            logger.warning(f"ADMO article fetch failed: {item['url']}: {article_data['error']}")

        # Enforce date cutoff at collection time — same as WAM/TII.
        # ADMO was the only scraper that skipped this check, letting
        # stale press releases (e.g., 8-day-old Habshan restoration)
        # enter the pipeline unchecked.
        pub_date = article_data.get("published_date", "")
        if pub_date:
            try:
                dt = datetime.strptime(pub_date, "%Y-%m-%d")
                if _is_before_cutoff(dt, cutoff):
                    continue
            except (ValueError, TypeError):
                pass

        articles.append(CollectedArticle(
            title=item["title"],
            snippet=article_data["raw_text"][:300],
            url=item["url"],
            source_name="Abu Dhabi Media Office",
            collected_via="scraper",
            raw_text=article_data["raw_text"],
            published_date=article_data["published_date"],
            category=item["category"],
            scout_mapping=["uae"],
        ))

    return articles


# ── 3. TII — HTML Scraper (Technology Innovation Institute) ──────────────────

TII_LISTING_URL = "https://www.tii.ae/news"


def collect_tii() -> list[CollectedArticle]:
    """Scrape TII news listing page.

    TII uses div.card-item cards where the title (h4) and link (a) are
    siblings — NOT nested. We select each card, then extract title, link,
    and date separately.
    """
    resp = _get(TII_LISTING_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    articles: list[CollectedArticle] = []
    seen_urls: set[str] = set()

    for card in soup.select("div.card-item"):
        # Title lives in h4 (inside div.card-details)
        title_tag = card.find(["h4", "h3"])
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        # Link is a sibling <a> with /news/ in href
        link = card.find("a", href=lambda h: h and "/news" in h)
        if not link:
            continue

        href = link["href"]
        if href.startswith("/"):
            url = f"https://www.tii.ae{href}"
        elif href.startswith("http"):
            url = href
        else:
            continue

        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Date appears as free text within the card
        published_date = ""
        card_text = card.get_text(" ", strip=True)
        date_match = _DATE_RE.search(card_text)
        if date_match:
            published_date = _parse_date(date_match.group())

        articles.append(CollectedArticle(
            title=title,
            snippet=title[:300],
            url=url,
            source_name="TII",
            collected_via="scraper",
            raw_text=title,
            published_date=published_date,
            category="",
            scout_mapping=["uae", "model_releases"],
        ))

    return articles


# ── 4. G42 — HTML Scraper ────────────────────────────────────────────────────

G42_LISTING_URL = "https://www.g42.ai/resources/news"


def collect_g42() -> list[CollectedArticle]:
    """Scrape G42 news listing page."""
    resp = _get(G42_LISTING_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    articles: list[CollectedArticle] = []
    seen_urls: set[str] = set()

    # G42 uses <a> tags with <h3> titles
    for link in soup.find_all("a", href=True):
        title_tag = link.find(["h3", "h4", "h2"])
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        href = link["href"]
        if href.startswith("/"):
            url = f"https://www.g42.ai{href}"
        elif href.startswith("http"):
            url = href
        else:
            continue

        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Try to find a date near the title (search within the <a> tag itself,
        # not the parent — the parent may be a shared container holding all cards)
        published_date = ""
        date_text = link.get_text(" ", strip=True)
        date_match = _DATE_RE.search(date_text)
        if date_match:
            published_date = _parse_date(date_match.group())

        articles.append(CollectedArticle(
            title=title,
            snippet=title[:300],
            url=url,
            source_name="G42",
            collected_via="scraper",
            raw_text=title,
            published_date=published_date,
            category="",
            scout_mapping=["uae", "intl_business"],
        ))

    return articles


# ── 5. Presight — HTML Scraper ───────────────────────────────────────────────

PRESIGHT_LISTING_URL = "https://www.presight.ai/news/"


def collect_presight() -> list[CollectedArticle]:
    """Scrape Presight news listing page.

    Presight uses div.blog-index__post cards. Inside each card:
      - p.intro contains the title as an <a> link
      - div.date contains the publication date
    The page loads all articles, so we filter to the last 30 days.
    """
    resp = _get(PRESIGHT_LISTING_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    articles: list[CollectedArticle] = []
    seen_urls: set[str] = set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    for card in soup.select("div.blog-index__post"):
        # Title lives in p.intro > a
        intro = card.select_one("p.intro")
        if not intro:
            continue
        link = intro.find("a", href=True)
        if not link:
            continue
        title = link.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        href = link.get("href", "")
        if href.startswith("/"):
            url = f"https://www.presight.ai{href}"
        elif href.startswith("http"):
            url = href
        else:
            continue

        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Date lives in div.date
        published_date = ""
        date_el = card.select_one("div.date")
        if date_el:
            date_match = _DATE_RE.search(date_el.get_text(strip=True))
            if date_match:
                published_date = _parse_date(date_match.group())

        # Filter: skip articles older than 30 days
        if published_date:
            try:
                dt = datetime.strptime(published_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except ValueError:
                pass

        articles.append(CollectedArticle(
            title=title,
            snippet=title[:300],
            url=url,
            source_name="Presight",
            collected_via="scraper",
            raw_text=title,
            published_date=published_date,
            category="",
            scout_mapping=["uae", "intl_business"],
        ))

    return articles


# ── 6. Khazna — WordPress REST API ──────────────────────────────────────────

KHAZNA_API_URL = "https://khaznadatacenters.com/wp-json/wp/v2/press-release"


def collect_khazna() -> list[CollectedArticle]:
    """Fetch Khazna press releases via WordPress REST API."""
    resp = _get(KHAZNA_API_URL, params={"per_page": 10})
    resp.raise_for_status()
    items = resp.json()

    articles: list[CollectedArticle] = []
    for item in items:
        title = _strip_html(item.get("title", {}).get("rendered", ""))
        excerpt = _strip_html(item.get("excerpt", {}).get("rendered", ""))
        url = item.get("link", "")
        date_str = item.get("date", "")

        published_date = ""
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                published_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        articles.append(CollectedArticle(
            title=title,
            snippet=excerpt[:300],
            url=url,
            source_name="Khazna Data Centers",
            collected_via="wordpress_api",
            raw_text=excerpt[:3000] if excerpt else title,
            published_date=published_date,
            category="",
            scout_mapping=["uae"],
        ))

    return articles



# ── 8. Newsletters — Gmail API ────────────────────────────────────────────────

# Project root for credentials.json and token.json
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GMAIL_CREDENTIALS_FILE = _PROJECT_ROOT / "credentials.json"
GMAIL_TOKEN_FILE = _PROJECT_ROOT / "token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Whitelisted newsletter senders — ONLY these are collected
NEWSLETTER_SENDERS = [
    # --- International Politics & Business ---
    {
        "from_filter": "from:noreply@news.bloomberg.com",
        "source_name": "Bloomberg Briefing",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    {
        "from_filter": "from:FT@news-alerts.ft.com",
        "source_name": "FT Briefing",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    {
        "from_filter": "from:FT@newsletters.ft.com",
        "source_name": "FT Edit",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    {
        "from_filter": "from:access@interactive.wsj.com",
        "source_name": "WSJ Briefing",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    {
        "from_filter": "from:flagship@semafor.com",
        "source_name": "Semafor Flagship",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    # --- UAE / Gulf ---
    {
        "from_filter": "from:newsletters@thenationalnews.com",
        "source_name": "The National",
        "scout_mapping": ["uae", "intl_politics"],
    },
    {
        "from_filter": "from:gulf@semafor.com",
        "source_name": "Semafor Gulf",
        "scout_mapping": ["uae", "intl_politics"],
    },
    # --- AI / Model Releases ---
    {
        "from_filter": "from:ai.plus@axios.com",
        "source_name": "Axios AI+",
        "scout_mapping": ["model_releases", "intl_business"],
    },
    {
        "from_filter": "from:swyx+ainews@substack.com",
        "source_name": "AINews (Latent Space)",
        "scout_mapping": ["model_releases"],
    },
    {
        "from_filter": "from:swyx@substack.com",
        "source_name": "AINews (Latent Space)",
        "scout_mapping": ["model_releases"],
    },
    {
        "from_filter": "from:news@alphasignal.ai",
        "source_name": "AlphaSignal",
        "scout_mapping": ["model_releases"],
    },
    {
        "from_filter": "from:newsletter@thedeepview.co",
        "source_name": "The Deep View",
        "scout_mapping": ["model_releases", "intl_business"],
    },
    {
        "from_filter": "from:dan@tldrnewsletter.com",
        "source_name": "TLDR AI",
        "scout_mapping": ["model_releases", "intl_business"],
    },
    # --- UAE + AI ---
    {
        "from_filter": "from:middleeastainews+middle-east-ai-news-minute@substack.com",
        "source_name": "Middle East AI News",
        "scout_mapping": ["uae", "model_releases"],
    },
    {
        "from_filter": "from:middleeastainews@substack.com",
        "source_name": "Middle East AI News Weekly",
        "scout_mapping": ["uae", "model_releases"],
    },
    # --- General News (Axios) ---
    {
        "from_filter": "from:mike@axios.com",
        "source_name": "Axios AM/PM",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    {
        "from_filter": "from:finishline@axios.com",
        "source_name": "Axios Finish Line",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    # --- Tech ---
    {
        "from_filter": "from:newsletters@techcrunch.com",
        "source_name": "TechCrunch",
        "scout_mapping": ["intl_business", "model_releases"],
    },
    {
        "from_filter": "from:technology@semafor.com",
        "source_name": "Semafor Technology",
        "scout_mapping": ["model_releases", "intl_business"],
    },
    # --- International ---
    {
        "from_filter": "from:newsletters@email.reuters.com",
        "source_name": "Reuters",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    {
        "from_filter": "from:dailybriefing@thomsonreuters.com",
        "source_name": "Reuters Daily Briefing",
        "scout_mapping": ["intl_politics", "intl_business"],
    },
    {
        "from_filter": "from:reuters_ai@thomsonreuters.com",
        "source_name": "Reuters AI",
        "scout_mapping": ["model_releases", "intl_business"],
    },
    {
        "from_filter": "from:gulfcurrents@thomsonreuters.com",
        "source_name": "Reuters Gulf Currents",
        "scout_mapping": ["uae", "intl_politics"],
    },
]

# Build a lookup from email address to sender config
_SENDER_LOOKUP: dict[str, dict] = {}
for _sender in NEWSLETTER_SENDERS:
    _email = _sender["from_filter"].replace("from:", "").strip().lower()
    _SENDER_LOOKUP[_email] = _sender

# End-of-content boilerplate markers (truncate everything after these)
_BOILERPLATE_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"Unsubscribe|"
    r"You received this (?:message|email|newsletter)|"
    r"Manage your preferences|"
    r"More from Bloomberg\.com|"
    r"Update your profile|"
    r"Was this email forwarded to you|"
    r"To stop receiving these emails|"
    r"Copyright \d{4}|"
    r"Terms\s*(?:&|and)\s*Conditions|"
    r"Privacy Policy\s*\|"
    r")",
    re.IGNORECASE,
)

# Header/inline junk lines to strip (NOT truncate after)
_HEADER_JUNK_RE = re.compile(
    r"^\s*(?:"
    r"View (?:this )?(?:email |post )?(?:in|on) (?:your )?(?:a )?(?:the )?(?:web )?(?:browser|app)"
    r"|Read in browser"
    r"|Open in app"
    r"|All newsletters"
    r"|Is this email difficult to read\?[^\n]*"
    r"|View this post on the web at"
    r"|Sponsored by"
    r"|Advertisement"
    r"|PRESENTED BY\b[^\n]*"
    r")\s*[›>|]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Inline URL patterns to strip from newsletter body text
_INLINE_URL_RE = re.compile(r"<https?://[^>]+>|https?://\S+")

# Semafor/AINews section markers
_SECTION_MARKER_RE = re.compile(r"(?:-->|↓↓\d*|—{3,})")

# Subjects that indicate signup/confirmation junk (not real newsletters)
_SIGNUP_SUBJECT_RE = re.compile(
    r"confirm your subscription|sign.?up confirmation|you'?ve subscribed|"
    r"verify your email|complete your subscription|"
    r"welcome to |thanks for subscribing",
    re.IGNORECASE,
)


def _get_gmail_service():
    """Build an authenticated Gmail API service.

    Uses credentials.json for OAuth2 and caches the token in token.json.
    First run requires a browser-based OAuth flow.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    token_path = str(GMAIL_TOKEN_FILE)
    creds_path = str(GMAIL_CREDENTIALS_FILE)

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"Gmail credentials file not found at {creds_path}. "
                    "Download it from Google Cloud Console."
                )
            # Only run interactive OAuth if explicitly requested via __main__
            # Otherwise raise so the collector fails gracefully instead of blocking
            if not os.environ.get("GMAIL_AUTH_INTERACTIVE"):
                raise RuntimeError(
                    "Gmail token.json not found. Run the following to authenticate:\n"
                    "  GMAIL_AUTH_INTERACTIVE=1 python3 backend/pipeline/collector.py\n"
                    "Then complete the OAuth flow in your browser."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _get_header(headers: list[dict], name: str) -> str:
    """Extract a header value from Gmail API message headers."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _pad_base64(data: str) -> str:
    """Add padding to base64url data from Gmail API (which omits '=' chars)."""
    missing = len(data) % 4
    if missing:
        data += "=" * (4 - missing)
    return data


def _extract_mime_part(
    payload: dict,
    target_mime: str,
    service=None,
    message_id: str = "",
) -> str:
    """Extract a specific MIME type body from Gmail API message payload.

    Walks multipart message parts looking for the target MIME type.
    Falls back to payload.body.data if no parts exist and mimeType matches.

    When body.data is empty but body.attachmentId exists (Gmail stores large
    bodies as attachments), fetches the attachment via the API if service and
    message_id are provided.
    """
    def _decode_body(body_obj: dict) -> str:
        """Try body.data first, then attachmentId fetch, then return ''."""
        data = body_obj.get("data", "")
        if not data and body_obj.get("attachmentId") and service and message_id:
            try:
                att = service.users().messages().attachments().get(
                    userId="me", messageId=message_id,
                    id=body_obj["attachmentId"],
                ).execute()
                data = att.get("data", "")
            except Exception as e:
                logger.warning(f"Gmail: attachment fetch failed: {e}")
        if data:
            return base64.urlsafe_b64decode(_pad_base64(data)).decode(
                "utf-8", errors="replace"
            )
        return ""

    parts = payload.get("parts", [])
    if parts:
        for part in parts:
            mime_type = part.get("mimeType", "")
            if mime_type == target_mime:
                result = _decode_body(part.get("body", {}))
                if result:
                    return result
            # Recurse into nested multipart
            if "parts" in part:
                result = _extract_mime_part(part, target_mime, service, message_id)
                if result:
                    return result

    # Fallback: body directly on payload (only if mimeType matches)
    if payload.get("mimeType", "") == target_mime:
        result = _decode_body(payload.get("body", {}))
        if result:
            return result

    return ""


def _html_to_text(html: str) -> str:
    """Convert HTML email body to plain text using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove non-content tags
    for tag in soup(["style", "script", "head", "meta", "link", "title"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _is_css_junk(text: str) -> bool:
    """Detect if text/plain is actually CSS code (e.g., FT newsletters)."""
    sample = text[:1000]
    # Check for CSS-specific patterns
    brace_count = sample.count("{") + sample.count("}")
    if brace_count > 6:
        return True
    if "color-scheme:" in sample or "@media" in sample:
        return True
    return False


def _plain_text_quality(text: str) -> int:
    """Estimate quality of text/plain after basic URL stripping.

    Returns approximate character count of non-URL, non-whitespace content.
    """
    stripped = _INLINE_URL_RE.sub("", text)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return len(stripped)


def _extract_plain_text(
    payload: dict,
    service=None,
    message_id: str = "",
) -> str:
    """Extract plain-text body from Gmail API message payload.

    Strategy:
    1. Look for text/plain MIME part — use it if it's real content (not CSS,
       not mostly URLs)
    2. Fallback: look for text/html and strip tags via BeautifulSoup
    3. If HTML also empty, use whatever text/plain we had
    """
    plain = _extract_mime_part(payload, "text/plain", service, message_id)
    plain_usable = (
        len(plain.strip()) > 100
        and not _is_css_junk(plain)
        and _plain_text_quality(plain) > 200
    )

    if plain_usable:
        return plain

    # Fallback: extract HTML and convert to text
    html = _extract_mime_part(payload, "text/html", service, message_id)
    if html.strip():
        converted = _html_to_text(html)
        if converted.strip():
            return converted

    # Last resort: return whatever text/plain we had (even if short)
    return plain


def _clean_newsletter_body(text: str) -> str:
    """Clean raw newsletter body text.

    - Strips CSS blocks (:root{...}, @media{...}, etc.)
    - Strips zero-width Unicode characters (ZWNJ, ZWS, etc.)
    - Truncates at boilerplate boundary (Unsubscribe, etc.)
    - Strips inline URLs (<https://...> and bare https://...)
    - Strips section markers (-->, ↓↓, etc.)
    - Normalises whitespace
    """
    # Normalise line endings (Gmail uses \r\n, HTML conversion uses \n)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Normalise non-breaking spaces
    text = text.replace("\xa0", " ")

    # Strip CSS blocks that leak from HTML email text/plain parts
    # Catches :root{...}, @media{...}, .class{...}, h2,p,a{...}
    text = re.sub(r"@media[^{]*\{[^}]*\}", "", text)
    text = re.sub(r"[.#:\w][^{}\n]{0,80}\{[^}]*\}", "", text)
    text = re.sub(r"supported-color-schemes:[^;\n]*;?", "", text)
    text = re.sub(r"color-scheme:[^;\n]*;?", "", text)

    # Strip zero-width / invisible Unicode characters (preheader spacers)
    text = text.replace("\u200c", "")   # ZWNJ
    text = text.replace("\u200b", "")   # ZWS
    text = text.replace("\u200d", "")   # ZWJ
    text = text.replace("\ufeff", "")   # BOM
    text = text.replace("\u00ad", "")   # Soft hyphen
    text = text.replace("\u034f", "")   # Combining Grapheme Joiner
    text = text.replace("\u2060", "")   # Word Joiner
    text = text.replace("\u180e", "")   # Mongolian Vowel Separator

    # Strip inline URLs early so header junk lines like
    # "View in browser <URL>" become just "View in browser"
    text = _INLINE_URL_RE.sub("", text)

    # Strip header/inline junk lines (View in browser, Sponsored by, etc.)
    text = _HEADER_JUNK_RE.sub("", text)

    match = _BOILERPLATE_RE.search(text)
    if match:
        text = text[:match.start()]

    text = _SECTION_MARKER_RE.sub(" ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()


_NEWSLETTER_SPLIT_SYSTEM = """\
Extract individual news stories from this newsletter. Return ONLY a JSON array.
Each story: {"headline": "...", "body": "...", "url": "..."}
- headline: the story's headline (under 15 words)
- body: the key facts in 1-3 sentences (under 300 chars). Use only what's in the text.
- url: the article URL if present, else ""
Skip ads, promos, subscription prompts, section headers, boilerplate, and sign-off content.
Return valid JSON only, no markdown."""


async def split_newsletter_with_llm(
    client,  # anthropic.AsyncAnthropic
    source_name: str,
    subject: str,
    body_text: str,
) -> list[dict]:
    """Use Haiku to extract individual stories from a newsletter body.

    Returns list of dicts with keys: headline, body, url.
    Returns [] on failure (caller falls back to unsplit article).
    """
    if not body_text or len(body_text.strip()) < 50:
        return []

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            system=_NEWSLETTER_SPLIT_SYSTEM,
            messages=[{"role": "user", "content": body_text}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        stories = safe_parse_json(raw)
        if not isinstance(stories, list):
            return []
        return [s for s in stories if isinstance(s, dict) and s.get("headline")]
    except Exception as e:
        logger.warning(f"Haiku split failed for {source_name} '{subject}': {e}")
        return []


async def split_all_newsletters(
    client,  # anthropic.AsyncAnthropic
    raw_articles: list[CollectedArticle],
) -> list[CollectedArticle]:
    """Split newsletter articles into individual stories using Haiku.

    Takes unsplit newsletter articles (category="newsletter") and returns
    individual story articles (category=""). Falls back to original article
    if Haiku returns < 2 stories.
    """
    async def _split_one(article: CollectedArticle) -> list[CollectedArticle]:
        stories = await split_newsletter_with_llm(
            client, article.source_name, article.title,
            article.raw_text,
        )
        if len(stories) < 2:
            return [article]  # Keep unsplit, category stays "newsletter"

        result = []
        for s in stories:
            headline = s.get("headline", "").strip()
            body = s.get("body", "").strip()
            url = s.get("url", "").strip()
            if not headline:
                continue
            result.append(CollectedArticle(
                title=headline,
                snippet=body[:150] if body else headline[:150],
                url=url,
                source_name=article.source_name,
                collected_via="gmail_api_haiku",
                raw_text=body[:500] if body else headline,
                published_date=article.published_date,
                category="",  # Content filter treats as normal article
                scout_mapping=list(article.scout_mapping),
            ))
        return result if result else [article]

    tasks = [_split_one(a) for a in raw_articles]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_stories: list[CollectedArticle] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Newsletter split error: {result}")
            all_stories.append(raw_articles[i])
        else:
            all_stories.extend(result)

    logger.info(
        f"Newsletter LLM split: {len(raw_articles)} newsletters → "
        f"{len(all_stories)} story items"
    )
    return all_stories


def _match_sender(from_header: str) -> dict | None:
    """Match a From header against whitelisted newsletter senders."""
    from_lower = from_header.lower()
    for email_addr, sender in _SENDER_LOOKUP.items():
        if email_addr in from_lower:
            return sender
    return None


def _parse_email_datetime(date_header: str) -> datetime | None:
    """Parse RFC 2822 email Date header into an aware datetime."""
    if not date_header:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(date_header)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def collect_newsletters() -> list[CollectedArticle]:
    """Collect newsletter articles from Gmail via the Gmail API.

    Uses get_lookback_cutoff_date() from config to determine the Gmail
    after: query date, matching the orchestrator's schedule logic.

    Returns [] if Gmail credentials are missing or auth fails.
    """
    cutoff = get_lookback_cutoff_date()
    gmail_date = cutoff.date().strftime("%Y/%m/%d")

    from_clauses = " OR ".join(s["from_filter"] for s in NEWSLETTER_SENDERS)
    query = f"({from_clauses}) after:{gmail_date}"
    logger.info(f"Gmail query: after:{gmail_date} ({len(NEWSLETTER_SENDERS)} senders)")

    service = _get_gmail_service()

    result = service.users().messages().list(
        userId="me", q=query, maxResults=50
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        logger.info("Gmail: no matching messages found")
        return []

    logger.info(f"Gmail: {len(messages)} messages matched query")

    articles: list[CollectedArticle] = []
    seen_keys: set[str] = set()

    for msg_meta in messages:
        msg_id = msg_meta["id"]

        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as e:
            logger.warning(f"Gmail: failed to fetch message {msg_id}: {e}")
            continue

        headers = msg.get("payload", {}).get("headers", [])
        from_header = _get_header(headers, "From")
        subject = _get_header(headers, "Subject")
        date_header = _get_header(headers, "Date")

        sender = _match_sender(from_header)
        if not sender:
            logger.debug(f"Gmail: skipping non-whitelisted sender: {from_header}")
            continue

        # Skip signup/confirmation junk
        if _SIGNUP_SUBJECT_RE.search(subject):
            logger.debug(f"Gmail: skipping signup email: {subject}")
            continue

        dedup_key = f"{sender['source_name']}||{subject}".lower()
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        payload = msg.get("payload", {})
        raw_body = _extract_plain_text(payload, service=service, message_id=msg_id)
        body_text = _clean_newsletter_body(raw_body)

        logger.info(
            f"Gmail extract: {sender['source_name']:30s} | "
            f"text={len(body_text):5d} chars | {subject[:50]}"
        )

        # Multi-story newsletters (Semafor, FT, WSJ) need enough body
        # text for the Haiku splitter to see ALL stories. 5k was cutting
        # off stories 6-10 in Semafor Flagship (typically 10 items).
        is_ainews = sender["source_name"] == "AINews (Latent Space)"
        max_chars = 12000 if is_ainews else 10000

        title = subject
        if is_ainews and title.startswith("[AINews]"):
            title = title[len("[AINews]"):].strip()

        published_dt = _parse_email_datetime(date_header)
        if _is_before_cutoff(published_dt, cutoff):
            dubai_dt = _ensure_aware_datetime(published_dt).astimezone(DUBAI_TZ)
            logger.debug(
                "Gmail: skipping %s because %s is older than cutoff %s",
                subject,
                dubai_dt.isoformat(),
                cutoff.isoformat(),
            )
            continue
        published_date, published_at = _to_dubai_published_fields(published_dt)

        # Return one article per newsletter (LLM splitting happens later)
        articles.append(CollectedArticle(
            title=title,
            snippet=body_text[:300],
            url="",
            source_name=sender["source_name"],
            collected_via="gmail_api",
            raw_text=body_text[:max_chars],
            published_date=published_date,
            category="newsletter",
            published_at=published_at,
            scout_mapping=list(sender["scout_mapping"]),
        ))

    return articles



# ── X/Twitter Timeline collector ─────────────────────────────────────────────

# Hardcoded user ID for @hhtbzayed — avoids a lookup API call each run.
_TAHNOON_USER_ID = "1671393095345119238"
_X_API_BASE = "https://api.x.com/2"
_LOOKBACK_HOURS_DEFAULT = 48
_LOOKBACK_HOURS_MONDAY = 72


def _is_english(text: str) -> bool:
    """Quick heuristic: treat as English if first 60 chars are mostly Latin."""
    sample = text.strip()[:60]
    latin_chars = len(re.findall(r"[A-Za-z]", sample))
    return latin_chars > len(sample) * 0.4


def collect_x_tahnoon() -> list[CollectedArticle]:
    """Fetch recent posts from Sheikh Tahnoon bin Zayed (@hhtbzayed).

    Uses X API v2. Returns English-language posts from the last 48h
    (72h on Monday) as CollectedArticle items mapped to 'uae'.
    He posts each update twice (Arabic then English ~1 min later);
    we filter to English-only to avoid duplicates.
    """
    bearer = os.environ.get("X_BEARER_TOKEN", "")
    if not bearer:
        # Escalated to ERROR so it surfaces in Cloud Run logs at the same
        # level as a collector failure (was WARNING, which was easy to miss).
        # The CollectorSkipped exception also routes to pipeline_runs.source_errors
        # via _run_one_collector → source_logs → _parse_collection_log.
        logger.error(
            "X_BEARER_TOKEN is not set in the environment — the x_tahnoon "
            "collector will contribute zero items. Set the env var or remove "
            "x_tahnoon from _COLLECTORS to silence this error."
        )
        raise CollectorSkipped("missing X_BEARER_TOKEN")

    headers = {"Authorization": f"Bearer {bearer}"}

    # Monday = 0 in Python's weekday()
    lookback = (
        _LOOKBACK_HOURS_MONDAY
        if datetime.now(timezone.utc).weekday() == 0
        else _LOOKBACK_HOURS_DEFAULT
    )
    start_time = (
        datetime.now(timezone.utc) - timedelta(hours=lookback)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "max_results": 10,
        "start_time": start_time,
        "tweet.fields": "created_at,text",
        "exclude": "retweets,replies",
    }
    url = f"{_X_API_BASE}/users/{_TAHNOON_USER_ID}/tweets"

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"X API request failed: {e}")
        return []

    try:
        data = resp.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        logger.error("X API returned non-JSON response (status %d)", resp.status_code)
        return []
    tweets = data.get("data", [])
    if not tweets:
        logger.info("X/@hhtbzayed: no new posts in the last %d hours", lookback)
        return []

    articles = []
    for tweet in tweets:
        text = tweet.get("text", "")

        # Skip Arabic duplicates — keep English versions only
        if not _is_english(text):
            continue

        tweet_id = tweet["id"]
        created_at = tweet.get("created_at", "")

        try:
            date_str = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            date_str = datetime.now().strftime("%Y-%m-%d")

        # Build a clean title from the first line, capped at 120 chars
        title = text.split("\n")[0][:120]
        if len(title) == 120:
            title = title.rsplit(" ", 1)[0] + "…"

        post_url = f"https://x.com/hhtbzayed/status/{tweet_id}"

        articles.append(CollectedArticle(
            title=title,
            snippet=text[:300],
            url=post_url,
            source_name="X / @hhtbzayed",
            collected_via="api",
            raw_text=text,
            published_date=date_str,
            category="",
            scout_mapping=["uae"],
        ))

    # Distinguish "genuinely quiet" from "all-filtered" — the latter is a
    # silent 0-yield that hid behind an INFO log in the 2026-04-15 audit.
    if len(tweets) > 0 and len(articles) == 0:
        logger.warning(
            "X/@hhtbzayed: %d tweets in window but 0 passed the English-language "
            "filter. Confirm _is_english() is still behaving as expected.",
            len(tweets),
        )
    else:
        logger.info(
            "X/@hhtbzayed: %d English posts collected (of %d total in window)",
            len(articles), len(tweets),
        )
    return articles


# ── Orchestration ────────────────────────────────────────────────────────────

# Registry of all collectors: (name, type, function)
_COLLECTORS: list[tuple[str, str, callable]] = [
    ("wam", "api", collect_wam),
    ("admo", "scraper", collect_admo),
    ("tii", "scraper", collect_tii),
    ("g42", "scraper", collect_g42),
    ("presight", "scraper", collect_presight),
    ("khazna", "wordpress_api", collect_khazna),
    ("newsletters", "gmail_api", collect_newsletters),
    ("x_tahnoon", "api", collect_x_tahnoon),
]


def _run_one_collector(
    name: str, ctype: str, func: callable
) -> tuple[str, str, str, list[CollectedArticle], float]:
    """Run a single collector with error handling and timing.

    Returns (name, type, status, articles, elapsed_seconds).
    """
    start = time.time()
    try:
        articles = func()
        elapsed = time.time() - start
        logger.info(f"Collector {name}: {len(articles)} articles in {elapsed:.1f}s")
        return name, ctype, "success", articles, elapsed
    except CollectorSkipped as e:
        elapsed = time.time() - start
        logger.warning(f"Collector {name} skipped after {elapsed:.1f}s: {e}")
        return name, ctype, f"skipped: {e}", [], elapsed
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Collector {name} failed after {elapsed:.1f}s: {e}", exc_info=True)
        return name, ctype, f"error: {e}", [], elapsed


async def run_all_collectors() -> list[CollectedArticle]:
    """Run all collectors concurrently and return merged, deduplicated articles.

    Each sync collector runs in a thread via asyncio.to_thread().
    Saves a collection_log_{today}.json with per-source stats.
    """
    today = get_today_date()
    start = time.time()

    # Run all collectors concurrently in threads
    tasks = [
        asyncio.to_thread(_run_one_collector, name, ctype, func)
        for name, ctype, func in _COLLECTORS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect articles and build log
    all_articles: list[CollectedArticle] = []
    source_logs: list[dict] = []
    seen_cache = load_cache(OUTPUT_DIR)

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Collector task raised: {result}")
            source_logs.append({
                "name": "unknown",
                "type": "unknown",
                "status": f"error: {result}",
                "articles": 0,
                "seconds": 0,
            })
            continue

        name, ctype, status, articles, elapsed = result

        # For infrequent publishers, skip items we've already seen.
        cached_count = 0
        if name in CACHED_COLLECTORS and articles:
            all_fetched = articles  # keep reference to full set
            articles, cached_count = filter_new_items(name, articles, seen_cache)
            # Always update cache with the FULL URL set (not just new items).
            update_cache_entry(name, all_fetched, seen_cache)
            if cached_count and not articles:
                logger.info(
                    "Collector %s: all %d items already seen — skipping",
                    name, cached_count,
                )
                status = "success (no new content)"

        all_articles.extend(articles)
        log_entry: dict = {
            "name": name,
            "type": ctype,
            "status": status,
            "articles": len(articles),
            "seconds": round(elapsed, 1),
        }
        if cached_count:
            log_entry["cached_skipped"] = cached_count
        source_logs.append(log_entry)

    total_elapsed = time.time() - start

    # Persist seen-URL cache for next run
    save_cache(OUTPUT_DIR, seen_cache)

    # Save collection log (no dedup here — pipeline-level dedup handles it)
    collection_log = {
        "collection_date": today,
        "total_seconds": round(total_elapsed, 1),
        "sources": source_logs,
        "total_articles": len(all_articles),
    }
    log_path = OUTPUT_DIR / f"collection_log_{today}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(collection_log, f, indent=2, ensure_ascii=False)

    logger.info(
        f"Collection complete: {len(all_articles)} articles from "
        f"{len(_COLLECTORS)} sources in {total_elapsed:.1f}s"
    )

    return all_articles


# ── Standalone test runner ───────────────────────────────────────────────────

async def _main():
    """Run all collectors and print results."""
    import sys

    # Enable interactive OAuth flow when run standalone
    os.environ["GMAIL_AUTH_INTERACTIVE"] = "1"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    print("Running all collectors...")
    articles = await run_all_collectors()

    today = get_today_date()
    log_path = OUTPUT_DIR / f"collection_log_{today}.json"
    with open(log_path) as f:
        log = json.load(f)

    # Print collection log
    print(f"\n{'='*70}")
    print(f"COLLECTION LOG — {today}")
    print(f"{'='*70}")
    print(f"Total time: {log['total_seconds']:.1f}s")
    print(f"Total articles: {log['total_articles']}")
    print(f"\nPer-source breakdown:")
    for src in log["sources"]:
        status_icon = "✅" if src["status"] == "success" else "❌"
        print(f"  {status_icon} {src['name']:12s} [{src['type']:14s}] "
              f"{src['articles']:4d} articles  ({src['seconds']:.1f}s) "
              f"{'— ' + src['status'] if src['status'] != 'success' else ''}")

    # Date breakdown
    dates: dict[str, int] = {}
    for a in articles:
        d = a.published_date or "(no date)"
        dates[d] = dates.get(d, 0) + 1
    print(f"\nBy date:")
    for d, count in sorted(dates.items(), reverse=True):
        print(f"  {d}: {count}")

    # Source breakdown
    sources: dict[str, int] = {}
    for a in articles:
        sources[a.source_name] = sources.get(a.source_name, 0) + 1
    print(f"\nBy source:")
    for s, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {s}: {count}")

    # Show first 20 articles
    print(f"\n{'='*70}")
    print(f"FIRST 20 ARTICLES")
    print(f"{'='*70}")
    for a in articles[:20]:
        print(f"\n  [{a.published_date or 'no date'}] [{a.source_name}] [{a.category}]")
        print(f"  {a.title}")
        if a.snippet and a.snippet != a.title:
            print(f"  {a.snippet[:120]}...")
        print(f"  {a.url}")

    # Save full output
    output = [asdict(a) for a in articles]
    output_path = OUTPUT_DIR / f"collected_raw_{today}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nFull output saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(_main())
