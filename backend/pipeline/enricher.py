"""
Content Enrichment Stage
========================
Detects thin items (< 80 words of raw_content) among gatekeeper-selected items
and enriches them via a progressive 3-step chain:

  Step 1: Fetch the source URL via trafilatura (free, fast)
  Step 2: Serper web search + trafilatura fetch of top results
  Step 3: Sonnet research agent with web_search tool (last resort)

Between steps, a Haiku judge evaluates whether content is now sufficient
for the ghostwriter to produce a substantive brief entry. The chain stops
early when the judge says SUFFICIENT.

Enrichment data is attached as structured metadata — NOT concatenated
into raw_content — so the ghostwriter can distinguish original source
material from supplementary extracts.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from urllib.parse import urlparse

import httpx

from config import CONTENT_FILTER_MODEL, MODEL, PROMPTS_DIR, get_today_date
from prompts.loader import extract_prompt_from_md
from pipeline.model_release import (
    attach_model_release_packet,
    build_model_release_packet,
    build_model_release_queries as build_model_release_queries_impl,
    classify_model_release_heuristics,
    classify_model_release_result,
    is_probable_model_release,
    is_possible_model_release,
    reserve_model_release_search_results,
    summarise_model_release_completeness,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
THIN_THRESHOLD = 80  # words
MODEL_RELEASE_MIN_ENRICHMENT_WORDS = 80
GENERAL_MIN_ENRICHMENT_WORDS = 50
MAX_EXTRACT_WORDS = 800
SERPER_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
JINA_BASE_URL = "https://r.jina.ai/"
ENRICHMENT_SEMAPHORE_LIMIT = 15
ANTHROPIC_MAX_ATTEMPTS = 3
ANTHROPIC_RETRY_DELAYS = [1, 2, 4]

PAYWALL_PHRASES = [
    "subscribe to continue",
    "subscription required",
    "sign in to read",
    "create a free account",
    "you've reached your limit",
    "premium content",
    "members only",
    "register to read",
    "paywall",
    "subscribe now to read",
]

# Deal / fundraise / M&A detection regex
DEAL_CUE_RE = re.compile(
    r"\b("
    r"funding round|fundraise[ds]?|series [a-z]|seed round|"
    r"raise[ds]? \$|raising \$|"
    r"acqui(?:res?|red?|sition|ring)|merger?|merg(?:e[ds]?|ing)|"
    r"(?:pre|post)[- ]money valuation|valued at|"
    r"ipo(?:\b|'d)|going public|"
    r"investment round|"
    r"(?:led|backed) by .{0,30}(?:capital|ventures?|partners?)"
    r")\b",
    re.IGNORECASE,
)


def is_probable_deal(item: dict) -> bool:
    """Return True when headline/content contains deal/fundraise language.

    Model releases take priority — if an item is already flagged as a model
    release, it is not a deal item even if deal keywords appear.
    """
    if item.get("is_model_release"):
        return False
    text = f"{item.get('headline', '')} {_normalise_raw_content(item.get('raw_content', ''))}"
    return bool(DEAL_CUE_RE.search(text))


def _build_deal_queries(
    headline: str, entities=None
) -> list[dict]:
    """Build supplementary search queries for deal/fundraise enrichment."""
    # Extract the most likely company name from entities or headline
    company = ""
    if entities:
        # Use the first entity (typically the primary company)
        company = entities[0].replace("**", "").strip()
    else:
        # Fall back to first few words of headline before a verb
        company = headline.split()[0] if headline else ""

    queries = []
    if company:
        queries.append({
            "query": f"{company} funding round total amount valuation",
            "query_intent": "deal_terms",
        })
        queries.append({
            "query": f"{company} investors lead round Series",
            "query_intent": "deal_parties",
        })
    # Always add headline-derived query
    queries.append({
        "query": f"{headline} deal terms valuation",
        "query_intent": "deal_overview",
    })
    return queries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_raw_content(raw_content) -> str:
    """Convert raw_content to a plain string if it's a dict or list."""
    if isinstance(raw_content, dict):
        return json.dumps(raw_content, ensure_ascii=False)
    if isinstance(raw_content, list):
        return json.dumps(raw_content, ensure_ascii=False)
    return str(raw_content) if raw_content else ""


def is_thin(item: dict) -> bool:
    """Return True if the item's raw_content has fewer than THIN_THRESHOLD words."""
    text = _normalise_raw_content(item.get("raw_content", ""))
    return len(text.split()) < THIN_THRESHOLD


def _truncate_at_sentence(text: str, max_words: int = MAX_EXTRACT_WORDS) -> str:
    """Truncate text at a sentence boundary near max_words."""
    words = text.split()
    if len(words) <= max_words:
        return text

    # Take max_words, then find the last sentence-ending punctuation
    truncated = " ".join(words[:max_words])
    # Look for last sentence boundary
    for punct in [". ", "? ", "! "]:
        idx = truncated.rfind(punct)
        if idx > len(truncated) * 0.5:  # Only cut if we keep >50% of content
            return truncated[: idx + 1].strip()

    # No good sentence boundary — just use the word limit
    return truncated.strip()


def _sync_model_release_flag(item: dict) -> bool:
    """Recompute whether an item should carry model-release structure."""
    is_model_release = is_probable_model_release(item)
    item["is_model_release"] = is_model_release

    if not is_model_release:
        item.pop("model_release_data", None)
        item.pop("benchmark_facts", None)
        item.pop("key_number_facts", None)
        item.pop("coverage_notes", None)

    return is_model_release


def _set_model_release_flag(item: dict, is_model_release: bool) -> bool:
    """Set the model-release flag and clear stale structured fields when false."""
    item["is_model_release"] = bool(is_model_release)
    if not is_model_release:
        item.pop("model_release_data", None)
        item.pop("benchmark_facts", None)
        item.pop("key_number_facts", None)
        item.pop("coverage_notes", None)
    return bool(is_model_release)


def _record_model_release_classifier_meta(item: dict, **updates) -> dict:
    """Attach lightweight classifier metadata for debugging and replay."""
    meta = item.get("_model_release_classifier")
    if not isinstance(meta, dict):
        meta = {}
        item["_model_release_classifier"] = meta
    meta.update(updates)
    return meta


async def _resolve_ambiguous_model_release_with_haiku(
    client,
    item: dict,
    signals: dict,
) -> tuple[bool, dict]:
    """Use Haiku as a tie-breaker for ambiguous model-card cases."""
    prompt = f"""Decide whether this news item should use the SPECIAL model-release card UI.

Return JSON only:
{{
  "should_render_model_card": true,
  "confidence": 0.0,
  "reason": "short reason"
}}

Use TRUE only for an actual deployable model launch with a clear developer-facing
surface such as an API, model card, docs, platform availability, chat interface,
or a comparable productized release surface.

Use FALSE for:
- funding rounds or companies raising money to build a future model
- ecosystem rankings, usage tables, or market-share stories
- benchmark-only/evaluation-only stories
- research-domain releases where the item is effectively paper + weights rather
  than a broadly deployable model launch

Item:
- headline: {signals.get("headline", "")}
- summary: {signals.get("summary", "")}
- raw_content: {signals.get("raw_content", "")[:2500]}
- brief_section: {signals.get("section", "")}
- variants: {signals.get("variants", [])}
- has_official_source: {signals.get("has_official_source")}
- has_product_deployment_cue: {signals.get("has_product_deployment_cue")}
- urls: {signals.get("urls", [])[:5]}
"""

    try:
        response = await _anthropic_messages_create_with_retry(
            client,
            "Model release ambiguity resolver",
            model=CONTENT_FILTER_MODEL,
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  [enricher] Model release ambiguity resolver failed: {e}")
        return False, {
            "decision_source": "haiku_error",
            "confidence": 0.0,
            "reason": str(e),
        }

    result_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            result_text = block.text

    parsed = _parse_judge_json(result_text) if result_text else {}
    decision = bool(parsed.get("should_render_model_card"))
    try:
        confidence = float(parsed.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    return decision, {
        "decision_source": "haiku",
        "confidence": confidence,
        "reason": str(parsed.get("reason", "") or "").strip(),
    }


async def _finalize_model_release_flag(item: dict, client) -> bool:
    """Resolve the final model-release decision, using Haiku only for ambiguity."""
    meta = item.get("_model_release_classifier")
    if isinstance(meta, dict) and meta.get("finalized"):
        return bool(item.get("is_model_release"))

    heuristic_decision, signals = classify_model_release_heuristics(item)
    heuristic_label = (
        "true" if heuristic_decision is True else
        "false" if heuristic_decision is False else
        "ambiguous"
    )
    _record_model_release_classifier_meta(
        item,
        heuristic_decision=heuristic_label,
        heuristic_signals={
            "has_variant": signals.get("has_variant"),
            "has_model_root": signals.get("has_model_root"),
            "has_release_cue": signals.get("has_release_cue"),
            "has_model_artifact_cue": signals.get("has_model_artifact_cue"),
            "has_product_deployment_cue": signals.get("has_product_deployment_cue"),
            "has_official_source": signals.get("has_official_source"),
            "has_research_publication_cue": signals.get("has_research_publication_cue"),
            "has_scientific_domain_cue": signals.get("has_scientific_domain_cue"),
            "has_funding_or_build_cue": signals.get("has_funding_or_build_cue"),
            "has_market_or_ranking_cue": signals.get("has_market_or_ranking_cue"),
        },
    )

    if heuristic_decision is not None:
        _record_model_release_classifier_meta(
            item,
            final_decision=bool(heuristic_decision),
            decision_source="heuristic",
            finalized=True,
        )
        return _set_model_release_flag(item, bool(heuristic_decision))

    llm_decision, llm_meta = await _resolve_ambiguous_model_release_with_haiku(
        client,
        item,
        signals,
    )
    _record_model_release_classifier_meta(
        item,
        final_decision=llm_decision,
        finalized=True,
        **llm_meta,
    )
    return _set_model_release_flag(item, llm_decision)


def _parse_judge_json(text: str) -> dict:
    """Parse the judge's JSON response, stripping markdown code fences if present."""
    cleaned = text.strip()
    # Strip ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: INSUFFICIENT with low confidence
        return {
            "decision": "INSUFFICIENT",
            "confidence": 0.0,
            "missing_elements": ["Failed to parse judge response"],
            "recommended_query_terms": [],
            "reasoning": "Judge response was not valid JSON",
        }


def _is_paywall_content(text: str) -> bool:
    """Detect if extracted text is mostly paywall messaging."""
    lower = text.lower()
    if len(text.split()) < 50:
        return any(phrase in lower for phrase in PAYWALL_PHRASES)
    return False


def _extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _default_judge_result(reasoning: str, confidence: float = 0.0) -> dict:
    """Return a safe fallback judge result."""
    return {
        "decision": "INSUFFICIENT",
        "confidence": confidence,
        "missing_elements": [],
        "recommended_query_terms": [],
        "reasoning": reasoning,
    }


def _normalise_judge_result(result: dict | None, fallback_reasoning: str) -> dict:
    """Ensure the stored judge result always has the expected audit fields."""
    result = result or {}
    decision = str(result.get("decision", "INSUFFICIENT")).upper()
    if decision not in {"SUFFICIENT", "INSUFFICIENT"}:
        decision = "INSUFFICIENT"

    confidence = result.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    missing_elements = result.get("missing_elements", [])
    if not isinstance(missing_elements, list):
        missing_elements = [str(missing_elements)]

    recommended_query_terms = result.get("recommended_query_terms", [])
    if not isinstance(recommended_query_terms, list):
        recommended_query_terms = [str(recommended_query_terms)]

    reasoning = str(result.get("reasoning", fallback_reasoning) or fallback_reasoning)

    return {
        "decision": decision,
        "confidence": confidence,
        "missing_elements": [str(x) for x in missing_elements[:5]],
        "recommended_query_terms": [str(x) for x in recommended_query_terms[:5]],
        "reasoning": reasoning,
    }


def _enforce_minimum_substance(
    headline: str,
    raw_content: str,
    extracts: list[dict],
    judge_result: dict,
    is_model_release: bool,
) -> dict:
    """Force very short raw-only items to continue enrichment.

    Haiku can occasionally mark a short newsletter snippet as "SUFFICIENT".
    That produces thin brief entries. If we still have no supplementary
    extracts and the original raw_content is below a minimum threshold,
    require at least one more enrichment step. Model releases need a higher
    minimum because Ghostwriter expects richer technical/commercial detail.
    """
    if judge_result.get("decision") != "SUFFICIENT" or extracts:
        return judge_result

    raw_word_count = len(_normalise_raw_content(raw_content).split())
    minimum_words = (
        MODEL_RELEASE_MIN_ENRICHMENT_WORDS
        if is_model_release
        else GENERAL_MIN_ENRICHMENT_WORDS
    )
    if raw_word_count >= minimum_words:
        return judge_result

    missing_elements = list(judge_result.get("missing_elements") or [])
    if is_model_release:
        for element in (
            "official announcement or release notes",
            "benchmark or eval context",
            "pricing or availability",
        ):
            if element not in missing_elements:
                missing_elements.append(element)
        reasoning = (
            f"Raw content is only {raw_word_count} words with no supplementary extracts; "
            f"model-release items under {MODEL_RELEASE_MIN_ENRICHMENT_WORDS} words must continue "
            "to web search for official launch details, benchmark context, and commercial terms."
        )
    else:
        for element in ("scale or consequences", "supporting context"):
            if element not in missing_elements:
                missing_elements.append(element)
        reasoning = (
            f"Raw content is only {raw_word_count} words with no supplementary extracts; "
            "that is too thin for a substantive brief entry."
        )

    recommended_terms = list(judge_result.get("recommended_query_terms") or [])
    if not recommended_terms:
        recommended_terms = [headline]

    return {
        **judge_result,
        "decision": "INSUFFICIENT",
        "confidence": min(float(judge_result.get("confidence", 0.0) or 0.0), 0.35),
        "missing_elements": missing_elements[:5],
        "recommended_query_terms": [str(term) for term in recommended_terms[:5]],
        "reasoning": reasoning,
    }


async def _anthropic_messages_create_with_retry(client, request_name: str, **kwargs):
    """Call Anthropic with bounded retries for transient failures."""
    last_error = None

    for attempt in range(ANTHROPIC_MAX_ATTEMPTS):
        try:
            return await client.messages.create(**kwargs)
        except Exception as e:
            last_error = e
            if attempt < ANTHROPIC_MAX_ATTEMPTS - 1:
                wait = ANTHROPIC_RETRY_DELAYS[min(attempt, len(ANTHROPIC_RETRY_DELAYS) - 1)]
                print(
                    f"  [enricher] {request_name} failed "
                    f"(attempt {attempt + 1}/{ANTHROPIC_MAX_ATTEMPTS}): {e}. "
                    f"Retrying in {wait}s"
                )
                await asyncio.sleep(wait)

    raise RuntimeError(
        f"{request_name} failed after {ANTHROPIC_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# Step 1: Source URL Fetch
# ---------------------------------------------------------------------------


_WAM_ARTICLE_RE = re.compile(
    r"^https?://(?:www\.)?wam\.ae/(?P<lang>en|ar)/article/(?P<slug>[^/?#]+)"
)
_WAM_API_BASE = "https://www.wam.ae/api/app/articles/GetArticleBySlug"
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _parse_wam_slug(url: str) -> tuple[str, str] | None:
    """Return (slug, lang) for a WAM article URL, or None if not a WAM URL."""
    m = _WAM_ARTICLE_RE.match(url or "")
    if not m:
        return None
    return m.group("slug"), m.group("lang")


def _html_to_text(html_str: str) -> str:
    """Strip HTML tags, unescape entities, collapse whitespace."""
    import html as html_lib

    text = _HTML_TAG_RE.sub(" ", html_str or "")
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


async def fetch_wam_article(url: str) -> dict | None:
    """Fetch a WAM article via its per-article JSON API.

    WAM is a client-side-rendered SPA — trafilatura/Jina return only a
    ~280-char stub. But WAM exposes its own per-article endpoint that
    returns the full HTML body (see stress_test on 2026-04-17):
    `/api/app/articles/GetArticleBySlug?slug=<slug>`.

    Returns the standard fetch-result dict or None on miss. Callers get
    `source_step="wam_api"` so the audit trail distinguishes this path.
    """
    parsed = _parse_wam_slug(url)
    if not parsed:
        return None
    slug, _lang = parsed
    try:
        async with httpx.AsyncClient(timeout=JINA_TIMEOUT) as http:
            resp = await http.get(
                _WAM_API_BASE,
                params={"slug": slug},
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
        body_html = (data.get("body") or "").strip()
        if not body_html:
            return None
        text = _html_to_text(body_html)
        if not text or _is_paywall_content(text):
            return None
        return {
            "url": url,
            "title": (data.get("title") or "").strip(),
            "extract": _truncate_at_sentence(text),
            "source_step": "wam_api",
        }
    except Exception as e:
        print(f"  [enricher] WAM API fetch failed for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Pre-triage WAM body fill
# ---------------------------------------------------------------------------
# WAM sitemap entries frequently arrive with raw_content == headline because
# the article isn't on any of the API listing pages the collector enriches
# from. Those thin items get misclassified as "ceremonial/protocol" by the
# Haiku triage stage even when the underlying article is substantive (see
# 2026-04-23 MBZ-Musk drop).

_WAM_PREFILL_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
_WAM_PREFILL_SEMAPHORE_LIMIT = 10
_WAM_THIN_BODY_CHAR_THRESHOLD = 200
# "ABU DHABI, 22nd April, 2026 (WAM) -- " and friends. The CITY group
# tolerates multi-word cities ("ABU DHABI", "RAS AL KHAIMAH") and the
# day-ordinal suffix ("nd"/"st"/"rd"/"th") is optional.
_WAM_DATELINE_RE = re.compile(
    r"^[A-Z][A-Z\s,'-]+,?\s*\d{1,2}(?:st|nd|rd|th)?\s+\w+,?\s*\d{4}\s*\(WAM\)\s*--?\s*"
)


def _strip_wam_dateline(text: str) -> str:
    """Strip the leading 'CITY, Nth Month, YYYY (WAM) --' dateline.

    No-op when the pattern doesn't match, so safe to call on any string.
    """
    return _WAM_DATELINE_RE.sub("", text or "", count=1).strip()


def _is_thin_wam_item(item: dict) -> bool:
    """Return True if this WAM item's body is effectively a headline echo."""
    if (item.get("source") or "").upper() != "WAM":
        return False
    raw = (item.get("raw_content") or "").strip()
    headline = (item.get("headline") or "").strip()
    if not raw:
        return True
    if raw == headline:
        return True
    return len(raw) < _WAM_THIN_BODY_CHAR_THRESHOLD


async def fill_thin_wam_bodies(items: list[dict]) -> dict:
    """Fetch full bodies for WAM items whose raw_content is headline-thin.

    Runs BEFORE triage so Haiku has substantive signal to distinguish
    protocol calls from real news. For each qualifying item, calls
    ``fetch_wam_article`` under a bounded semaphore, strips the WAM
    dateline, and writes the text into ``raw_content`` + ``summary``.

    Fail-open: if the API errors or returns nothing, the item is left
    unchanged and downstream stages decide. Mirrors the semaphore + per-
    item try/except pattern at ``enrich_item`` (see ``_enrich_with_semaphore``).

    Returns a log dict suitable for ``save_intermediate``.
    """
    candidates = [
        (i, it) for i, it in enumerate(items)
        if _is_thin_wam_item(it) and (it.get("source_url") or "")
    ]
    log = {
        "total_scanned": len(items),
        "candidates": len(candidates),
        "fetched": 0,
        "enriched": 0,
        "failed": 0,
        "skipped": 0,
        "per_item": [],
    }
    if not candidates:
        return log

    semaphore = asyncio.Semaphore(_WAM_PREFILL_SEMAPHORE_LIMIT)

    async def _run_one(idx: int, item: dict) -> None:
        headline = (item.get("headline") or "").strip()
        len_before = len((item.get("raw_content") or "").strip())
        async with semaphore:
            try:
                result = await asyncio.wait_for(
                    fetch_wam_article(item.get("source_url", "")),
                    timeout=_WAM_PREFILL_TIMEOUT.read + 2.0,
                )
            except Exception as e:  # fail-open
                log["failed"] += 1
                log["per_item"].append({
                    "headline": headline,
                    "outcome": "error",
                    "error": str(e)[:200],
                    "len_before": len_before,
                    "len_after": len_before,
                })
                return
        if not result or not result.get("extract"):
            log["skipped"] += 1
            log["per_item"].append({
                "headline": headline,
                "outcome": "no_body_returned",
                "len_before": len_before,
                "len_after": len_before,
            })
            return
        log["fetched"] += 1
        stripped = _strip_wam_dateline(result["extract"])
        if len(stripped) <= len_before:
            log["skipped"] += 1
            log["per_item"].append({
                "headline": headline,
                "outcome": "not_longer",
                "len_before": len_before,
                "len_after": len(stripped),
            })
            return
        item["raw_content"] = stripped
        item["summary"] = stripped[:300]
        log["enriched"] += 1
        log["per_item"].append({
            "headline": headline,
            "outcome": "enriched",
            "len_before": len_before,
            "len_after": len(stripped),
        })

    await asyncio.gather(*[_run_one(i, it) for i, it in candidates])
    return log


async def _fetch_via_serper(url: str) -> dict | None:
    """Fetch article content via Serper's /scrape endpoint.

    Faster than Jina (~1.5s vs ~13s median) but returns less content on
    some sites. Used as the first network fallback after trafilatura;
    Jina remains the deep-coverage last resort.
    """
    if not SERPER_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=SERPER_TIMEOUT) as http:
            resp = await http.post(
                "https://scrape.serper.dev",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json",
                },
                json={"url": url},
            )
            resp.raise_for_status()
            data = resp.json()
        content = (
            data.get("text") or data.get("content") or data.get("markdown") or ""
        ).strip()
        title = (data.get("metadata", {}).get("title") or data.get("title") or "").strip()
        if not content or _is_paywall_content(content):
            return None
        return {
            "url": url,
            "title": title,
            "extract": _truncate_at_sentence(content),
            "source_step": "serper_scrape",
        }
    except Exception as e:
        print(f"  [enricher] Serper scrape failed for {url}: {e}")
        return None


async def _fetch_via_jina(url: str) -> dict | None:
    """Last-resort fallback: fetch article content via Jina Reader API.

    Slower than Serper but tends to return more content. Kept as a net
    for sites where Serper returns stub-only responses.
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=JINA_TIMEOUT) as http:
            resp = await http.get(f"{JINA_BASE_URL}{url}", headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = (data.get("data", {}).get("content") or "").strip()
        title = (data.get("data", {}).get("title") or "").strip()

        if not content or _is_paywall_content(content):
            print(f"  [enricher] Jina fallback returned empty/paywall for {url}")
            return None

        return {
            "url": url,
            "title": title,
            "extract": _truncate_at_sentence(content),
            "source_step": "jina_fallback",
        }
    except Exception as e:
        print(f"  [enricher] Jina fallback failed for {url}: {e}")
        return None


async def fetch_source_url(url: str, include_tables: bool = False) -> dict | None:
    """Fetch and extract article text from the source URL.

    Fallback chain (first success wins):
      1. WAM per-article JSON API (wam.ae only — the SPA shell defeats
         trafilatura/Jina, so this is the only reliable source for
         80%+ of our URL volume).
      2. trafilatura (fast, local, free — works on most cooperative
         static HTML sites).
      3. Serper /scrape (paid, ~1.5s, reliable on anti-bot sites).
      4. Jina Reader (free tier, slower, deepest content coverage).

    Returns dict with url, title, extract, source_step or None on
    total failure. All trafilatura calls run via asyncio.to_thread()
    since they are blocking.
    """
    if not url or not url.startswith("http"):
        return None

    # --- WAM shortcut: skip trafilatura/Jina on wam.ae (empirically broken)
    if _parse_wam_slug(url):
        result = await fetch_wam_article(url)
        if result:
            return result
        print(f"  [enricher] WAM API returned nothing for {url}, falling through")

    # --- Primary: trafilatura (fast, no API dependency) ---
    try:
        from trafilatura import extract, fetch_url

        downloaded = await asyncio.to_thread(fetch_url, url)
        if downloaded:
            text = await asyncio.to_thread(
                extract,
                downloaded,
                include_comments=False,
                include_tables=include_tables,
                favor_recall=True,
            )

            if text and not _is_paywall_content(text):
                return {
                    "url": url,
                    "title": "",
                    "extract": _truncate_at_sentence(text),
                    "source_step": "url_fetch",
                }
    except Exception as e:
        print(f"  [enricher] trafilatura failed for {url}: {e}")

    # --- Fallback 1: Serper /scrape (fast, reliable) ---
    print(f"  [enricher] trafilatura returned nothing for {url}, trying Serper /scrape")
    result = await _fetch_via_serper(url)
    if result:
        print(f"  [enricher] Serper /scrape succeeded for {url}")
        return result

    # --- Fallback 2: Jina Reader (deep content coverage, slower) ---
    print(f"  [enricher] Serper returned nothing for {url}, trying Jina fallback")
    result = await _fetch_via_jina(url)
    if result:
        print(f"  [enricher] Jina fallback succeeded for {url}")
    return result


# ---------------------------------------------------------------------------
# Judge Evaluation
# ---------------------------------------------------------------------------


def _load_judge_prompt() -> str:
    """Load the enrichment judge prompt from the prompts directory."""
    prompt_path = PROMPTS_DIR / "enrichment_judge_prompt.md"
    raw_md = prompt_path.read_text(encoding="utf-8")
    return extract_prompt_from_md(raw_md)


async def evaluate_content(
    client,
    headline: str,
    raw_content: str,
    extracts: list[dict],
    is_model_release: bool,
    is_deal: bool = False,
) -> tuple[dict, dict]:
    """Ask the Haiku judge whether content is sufficient.

    Returns (judge_result_dict, usage_dict).
    """
    system_prompt = _load_judge_prompt()

    # Build the user message with all available content
    extracts_text = ""
    if extracts:
        for i, ext in enumerate(extracts, 1):
            extracts_text += f"\n--- Supplementary Extract {i} (from {ext.get('url', 'unknown')}) ---\n"
            extracts_text += ext.get("extract", "")[:3000] + "\n"

    today = get_today_date()

    user_message = f"""Today's date: {today}
headline: {headline}
raw_content: {raw_content}
supplementary_extracts: {extracts_text if extracts_text else "(none yet)"}
is_model_release: {is_model_release}
is_deal: {is_deal}"""

    try:
        response = await _anthropic_messages_create_with_retry(
            client,
            "Enrichment judge",
            model=CONTENT_FILTER_MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        result_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                result_text = block.text

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        if not result_text:
            return _default_judge_result("Judge returned no text response"), usage

        judge_result = _normalise_judge_result(
            _parse_judge_json(result_text),
            "Judge response was missing required fields",
        )
        judge_result = _enforce_minimum_substance(
            headline,
            raw_content,
            extracts,
            judge_result,
            is_model_release,
        )
        return judge_result, usage
    except Exception as e:
        print(f"  [enricher] Enrichment judge failed: {e}")
        return _default_judge_result(f"Judge request failed: {e}"), {
            "input_tokens": 0,
            "output_tokens": 0,
        }


# ---------------------------------------------------------------------------
# Step 2: Serper Web Search + Fetch
# ---------------------------------------------------------------------------


def build_search_query(
    headline: str,
    missing: list[str],
    entities: list[str],
    recommended_terms: list[str],
) -> str:
    """Build a targeted search query from available context.

    Strategy: headline for topic anchoring + judge's recommended search
    terms (designed for search engines) + key entities for specificity.
    Missing elements are editorial descriptions and are NOT included —
    they dilute query precision (e.g. "Nature and scale of attacks").
    """
    parts = [headline]

    # Judge's recommended search terms — primary refinement
    for term in recommended_terms[:4]:
        if term:
            parts.append(str(term).strip())

    # Key entities for specificity
    if entities:
        clean_entities = [e.replace("**", "").strip() for e in entities[:2] if e]
        parts.extend(clean_entities)

    deduped_parts = []
    seen = set()
    for part in parts:
        cleaned = " ".join(part.split())
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            deduped_parts.append(cleaned)

    query = " ".join(deduped_parts)
    # Cap at 200 chars
    if len(query) > 200:
        query = query[:200].rsplit(" ", 1)[0]
    return query


def build_model_release_queries(
    headline: str,
    entities: list[str] | None = None,
) -> list[dict[str, str]]:
    """Supplementary search queries for model release enrichment.

    These run in parallel with the judge-recommended query to ensure we
    fetch benchmark data, model cards, and availability information that
    the ghostwriter needs for structured model release cards.
    """
    return build_model_release_queries_impl(headline, entities=entities)


async def serper_search_with_retry(query: str, max_attempts: int = 3) -> list[dict]:
    """Search via Serper API with exponential backoff retry.

    Returns list of {title, link, snippet} dicts.
    """
    if not SERPER_API_KEY:
        print("  [enricher] SERPER_API_KEY not set — skipping web search")
        return []

    delays = [1, 2, 4]
    last_error = None

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=SERPER_TIMEOUT) as http:
                resp = await http.post(
                    "https://google.serper.dev/search",
                    json={"q": query, "num": 6},
                    headers={"X-API-KEY": SERPER_API_KEY},
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("organic", [])
            # Domain dedup — one result per domain
            seen_domains = set()
            deduped = []
            for r in results:
                domain = _extract_domain(r.get("link", ""))
                if domain and domain not in seen_domains:
                    seen_domains.add(domain)
                    deduped.append({
                        "title": r.get("title", ""),
                        "link": r.get("link", ""),
                        "snippet": r.get("snippet", ""),
                    })
                if len(deduped) >= 3:
                    break

            return deduped

        except Exception as e:
            last_error = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delays[attempt])

    print(f"  [enricher] Serper search failed after {max_attempts} attempts: {last_error}")
    return []


async def _fetch_single_url(url: str, step_label: str, include_tables: bool = False) -> dict | None:
    """Fetch a single URL via trafilatura, return enrichment dict or None."""
    result = await fetch_source_url(url, include_tables=include_tables)
    if result:
        result["source_step"] = step_label
    return result


async def search_and_fetch(
    headline: str,
    missing: list[str],
    entities: list[str],
    recommended_terms: list[str],
    supplementary_queries: list[str] | list[dict[str, str]] | None = None,
    is_model_release: bool = False,
) -> list[dict]:
    """Run Serper search, then fetch top results via trafilatura in parallel.

    For model releases, supplementary_queries run in parallel with the
    primary judge-recommended query to target benchmark data, model cards,
    and pricing pages. Results are merged with domain dedup.

    Returns list of enrichment source dicts.
    """
    query = build_search_query(headline, missing, entities, recommended_terms)
    print(f"  [enricher] Web search: {query}")

    # Run primary + any supplementary searches in parallel
    search_tasks = [serper_search_with_retry(query)]
    search_intents = ["primary"]
    if supplementary_queries:
        for sq in supplementary_queries:
            if isinstance(sq, dict):
                query_text = str(sq.get("query", "")).strip()
                intent = str(sq.get("intent", "supplementary")).strip() or "supplementary"
            else:
                query_text = str(sq).strip()
                intent = "supplementary"
            if not query_text:
                continue
            print(f"  [enricher] Supplementary search ({intent}): {query_text}")
            search_tasks.append(serper_search_with_retry(query_text))
            search_intents.append(intent)

    all_search_results = await asyncio.gather(*search_tasks)

    all_candidates: list[dict] = []
    for intent, result_list in zip(search_intents, all_search_results):
        if not isinstance(result_list, list):
            continue
        for r in result_list:
            candidate = dict(r)
            candidate["query_intent"] = intent
            candidate["classified_intents"] = list(
                classify_model_release_result(
                    candidate.get("link", ""),
                    candidate.get("title", ""),
                    candidate.get("snippet", ""),
                )
            )
            all_candidates.append(candidate)

    if is_model_release:
        merged = reserve_model_release_search_results(all_candidates, max_total=7)
    else:
        seen_domains: set[str] = set()
        merged = []
        for candidate in all_candidates:
            domain = _extract_domain(candidate.get("link", ""))
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                merged.append(candidate)
            if len(merged) >= 5:
                break

    if not merged:
        return []

    # Fetch top results in parallel
    tasks = [
        _fetch_single_url(r["link"], "web_search", include_tables=is_model_release)
        for r in merged
    ]
    fetched = await asyncio.gather(*tasks, return_exceptions=True)

    extracts = []
    for i, result in enumerate(fetched):
        if isinstance(result, dict) and result is not None:
            # Add title from search results
            result["title"] = merged[i].get("title", "")
            extracts.append(result)

    return extracts


async def _maybe_normalise_model_release_packet_with_llm(
    client,
    headline: str,
    item: dict,
) -> None:
    """Last-mile normalisation for benchmark facts when regex extraction finds nothing."""
    packet = build_model_release_packet(item)
    if packet.get("benchmark_facts"):
        return

    snippets: list[str] = []
    for source in item.get("enriched_sources", []) or []:
        extract = _normalise_raw_content(source.get("extract", ""))
        if re.search(r"benchmark|eval|swe-bench|osworld|mmlu|gpqa|humaneval|gdpval", extract, re.IGNORECASE):
            snippets.append(extract[:2000])
    raw_content = _normalise_raw_content(item.get("raw_content", ""))
    if re.search(r"benchmark|eval|swe-bench|osworld|mmlu|gpqa|humaneval|gdpval", raw_content, re.IGNORECASE):
        snippets.append(raw_content[:2000])

    if not snippets:
        return

    prompt = f"""Normalize benchmark and key-number facts for this model release.

Headline: {headline}

Return JSON only:
{{
  "benchmark_facts": [
    {{"benchmark": "name", "model": "model name", "score": "54.38%", "source_url": "url or empty string"}}
  ],
  "key_number_facts": [
    {{"label": "Pricing (mini)", "value": "$0.75/$4.50", "qualifier": "per 1M in/out tokens", "source_url": "url or empty string", "kind": "pricing"}}
  ],
  "coverage_notes": ["brief note"]
}}

Use only the evidence below. Omit any field you cannot support.

Evidence:
{chr(10).join(snippets[:4])}
"""

    try:
        response = await _anthropic_messages_create_with_retry(
            client,
            "Model release packet normalizer",
            model=CONTENT_FILTER_MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  [enricher] Model release packet normalizer failed: {e}")
        return

    result_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            result_text = block.text
    if not result_text:
        return

    parsed = _parse_judge_json(result_text)
    benchmark_facts = parsed.get("benchmark_facts")
    if isinstance(benchmark_facts, list):
        existing = item.get("benchmark_facts", []) or []
        item["benchmark_facts"] = existing + [fact for fact in benchmark_facts if isinstance(fact, dict)]
    key_number_facts = parsed.get("key_number_facts")
    if isinstance(key_number_facts, list):
        existing = item.get("key_number_facts", []) or []
        item["key_number_facts"] = existing + [fact for fact in key_number_facts if isinstance(fact, dict)]
    coverage_notes = parsed.get("coverage_notes")
    if isinstance(coverage_notes, list):
        existing = item.get("coverage_notes", []) or []
        item["coverage_notes"] = existing + [str(note) for note in coverage_notes if note]


# ---------------------------------------------------------------------------
# Step 3: Sonnet Research Agent
# ---------------------------------------------------------------------------


async def research_agent(
    client,
    headline: str,
    raw_content: str,
    extracts: list[dict],
    missing: list[str],
) -> tuple[dict | None, dict]:
    """Use Sonnet with web_search tool to research the topic.

    Returns (enriched_facts_dict, usage_dict).
    """
    extracts_summary = ""
    if extracts:
        for ext in extracts[:3]:
            extracts_summary += f"\n- {ext.get('url', '')}: {ext.get('extract', '')[:500]}\n"

    missing_str = ", ".join(missing) if missing else "general context and details"

    user_message = f"""Research this news item thoroughly. I need specific facts and details.

Headline: {headline}

What we already know:
{raw_content}
{extracts_summary}

What we still need: {missing_str}

Find authoritative sources and provide:
1. A factual summary (200-400 words) of what happened
2. Key facts with their sources
3. Any open questions or unverified claims

Return your findings as JSON:
{{
  "summary": "200-400 word factual summary",
  "key_facts": [
    {{"fact": "specific factual finding", "source": "url where you found it"}}
  ],
  "open_questions": ["things you couldn't verify"]
}}"""

    try:
        response = await _anthropic_messages_create_with_retry(
            client,
            "Enrichment research agent",
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                }
            ],
        )

        # Extract the final text block from the response
        result_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                result_text = block.text

        # Calculate total usage including tool use turns
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        if not result_text:
            return None, usage

        facts = _parse_judge_json(result_text)  # Same JSON parsing logic
        # Validate structure
        if "summary" not in facts:
            return None, usage

        return facts, usage

    except Exception as e:
        print(f"  [enricher] Research agent failed: {e}")
        return None, {"input_tokens": 0, "output_tokens": 0}


# ---------------------------------------------------------------------------
# Main Enrichment Chain
# ---------------------------------------------------------------------------


async def enrich_item(item: dict, client) -> dict:
    """Run the progressive enrichment chain on a single item.

    Modifies item in-place, adding:
      - enriched_sources: list of supplementary extracts
      - enriched_facts: research agent findings (if used)
      - _enrichment: metadata about the enrichment process
    """
    start_time = time.time()

    # Normalize raw_content
    raw_content = _normalise_raw_content(item.get("raw_content", ""))
    original_word_count = len(raw_content.split())

    headline = item.get("headline", "")
    source_url = item.get("source_url", "")
    entities = item.get("entities", [])
    is_model_release = _set_model_release_flag(item, is_possible_model_release(item))
    is_deal = is_probable_deal(item)

    enriched_sources: list[dict] = []
    enriched_facts: dict | None = None
    item["enriched_sources"] = enriched_sources
    steps_taken: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0
    final_source = "none"
    judge_1_result = None
    judge_2_result = None

    print(f"  [enricher] Enriching: {headline[:80]}... ({original_word_count} words)")

    def _model_release_is_complete(search_exhausted: bool = False) -> tuple[bool, dict]:
        attach_model_release_packet(item, search_exhausted=search_exhausted)
        packet = build_model_release_packet(item)
        completeness = summarise_model_release_completeness(
            packet,
            search_exhausted=search_exhausted,
        )
        item["coverage_notes"] = completeness["coverage_notes"]
        if isinstance(item.get("_enrichment"), dict):
            item["_enrichment"]["benchmark_families_found"] = completeness["benchmark_families_found"]
            item["_enrichment"]["official_source_found"] = completeness["official_source_found"]
            item["_enrichment"]["pricing_found"] = completeness["pricing_found"]
            item["_enrichment"]["availability_found"] = completeness["availability_found"]
            item["_enrichment"]["dual_model_release"] = completeness["dual_model_release"]
        return completeness["complete"], completeness

    # ── Step 1: Fetch source URL ──────────────────────────────────────────
    steps_taken.append("url_fetch")
    source_extract = await fetch_source_url(source_url, include_tables=is_model_release)
    if source_extract:
        enriched_sources.append(source_extract)
        final_source = "url_fetch"
        print(f"  [enricher] Source URL fetched: {len(source_extract['extract'].split())} words")

    # ── Judge 1 ───────────────────────────────────────────────────────────
    steps_taken.append("judge_1")
    judge1, usage1 = await evaluate_content(
        client, headline, raw_content, enriched_sources, is_model_release,
        is_deal=is_deal,
    )
    judge_1_result = judge1
    total_input_tokens += usage1["input_tokens"]
    total_output_tokens += usage1["output_tokens"]

    should_continue_after_judge1 = judge1.get("decision") != "SUFFICIENT"
    if judge1.get("decision") == "SUFFICIENT":
        print(f"  [enricher] Judge 1: SUFFICIENT (confidence: {judge1.get('confidence', '?')})")
        if is_model_release:
            complete, completeness = _model_release_is_complete(search_exhausted=False)
            if not complete:
                should_continue_after_judge1 = True
                print(
                    "  [enricher] Judge 1 sufficient but model-release packet incomplete — "
                    f"continuing ({', '.join(completeness['missing'])})"
                )
    else:
        print(f"  [enricher] Judge 1: INSUFFICIENT — {judge1.get('reasoning', '')}")

    if should_continue_after_judge1:
        # ── Step 2: Web search ────────────────────────────────────────────
        steps_taken.append("web_search")
        supplementary = None
        if is_model_release:
            supplementary = build_model_release_queries(headline, entities=entities)
        elif is_deal:
            supplementary = _build_deal_queries(headline, entities)
        search_extracts = await search_and_fetch(
            headline,
            judge1.get("missing_elements", []),
            entities,
            judge1.get("recommended_query_terms", []),
            supplementary_queries=supplementary,
            is_model_release=is_model_release,
        )
        enriched_sources.extend(search_extracts)

        if search_extracts:
            final_source = "web_search"
            print(f"  [enricher] Web search: {len(search_extracts)} sources fetched")

        # ── Judge 2 ───────────────────────────────────────────────────────
        steps_taken.append("judge_2")
        judge2, usage2 = await evaluate_content(
            client, headline, raw_content, enriched_sources, is_model_release,
            is_deal=is_deal,
        )
        judge_2_result = judge2
        total_input_tokens += usage2["input_tokens"]
        total_output_tokens += usage2["output_tokens"]

        should_continue_after_judge2 = judge2.get("decision") != "SUFFICIENT"
        if judge2.get("decision") == "SUFFICIENT":
            print(f"  [enricher] Judge 2: SUFFICIENT (confidence: {judge2.get('confidence', '?')})")
            if is_model_release:
                complete, completeness = _model_release_is_complete(search_exhausted=False)
                if not complete:
                    should_continue_after_judge2 = True
                    print(
                        "  [enricher] Judge 2 sufficient but model-release packet incomplete — "
                        f"running final targeted search ({', '.join(completeness['missing'])})"
                    )
                    steps_taken.append("web_search_final")
                    final_queries = build_model_release_queries(headline, entities=entities)
                    search_extracts = await search_and_fetch(
                        headline,
                        completeness.get("missing", []),
                        entities,
                        judge2.get("recommended_query_terms", []),
                        supplementary_queries=final_queries,
                        is_model_release=True,
                    )
                    if search_extracts:
                        enriched_sources.extend(search_extracts)
                        final_source = "web_search"
                        print(f"  [enricher] Final web search: {len(search_extracts)} sources fetched")
                    complete, completeness = _model_release_is_complete(search_exhausted=True)
                    if not complete:
                        print(
                            "  [enricher] Model-release completeness still limited after final search — "
                            f"{', '.join(completeness['missing'])}"
                        )
                    should_continue_after_judge2 = False
        else:
            print(f"  [enricher] Judge 2: INSUFFICIENT — {judge2.get('reasoning', '')}")

        if should_continue_after_judge2:
            # ── Step 3: Research agent ────────────────────────────────────
            steps_taken.append("research_agent")
            print(f"  [enricher] Escalating to research agent...")
            facts, usage3 = await research_agent(
                client,
                headline,
                raw_content,
                enriched_sources,
                judge2.get("missing_elements", []),
            )
            total_input_tokens += usage3["input_tokens"]
            total_output_tokens += usage3["output_tokens"]

            if facts:
                enriched_facts = facts
                item["enriched_facts"] = enriched_facts
                final_source = "research_agent"
                print(f"  [enricher] Research agent completed: {len(facts.get('key_facts', []))} facts")
            else:
                print(f"  [enricher] Research agent returned no results")

    if is_model_release:
        attach_model_release_packet(item, search_exhausted=True)
        await _maybe_normalise_model_release_packet_with_llm(client, headline, item)
        attach_model_release_packet(item, search_exhausted=True)
    is_model_release = await _finalize_model_release_flag(item, client)

    # ── Attach enrichment data to item ────────────────────────────────────
    elapsed = round(time.time() - start_time, 1)

    # Calculate total enriched word count
    enriched_word_count = original_word_count
    for src in enriched_sources:
        enriched_word_count += len(src.get("extract", "").split())
    if enriched_facts and enriched_facts.get("summary"):
        enriched_word_count += len(enriched_facts["summary"].split())

    item["enriched_sources"] = enriched_sources

    if enriched_facts:
        item["enriched_facts"] = enriched_facts

    item["_enrichment"] = {
        "was_thin": True,
        "original_word_count": original_word_count,
        "steps_taken": steps_taken,
        "final_source": final_source,
        "judge_1_result": judge_1_result,
        "judge_2_result": judge_2_result,
        "enrichment_sources": [s.get("url", "") for s in enriched_sources],
        "enriched_word_count": enriched_word_count,
        "elapsed_seconds": elapsed,
        "tokens": {
            "input": total_input_tokens,
            "output": total_output_tokens,
        },
    }

    if is_model_release:
        attach_model_release_packet(item, search_exhausted=True)

    print(
        f"  [enricher] Done: {headline[:60]}... "
        f"({original_word_count} → {enriched_word_count} words, "
        f"{elapsed}s, final={final_source})"
    )

    return item


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


async def enrich_selected_items(
    items: list[dict], client
) -> tuple[list[dict], dict]:
    """Enrich thin items among the gatekeeper-selected items.

    Args:
        items: List of selected items from the gatekeeper.
        client: anthropic.AsyncAnthropic client instance.

    Returns:
        (items, usage) — items with enrichment data attached, and
        aggregate token usage dict.
    """
    thin_items = []
    already_enriched = 0
    for i, item in enumerate(items):
        if not is_thin(item):
            continue
        if item.get("_enrichment", {}).get("was_thin"):
            already_enriched += 1
            continue
        thin_items.append((i, item))

    if not thin_items:
        for item in items:
            await _finalize_model_release_flag(item, client)
            if item.get("is_model_release"):
                attach_model_release_packet(item, search_exhausted=True)
        if already_enriched:
            print(
                f"  [enricher] No thin items need enrichment "
                f"({already_enriched} already enriched from cache)"
            )
        else:
            print(f"  [enricher] No thin items found ({len(items)} items all >= {THIN_THRESHOLD} words)")
        return items, {"input_tokens": 0, "output_tokens": 0}

    print(
        f"  [enricher] Found {len(thin_items)} thin item(s) out of {len(items)} "
        f"(threshold: {THIN_THRESHOLD} words)"
    )
    if already_enriched:
        print(f"  [enricher] Skipping {already_enriched} item(s) already enriched from cache")

    # Run enrichment with concurrency limit
    semaphore = asyncio.Semaphore(ENRICHMENT_SEMAPHORE_LIMIT)

    async def _enrich_with_semaphore(idx: int, item: dict):
        async with semaphore:
            try:
                enriched = await enrich_item(item, client)
            except Exception as e:
                raw_content = _normalise_raw_content(item.get("raw_content", ""))
                print(f"  [enricher] Unhandled enrichment failure for '{item.get('headline', '')[:80]}': {e}")
                item["enriched_sources"] = item.get("enriched_sources", [])
                item["_enrichment"] = {
                    "was_thin": True,
                    "original_word_count": len(raw_content.split()),
                    "steps_taken": ["error"],
                    "final_source": "none",
                    "judge_1_result": None,
                    "judge_2_result": None,
                    "enrichment_sources": [],
                    "enriched_word_count": len(raw_content.split()),
                    "elapsed_seconds": 0.0,
                    "tokens": {"input": 0, "output": 0},
                    "error": str(e),
                }
                enriched = item

            items[idx] = enriched

    tasks = [
        _enrich_with_semaphore(idx, item) for idx, item in thin_items
    ]
    await asyncio.gather(*tasks)

    for item in items:
        await _finalize_model_release_flag(item, client)
        if item.get("is_model_release"):
            attach_model_release_packet(item, search_exhausted=True)

    # Aggregate token usage
    total_input = 0
    total_output = 0
    for _, item in thin_items:
        enrichment_meta = item.get("_enrichment", {})
        tokens = enrichment_meta.get("tokens", {})
        total_input += tokens.get("input", 0)
        total_output += tokens.get("output", 0)

    usage = {
        "input_tokens": total_input,
        "output_tokens": total_output,
    }

    print(
        f"  [enricher] Enrichment complete: "
        f"{len(thin_items)} items enriched, "
        f"{total_input + total_output} total tokens"
    )

    return items, usage
