"""Regional Research Ecosystem Scout — hybrid Serper + Claude agent.

Two-phase coverage for Gulf academic and research developments within
the pipeline lookback window:

1. **Serper discipline pre-fetch** (deterministic): fan out 6 Google searches
   by research discipline (biotech, robotics, quantum, engineering,
   materials, healthcare AI). Google's index has better long-tail coverage
   of institutional sites (`aurak.ac.ae`, `ku.ac.ae`, etc.) than Claude's
   native `web_search_20250305` tool, which uses the Brave index. The
   2026-04-21 head-to-head on the biotech query found 0 AURAK hits via
   Claude web_search vs 3 AURAK hits via Serper — the index gap is real
   and can't be fixed by prompt tuning.

2. **Claude agentic phase**: pre-fetched candidates are injected into the
   scout prompt; Claude evaluates them, runs a broad AI sweep, does
   entity checks on high-priority watchlist institutions, and follows up
   on interesting threads — all via its native `web_search` tool.

Runs after the 9 deterministic collectors and receives their headlines
as dedup context. Output merges into the standard pipeline item pool
before triage. Non-fatal at every layer: per-discipline Serper failure
→ skip that discipline; whole-Serper-phase failure → fall through to
Claude-only; whole-scout failure → pipeline continues without a
regional-scout contribution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import anthropic
import httpx
from supabase import create_client, Client

from config import MODEL, PROMPTS_DIR, get_lookback_cutoff_date, get_today_date
from pipeline.collector import CollectedArticle

logger = logging.getLogger(__name__)
GST = ZoneInfo("Asia/Dubai")

# Retry settings (mirrors enricher.py pattern)
MAX_ATTEMPTS = 3
RETRY_DELAYS = [1, 2, 4]

# Cost tracking (Sonnet pricing per million tokens)
INPUT_COST_PER_M = 3.0
OUTPUT_COST_PER_M = 15.0
SEARCH_COST_PER_USE = 0.01

# ---------------------------------------------------------------------------
# Serper discipline sweep — Phase 1 of the hybrid flow
# ---------------------------------------------------------------------------

# Queries are templated with the current year at runtime. Six disciplines
# chosen because the 2026-04-21 empirical survey showed each one surfaces
# distinct events the AI-qualified broad sweep misses (e.g. AURAK
# Biotechnology Conference only appears under the biotech query; NYUAD
# Marri Nut only under materials). Expanding this list requires a fresh
# Serper audit — adding queries that return noise bloats the prompt
# without lifting signal.
_DISCIPLINE_QUERIES: list[tuple[str, str]] = [
    ("biotech",       "UAE OR Gulf university biotechnology OR genomics conference {year}"),
    ("robotics",      "UAE OR Gulf university robotics OR autonomous systems research {year}"),
    ("quantum",       "UAE OR Gulf university quantum OR photonics research {year}"),
    ("engineering",   "UAE OR Gulf university engineering OR applied science symposium {year}"),
    ("materials",     "UAE OR Gulf university materials science OR nanotechnology research {year}"),
    ("healthcare_ai", "UAE OR Gulf university healthcare AI OR digital health research {year}"),
]

# Known SEO/aggregator spam domains observed in the 2026-04-21 head-to-head.
# These sites publish "UAE biotechnology conferences 2026" calendar pages
# that look relevant but carry no real news content. Kept small — `tbs=qdr:w`
# already filters most of them out via recency. Claude's evaluation step is
# a second filter for anything that slips through.
_SERPER_SPAM_DOMAINS: frozenset[str] = frozenset({
    "conferenceindex.org",
    "internationalconferencealerts.com",
    "conferencealerts.co.in",
    "magnusconferences.com",
    "academicworldresearch.org",
    "waset.org",
})

_SERPER_SEARCH_URL = "https://google.serper.dev/search"
_SERPER_PER_DISCIPLINE_TOP_N = 5   # inject up to 5 raw hits per discipline
_SERPER_TIMEOUT = 10.0
_SERPER_RETRY_DELAYS = [1.0, 2.0, 4.0]


def _is_serper_enabled() -> bool:
    """Feature flag: default ON; set REGIONAL_SCOUT_SERPER_ENABLED=false to
    fully disable the Serper phase and revert to Claude-only coverage."""
    val = os.getenv("REGIONAL_SCOUT_SERPER_ENABLED", "true").strip().lower()
    return val not in ("false", "0", "no", "")


async def _serper_discipline_sweep(
    client: httpx.AsyncClient,
    discipline: str,
    query: str,
    api_key: str,
) -> tuple[list[dict], str]:
    """One Serper /search for one discipline. Returns (filtered_hits, error_msg).

    Filters out spam domains and caps at `_SERPER_PER_DISCIPLINE_TOP_N`.
    Retries 429s per the established pattern in web_search_verify.py. Detects
    the "Not enough credits" 400 response explicitly.

    Returns `([], reason)` on any failure so one discipline's outage doesn't
    kill the whole Serper phase. `error_msg` is empty on success.
    """
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": 10, "tbs": "qdr:w"}  # last 7 days
    last_err = ""
    for attempt, delay in enumerate([0.0, *_SERPER_RETRY_DELAYS]):
        if delay:
            await asyncio.sleep(delay)
        try:
            resp = await client.post(
                _SERPER_SEARCH_URL,
                json=payload,
                headers=headers,
                timeout=_SERPER_TIMEOUT,
            )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < len(_SERPER_RETRY_DELAYS):
                continue
            logger.warning(
                "regional_scout/Serper[%s]: network failure after %d attempts: %s",
                discipline, attempt + 1, last_err,
            )
            return [], last_err

        if resp.status_code == 429:
            if attempt < len(_SERPER_RETRY_DELAYS):
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        await asyncio.sleep(min(float(retry_after), 8.0))
                    except ValueError:
                        pass
                continue
            last_err = "429 rate limit after retries"
            logger.warning("regional_scout/Serper[%s]: %s", discipline, last_err)
            return [], last_err

        if resp.status_code != 200:
            # "Not enough credits" arrives as HTTP 400 with a specific body;
            # we've been burned by silent degradation before, so log loudly.
            body_preview = resp.text[:200]
            if "Not enough credits" in body_preview:
                last_err = "Serper credits exhausted"
                logger.warning(
                    "regional_scout/Serper[%s]: CREDITS EXHAUSTED — discipline "
                    "sweep disabled for this run. Top up to restore.",
                    discipline,
                )
            else:
                last_err = f"HTTP {resp.status_code}: {body_preview}"
                logger.warning(
                    "regional_scout/Serper[%s]: %s", discipline, last_err,
                )
            return [], last_err

        # 200 OK — parse organic results
        try:
            data = resp.json()
        except ValueError as e:
            last_err = f"JSON decode: {e}"
            logger.warning("regional_scout/Serper[%s]: %s", discipline, last_err)
            return [], last_err
        break
    else:
        return [], last_err or "retry loop exhausted"

    organic = data.get("organic", []) if isinstance(data, dict) else []
    cleaned: list[dict] = []
    for r in organic:
        if not isinstance(r, dict):
            continue
        url = r.get("link", "") or ""
        if not url:
            continue
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        if domain in _SERPER_SPAM_DOMAINS:
            continue
        cleaned.append({
            "discipline": discipline,
            "title": r.get("title", "") or "",
            "url": url,
            "snippet": r.get("snippet", "") or "",
            "date": r.get("date", "") or "",
            "source_name": r.get("source", "") or domain,
            "domain": domain,
        })
        if len(cleaned) >= _SERPER_PER_DISCIPLINE_TOP_N:
            break
    return cleaned, ""


async def _run_discipline_sweeps(
    existing_headlines: list[str],
    year: int,
) -> tuple[list[dict], dict]:
    """Run all 6 discipline sweeps in parallel, dedup, and return survivors.

    Returns `(prefetched, stats)`. `prefetched` is a flat list ready for
    prompt injection and `CollectedArticle` conversion. `stats` is an
    observability dict for the `summary` return.
    """
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    stats = {
        "enabled": _is_serper_enabled(),
        "queries_run": 0,
        "results_raw": 0,
        "after_spam_filter": 0,
        "after_headline_dedup": 0,
        "after_cross_discipline_dedup": 0,
        "per_discipline_counts": {},
        "errors": [],
    }

    if not stats["enabled"]:
        logger.info("regional_scout/Serper: disabled via REGIONAL_SCOUT_SERPER_ENABLED")
        return [], stats
    if not api_key:
        stats["errors"].append("SERPER_API_KEY not set")
        logger.warning("regional_scout/Serper: SERPER_API_KEY missing — skipping phase")
        return [], stats

    queries = [(d, q.replace("{year}", str(year))) for d, q in _DISCIPLINE_QUERIES]
    stats["queries_run"] = len(queries)

    async with httpx.AsyncClient() as http:
        results = await asyncio.gather(
            *[_serper_discipline_sweep(http, d, q, api_key) for d, q in queries],
            return_exceptions=True,
        )

    # Flatten with error capture
    flat: list[dict] = []
    for (discipline, _q), out in zip(queries, results):
        if isinstance(out, Exception):
            stats["errors"].append(f"{discipline}: {type(out).__name__}: {out}")
            continue
        hits, err = out
        if err:
            stats["errors"].append(f"{discipline}: {err}")
        flat.extend(hits)

    stats["results_raw"] = len(flat) + sum(
        1 for r in results if isinstance(r, tuple)  # rough raw count proxy
    )
    stats["after_spam_filter"] = len(flat)  # spam already stripped per-call

    # Dedup by URL across disciplines
    seen_urls: set[str] = set()
    after_url_dedup: list[dict] = []
    for item in flat:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        after_url_dedup.append(item)
    stats["after_cross_discipline_dedup"] = len(after_url_dedup)

    # Dedup against existing headlines (fuzzy, reuse _is_duplicate logic)
    prefetched: list[dict] = []
    for item in after_url_dedup:
        if _is_duplicate(item["title"], existing_headlines):
            continue
        prefetched.append(item)
    stats["after_headline_dedup"] = len(prefetched)

    # Per-discipline counts (of survivors)
    for item in prefetched:
        d = item["discipline"]
        stats["per_discipline_counts"][d] = stats["per_discipline_counts"].get(d, 0) + 1

    logger.info(
        "regional_scout/Serper: %d queries → %d raw → %d after dedup "
        "(errors: %d)",
        stats["queries_run"], len(flat), len(prefetched), len(stats["errors"]),
    )
    return prefetched, stats


def _format_prefetched_candidates(items: list[dict]) -> str:
    """Render Serper discipline survivors as a prompt-injection block."""
    if not items:
        return "(No discipline pre-fetches this run — Serper phase was empty or disabled.)"
    lines = []
    for it in items:
        line = (
            f"- [{it['discipline']}] {it['title']}\n"
            f"    URL: {it['url']}\n"
            f"    Source: {it.get('source_name') or it.get('domain', '')}  "
            f"Date: {it.get('date') or 'unknown'}\n"
            f"    Snippet: {it.get('snippet', '')[:240]}"
        )
        lines.append(line)
    return "\n".join(lines)


def _normalize_serper_hit_to_collected_article(item: dict) -> CollectedArticle:
    """Convert a Serper pre-fetch hit into a CollectedArticle.

    Distinct from `_normalize_to_collected_article` (used for Claude-returned
    candidates) so we can track provenance via `collected_via`.
    """
    return CollectedArticle(
        title=item.get("title", "Untitled"),
        snippet=item.get("snippet", "")[:300],
        url=item.get("url", ""),
        source_name=item.get("source_name") or item.get("domain", "Unknown"),
        collected_via="serper_discipline_sweep",
        raw_text=item.get("snippet", ""),
        published_date=item.get("date", ""),  # Serper's "3 days ago" stays as-is;
                                              # downstream date_verify resolves it
        category="",
        scout_mapping=["regional"],
    )


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Client:
    """Create a Supabase client using the service role key."""
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY"
        )
    return create_client(url, key)


def _load_entity_watchlist(sb: Client) -> list[dict]:
    """Load all enabled entities from scout_entity_watchlist."""
    result = sb.table("scout_entity_watchlist") \
        .select("id, entity_name, aliases, priority, notes") \
        .eq("enabled", True) \
        .order("priority", desc=True) \
        .order("entity_name") \
        .execute()
    return result.data or []


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def _format_entity_watchlist(entities: list[dict]) -> str:
    """Format entity watchlist for injection into the prompt."""
    lines = []
    for ent in entities:
        priority_tag = f"[{ent['priority'].upper()}]"
        aliases = ent.get("aliases") or []
        alias_str = f" (aliases: {', '.join(aliases)})" if aliases else ""
        note_str = f" — {ent['notes']}" if ent.get("notes") else ""
        lines.append(f"- {priority_tag} {ent['entity_name']}{alias_str}{note_str}")
    return "\n".join(lines) if lines else "(No entities configured)"


def _format_existing_headlines(headlines: list[str]) -> str:
    """Format existing headlines for injection into the prompt."""
    if not headlines:
        return "(No stories collected yet)"
    return "\n".join(f"- {h}" for h in headlines[:80])


def _build_prompt(
    entities: list[dict],
    existing_headlines: list[str],
    today: str,
    prefetched_candidates: list[dict] | None = None,
) -> str:
    """Load the prompt template and fill in dynamic sections.

    `prefetched_candidates` is the output of the Serper discipline-sweep
    phase (list of `{discipline, title, url, snippet, date, source_name}`).
    Rendered into the `{prefetched_candidates}` placeholder in the template.
    When None or empty, the template shows an explicit "no pre-fetch" note.
    """
    prompt_path = PROMPTS_DIR / "regional_scout_prompt.md"
    template = prompt_path.read_text(encoding="utf-8")
    lookback_cutoff = get_lookback_cutoff_date()
    lookback_date = lookback_cutoff.strftime("%Y-%m-%d")
    lookback_cutoff_label = lookback_cutoff.strftime("%Y-%m-%d %H:%M GST")

    return template.replace("{entity_watchlist}", _format_entity_watchlist(entities)) \
        .replace("{existing_headlines}", _format_existing_headlines(existing_headlines)) \
        .replace("{today_date}", today) \
        .replace("{lookback_date}", lookback_date) \
        .replace("{lookback_cutoff}", lookback_cutoff_label) \
        .replace("{prefetched_candidates}",
                 _format_prefetched_candidates(prefetched_candidates or []))


# ---------------------------------------------------------------------------
# API call with retry
# ---------------------------------------------------------------------------

async def _call_with_retry(client: anthropic.AsyncAnthropic, **kwargs):
    """Call Anthropic with bounded retries for transient failures."""
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await client.messages.create(**kwargs)
        except Exception as e:
            last_error = e
            if attempt < MAX_ATTEMPTS - 1:
                wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                print(
                    f"  [regional_scout] API call failed "
                    f"(attempt {attempt + 1}/{MAX_ATTEMPTS}): {e}. "
                    f"Retrying in {wait}s"
                )
                await asyncio.sleep(wait)
    raise RuntimeError(
        f"Regional scout API call failed after {MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array from the response text."""
    # Try code fences first
    fence_match = re.search(
        r"```(?:json)?\s*\n?(\[.*?\])\s*\n?```", text, re.DOTALL
    )
    if fence_match:
        return json.loads(fence_match.group(1))

    # Try raw JSON array
    arr_match = re.search(r"(\[.*\])", text, re.DOTALL)
    if arr_match:
        return json.loads(arr_match.group(1))

    raise ValueError("No JSON array found in response")


def _count_web_searches(response) -> int:
    """Count how many web_search tool uses occurred in the response."""
    count = 0
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "web_search":
            count += 1
    # Also check server_tool_use blocks for web_search
    for block in response.content:
        if getattr(block, "type", None) == "server_tool_use":
            count += 1
    return count


# ---------------------------------------------------------------------------
# Dedup and normalization
# ---------------------------------------------------------------------------

def _is_duplicate(title: str, existing: list[str], threshold: float = 0.85) -> bool:
    """Check if a title is too similar to any existing headline."""
    title_lower = title.lower().strip()
    for existing_title in existing:
        ratio = SequenceMatcher(None, title_lower, existing_title.lower().strip()).ratio()
        if ratio >= threshold:
            return True
    return False


def _normalize_to_collected_article(candidate: dict) -> CollectedArticle:
    """Convert a scout candidate dict into a CollectedArticle."""
    return CollectedArticle(
        title=candidate.get("title", "Untitled"),
        snippet=candidate.get("summary", "")[:300],
        url=candidate.get("url", ""),
        source_name=candidate.get("source_name", "Unknown"),
        collected_via="claude_web_search",
        raw_text=candidate.get("summary", ""),
        published_date=candidate.get("published_date", ""),
        category="",
        scout_mapping=["regional"],
    )


# ---------------------------------------------------------------------------
# Entity hit tracking
# ---------------------------------------------------------------------------

def _update_entity_hit_dates(
    sb: Client,
    entities: list[dict],
    candidates: list[dict],
    today: str,
) -> None:
    """Update last_hit_date for entities mentioned in candidates."""
    # Build a set of all mentioned entity names (case-insensitive)
    mentioned = set()
    for c in candidates:
        for name in c.get("entities_mentioned", []):
            mentioned.add(name.lower().strip())

    # Match against watchlist (by name or alias)
    for ent in entities:
        ent_names = {ent["entity_name"].lower()}
        for alias in ent.get("aliases") or []:
            ent_names.add(alias.lower())
        if mentioned & ent_names:
            try:
                sb.table("scout_entity_watchlist") \
                    .update({"last_hit_date": today}) \
                    .eq("id", ent["id"]) \
                    .execute()
            except Exception as e:
                logger.warning(f"Failed to update hit date for {ent['entity_name']}: {e}")


# ---------------------------------------------------------------------------
# Run logging
# ---------------------------------------------------------------------------

def _log_run(
    sb: Client,
    today: str,
    model: str,
    search_count: int,
    candidates_returned: int,
    input_tokens: int,
    output_tokens: int,
    duration_seconds: float,
    raw_output: list[dict] | None,
) -> None:
    """Insert a row into scout_run_log."""
    input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_M
    output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_M
    search_cost = search_count * SEARCH_COST_PER_USE
    total_cost = input_cost + output_cost + search_cost

    row = {
        "run_date": today,
        "model": model,
        "search_count": search_count,
        "candidates_returned": candidates_returned,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(total_cost, 4),
        "duration_seconds": round(duration_seconds, 1),
        "raw_output": raw_output,
    }
    try:
        sb.table("scout_run_log").insert(row).execute()
    except Exception as e:
        logger.warning(f"Failed to log scout run: {e}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_regional_scout(
    client: anthropic.AsyncAnthropic,
    existing_headlines: list[str],
) -> tuple[list[CollectedArticle], dict]:
    """Run the regional research scout and return collected articles.

    Args:
        client: Shared Anthropic async client from the orchestrator.
        existing_headlines: Headlines already collected by other scouts,
            used to avoid duplicate coverage.

    Returns:
        Tuple of (list of CollectedArticle, summary dict with token counts).
    """
    today = get_today_date()
    start_time = time.time()
    empty_summary = {"input_tokens": 0, "output_tokens": 0}

    # --- Load entity watchlist ---
    try:
        sb = _get_supabase_client()
        entities = _load_entity_watchlist(sb)
    except Exception as e:
        logger.warning(f"Regional scout: failed to load watchlist: {e}")
        print(f"  [regional_scout] Failed to load watchlist: {e}")
        return [], empty_summary

    if not entities:
        print("  [regional_scout] No entities in watchlist — skipping")
        return [], empty_summary

    print(f"  [regional_scout] Loaded {len(entities)} entities "
          f"({sum(1 for e in entities if e['priority'] == 'high')} high-priority)")

    # --- PHASE 1: Serper discipline pre-fetch (hybrid flow) ---
    # Determines long-tail institutional coverage (AURAK etc.) that Claude's
    # native web_search misses due to Brave-index gaps. Fail-open at every
    # layer: discipline errors shrink the pool; whole-phase errors → Claude
    # runs solo.
    prefetched: list[dict] = []
    serper_stats: dict = {"enabled": False, "errors": ["phase_not_run"]}
    try:
        year = int(today[:4]) if today and len(today) >= 4 else 2026
        prefetched, serper_stats = await _run_discipline_sweeps(
            existing_headlines, year,
        )
        if prefetched:
            print(
                f"  [regional_scout] Serper pre-fetched {len(prefetched)} "
                f"candidates across "
                f"{len(serper_stats.get('per_discipline_counts', {}))} disciplines"
            )
        elif serper_stats.get("enabled"):
            print("  [regional_scout] Serper pre-fetch returned 0 candidates")
    except Exception as e:
        logger.warning(f"regional_scout: Serper phase failed (non-fatal): {e}")
        print(f"  [regional_scout] Serper phase failed (non-fatal): {e}")
        serper_stats["errors"] = [f"phase_exception: {type(e).__name__}: {e}"]

    # --- PHASE 2: Build prompt and call Claude with web_search ---
    system_prompt = _build_prompt(entities, existing_headlines, today, prefetched)
    lookback_cutoff = get_lookback_cutoff_date().strftime("%Y-%m-%d %H:%M GST")
    user_message = (
        f"Find noteworthy Gulf academic and research developments from the "
        f"pipeline lookback window since {lookback_cutoff} for the intelligence "
        f"brief dated {today}. Evaluate the pre-fetched discipline candidates "
        f"above, then use web_search for broad AI sweeps and entity checks to "
        f"fill gaps. Return your findings as a JSON array."
    )

    # max_uses for web_search reduced from 20 → 10 because the discipline
    # sweeps are now handled deterministically by Serper. Claude only needs
    # tool budget for the broad AI sweep, entity checks, and follow-ups.
    # max_tokens stays at 8192 — ample for the ~30-candidate pre-fetch
    # context plus Claude's JSON output.
    try:
        response = await _call_with_retry(
            client,
            model=MODEL,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 10,
                }
            ],
        )
    except Exception as e:
        logger.error(f"Regional scout API call failed: {e}")
        print(f"  [regional_scout] API call failed: {e}")
        # Even if Claude fails, we can salvage the Serper pre-fetch as a
        # minimal scout contribution — better than zero regional coverage.
        if prefetched:
            salvage = [_normalize_serper_hit_to_collected_article(p) for p in prefetched]
            print(
                f"  [regional_scout] Salvaging {len(salvage)} Serper pre-fetches "
                f"as scout output (Claude failed)"
            )
            return salvage, {**empty_summary, "serper": serper_stats}
        return [], {**empty_summary, "serper": serper_stats}

    # --- Extract usage ---
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    search_count = _count_web_searches(response)
    duration = time.time() - start_time

    # Attach Serper stats to the returned summary for observability.
    usage["serper"] = serper_stats

    # --- Parse response ---
    result_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            result_text = block.text  # Take the last text block

    if not result_text:
        logger.warning("Regional scout: no text in response")
        _log_run(sb, today, MODEL, search_count, 0,
                 usage["input_tokens"], usage["output_tokens"], duration, None)
        # Salvage Serper pre-fetches rather than return zero coverage
        salvage = [_normalize_serper_hit_to_collected_article(p) for p in prefetched]
        return salvage, usage

    try:
        candidates = _extract_json_array(result_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Regional scout: failed to parse JSON: {e}")
        logger.debug(f"Response preview: {result_text[:500]}")
        _log_run(sb, today, MODEL, search_count, 0,
                 usage["input_tokens"], usage["output_tokens"], duration,
                 [{"error": str(e), "raw_text": result_text[:2000]}])
        salvage = [_normalize_serper_hit_to_collected_article(p) for p in prefetched]
        return salvage, usage

    if not isinstance(candidates, list):
        candidates = []

    print(f"  [regional_scout] {len(candidates)} raw candidates, "
          f"{search_count} web searches, "
          f"tokens: {usage['input_tokens']}in/{usage['output_tokens']}out, "
          f"{duration:.1f}s")

    # --- Dedup against existing headlines ---
    deduped = []
    for c in candidates:
        title = c.get("title", "")
        if not title:
            continue
        if _is_duplicate(title, existing_headlines):
            print(f"  [regional_scout] Skipping duplicate: {title[:60]}")
            continue
        deduped.append(c)

    # --- Normalize Claude candidates to CollectedArticle ---
    # Claude's evaluation step IS the filter — it sees the Serper pre-fetches
    # in its prompt and picks the ones worth including. Do NOT re-add Serper
    # survivors Claude rejected: in practice those are Instagram reels, job
    # postings, and event-calendar noise that would flood the downstream
    # pipeline. The `salvage` path above still rescues Serper items when
    # Claude itself fails (API error or JSON parse error).
    articles = [_normalize_to_collected_article(c) for c in deduped]

    # --- Update entity hit dates ---
    try:
        _update_entity_hit_dates(sb, entities, deduped, today)
    except Exception as e:
        logger.warning(f"Regional scout: failed to update hit dates: {e}")

    # --- Log the run ---
    _log_run(
        sb, today, MODEL, search_count, len(articles),
        usage["input_tokens"], usage["output_tokens"], duration,
        candidates,
    )

    print(f"  [regional_scout] Returning {len(articles)} candidates "
          f"({len(candidates) - len(deduped)} Claude duplicates removed)")

    return articles, usage
