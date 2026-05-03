from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import re
import time
from datetime import datetime, date, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import anthropic

from config import (
    OUTPUT_DIR, REQUIRED_SCOUTS, MODEL, CONTENT_FILTER_MODEL, SCRAPER_GRACE_HOURS,
    SYNTHESIS_ENABLED, ENTITY_CLASSIFIER_ENABLED, HISTORY_DEDUP_ENABLED,
    get_today_date, get_lookback_cutoff_date, get_previous_brief_headlines,
    get_recent_history_headlines,
)

# Lightweight model for lower-stakes pipeline tasks (drop ghostwriting, EiC selection)
HAIKU_MODEL = CONTENT_FILTER_MODEL
from prompts.loader import load_prompt
from pipeline.collector import NEWSLETTER_SENDERS, run_all_collectors, split_all_newsletters
from pipeline.content_filter import run_content_filter
from pipeline.dedup import deduplicate_items
from pipeline.event_tuples import extract_event_tuples
from pipeline.gatekeeper import run_gatekeeper, run_chunked_gatekeeper
from pipeline.history_dedup import (
    apply_history_dedup_verdicts,
    merge_history_dedup_verdicts,
    run_history_dedup,
    run_tuple_aware_history_dedup,
)
from pipeline.synthesis import (
    run_synthesis,
    apply_synthesis_annotations,
    clear_synthesis_annotations,
)
from pipeline.ghostwriter import run_ghostwriter
from pipeline.card_batch import (
    run_card_batch,
    route_and_run_card_agents,
    run_chunked_card_batches,
)
from pipeline.section_classifier import (
    SECTIONS as CANONICAL_SECTIONS,
    classify_candidate_sections,
)
from pipeline.gk_rekeyer import rekey_gatekeeper_output
from pipeline.entity_classifier import (
    run_entity_classifier,
    apply_entity_classifications,
    build_classifier_input_items,
)
from pipeline.editor import run_editor
from pipeline.date_verify import verify_dates
from pipeline.web_search_verify import verify_dates_via_search
from pipeline.enricher import fetch_source_url, fill_thin_wam_bodies, is_thin, THIN_THRESHOLD
from pipeline.json_utils import safe_parse_json
from pipeline.enricher import enrich_selected_items
from pipeline.model_release import validate_model_release_output
from pipeline.scouts.regional_research_scout import run_regional_scout
from pipeline.manual_entries import (
    fetch_pending_manual_entries,
    convert_to_gatekeeper_shape,
    mark_entries_ingested,
    expire_old_entries,
)

logger = logging.getLogger(__name__)
GST = ZoneInfo("Asia/Dubai")

# Sentinel for items missing publication date evidence
NO_DATE_EVIDENCE = "NO DATE FOUND IN SOURCE"

# The 5 canonical brief sections (in display order)
BRIEF_SECTIONS = [
    "UAE",
    "Regional Research & Academic Events",
    "International Politics & Policy",
    "International Business & Technology",
    "Model Releases & Technical Developments",
]

# Accept legacy section labels from older prompts/outputs and normalize to
# canonical BRIEF_SECTIONS before assembly.
SECTION_NAME_MAP = {
    "uae": "UAE",
    "regional research & academic events": "Regional Research & Academic Events",
    "regional research ecosystem": "Regional Research & Academic Events",
    "regional research and academic events": "Regional Research & Academic Events",
    "regional research and academic ecosystem": "Regional Research & Academic Events",
    "international politics & policy": "International Politics & Policy",
    "international business & technology": "International Business & Technology",
    "international business and technology": "International Business & Technology",
    "model releases & technical developments": "Model Releases & Technical Developments",
    "model releases and technical developments": "Model Releases & Technical Developments",
}

# Cost rates for claude-sonnet-4-6 (per million tokens)
INPUT_COST_PER_M = 3.0
OUTPUT_COST_PER_M = 15.0


# Ghostwriter reliability settings
MAX_GHOSTWRITER_MISSING_ID_RETRIES = 2

# Continuity scoring — items overlapping with yesterday's brief are penalized
# so fresh stories get priority. Penalized items can still be selected if
# they're important enough, but they must beat fresh stories by a wider margin.
CONTINUITY_PENALTY = 1.5

# Fields to send to the Gatekeeper (raw_content and additional_context are stripped
# to save ~50% of input tokens, then rejoined onto selected items afterward).
GATEKEEPER_KEEP_FIELDS = {
    "_idx",  # stable index for rejoining drops to original items
    "headline", "source", "source_url", "date", "date_evidence",
    "summary", "entities", "category", "significance",
    "also_covered_by", "source_scout", "_date_flag", "_verified_date",
    "uae_exposure", "_merged_from_scouts", "_previous_brief_overlap",
    # Phase 2 — Synthesis annotations that tell the Gatekeeper which items
    # belong to the same event cluster, the cluster's continuity status vs
    # prior briefs, and the significance tier. The Gatekeeper prompt has
    # explicit rules for how to use these fields.
    "cluster_id", "cluster_event_key", "cluster_composite_headline",
    "cluster_continuity", "cluster_continuity_reference",
    "cluster_significance_tier", "facet",
    # Phase 2 (curation rewrite) — pre-Gatekeeper section classifier
    # assigns this so Gatekeeper can enforce per-section quotas.
    "brief_section",
}

# Batch sizes for the content filter. The 14-day audit of the prior
# (40-50) batch size surfaced attention-dilution symptoms — same-pattern
# items getting opposite verdicts across batches (e.g. "Crown Prince meets
# Brookfield CEO" passed while "Khaled bin Mohamed bin Zayed meets CEO of
# Nubank" failed). Halving the batch size sharpens per-item attention at
# trivial extra API cost (Haiku is cheap; rate limits are per-minute, not
# per-call). Revisit if drop-rate or latency shift materially.
CONTENT_FILTER_MIN_BATCH_SIZE = 20
CONTENT_FILTER_MAX_BATCH_SIZE = 25
CONTENT_FILTER_TARGET_BATCH_SIZE = 22

# Sources that bypass the NEWS/NOT_NEWS content filter entirely. Use sparingly:
# only for tightly pre-filtered, hand-picked low-volume feeds whose value is the
# *fact of posting* as much as the content. These items still compete for slots
# at the Gatekeeper, which is the discerning gate — we just don't want Haiku
# classifying e.g. a principal's disclosed meeting as "executive characterization"
# and dropping it pre-gatekeeper. See backend/pipeline/collector.py for how each
# of these sources is shaped before collection (English-only, no RTs/replies, etc.).
CONTENT_FILTER_BYPASS_SOURCES = {
    "X / @hhtbzayed",  # Sheikh Tahnoon bin Zayed — UAE NSA, chair of ADQ/IHC
}


def _is_content_filter_bypass(item: dict) -> bool:
    """Return True if the item's source is on the content-filter bypass list."""
    name = (item.get("source") or item.get("source_name") or "").strip()
    return name in CONTENT_FILTER_BYPASS_SOURCES


# Sources whose items skip the date_verify HTTP enrichment stage entirely.
# A source belongs here when the collector already stamps an authoritative
# publication date AND one of the following holds:
#   (a) empirical live testing confirms date_verify fetches fail
#       systematically on the article URLs (bot-blocked CDN, SPA-rendered
#       HTML, non-200 status), so the HTTP latency is pure waste, OR
#   (b) date_verify succeeds on the article URLs but returns the WRONG
#       date — worse than useless — because of page-structure quirks the
#       generic extractor mishandles (sidebar <time> elements, non-ISO
#       JSON-LD, etc.).
#
# WAM: sitemap XML <news:publication_date> is authoritative (see collect_wam
# in collector.py). Live test on 40 WAM URLs: 0/40 verified (100% bot-blocked
# / no parseable meta tags). Case (a). Saves ~30-60s of wall-clock per run.
#
# TII: listing-page <time> (matches article JSON-LD datePublished) is
# authoritative. Live test found date_verify returns a WRONG date on every
# TII URL: articles have no article:published_time meta tag, their JSON-LD
# datePublished uses human-readable "31 Mar 2026" which _parse_date_string
# requires ISO for, so extraction falls through to _extract_date_from_time_tag
# — which picks the first <time> on the page, which is a sidebar "recent
# articles" widget, not the article's publication time. Case (b): silently
# poisons TII items with unrelated dates, risking date-filter false-drops.
# Bypassing here keeps the collector's correct listing date intact.
#
# Before adding a source, confirm the bypass is correct: the collector date
# must genuinely be authoritative for that source. Sources whose collector
# scrapes dates from arbitrary HTML regex (e.g. G42, Presight) should NOT
# be added — verify_dates is the backstop for them.
VERIFY_DATES_BYPASS_SOURCES = {
    "WAM",
    "TII",
}


def _skips_date_verify(item: dict) -> bool:
    """Return True if the item's source is on the date-verify bypass list."""
    name = (item.get("source") or item.get("source_name") or "").strip()
    return name in VERIFY_DATES_BYPASS_SOURCES


NEWSLETTER_SOURCE_NAMES = {
    str(sender.get("source_name") or "").strip()
    for sender in NEWSLETTER_SENDERS
    if sender.get("source_name")
}

def timestamp() -> str:
    """Return current timestamp formatted for console output."""
    return datetime.now(GST).strftime("[%H:%M:%S]")


def current_gst_timestamp() -> str:
    """Return the current timestamp in GST as an ISO 8601 string."""
    return datetime.now(GST).isoformat(timespec="seconds")


def estimate_cost_usd(total_input: int, total_output: int) -> float:
    """Estimate total USD cost from token usage."""
    input_cost = (total_input / 1_000_000) * INPUT_COST_PER_M
    output_cost = (total_output / 1_000_000) * OUTPUT_COST_PER_M
    return input_cost + output_cost


def save_intermediate(filename: str, data) -> Path:
    """Save intermediate pipeline results for debugging."""
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return output_path


def load_intermediate(filename: str):
    """Load intermediate pipeline results if they exist."""
    output_path = OUTPUT_DIR / filename
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# Phrases that suggest the scout is rationalizing a date or the story is old.
_STALENESS_RE = re.compile(
    r"(?:last week|several weeks|last month|weeks ago|months ago|earlier this year|"
    r"late last year|falls within the .{0,20} window|is recent enough|"
    r"likely occurred recently)",
    re.IGNORECASE,
)

# Phrases in date_evidence that reveal inference rather than actual source evidence.
# These indicate the scout couldn't find a real publication date and guessed.
_WEAK_EVIDENCE_RE = re.compile(
    r"(?:no specific date|no date (?:url|found|visible|available)|"
    r"alongside .{0,30} items|current (?:news |feed )?page|"
    r"appears (?:on|in) the (?:feed|page|list)|"
    r"position on|inferred|estimated|assumed|approximat)",
    re.IGNORECASE,
)


def flag_date_suspicious(item: dict, cutoff: date) -> str | None:
    """Return a reason string if the item's date looks suspicious, else None."""
    reasons: list[str] = []

    # Check 1: date_evidence field missing, empty, or says NO DATE FOUND
    date_evidence = (item.get("date_evidence") or "").strip()
    if not date_evidence or "NO DATE FOUND" in date_evidence.upper():
        reasons.append("no_date_evidence")

    # Check 1b: date_evidence exists but contains weak/inferred evidence
    if date_evidence and _WEAK_EVIDENCE_RE.search(date_evidence):
        reasons.append("weak_date_evidence")

    # Check 2: staleness phrases in text fields
    text_to_scan = " ".join(
        filter(None, [
            item.get("date_evidence", ""),
            item.get("additional_context", ""),
            item.get("raw_content", ""),
            item.get("summary", ""),
        ])
    )
    if _STALENESS_RE.search(text_to_scan):
        reasons.append("staleness_phrase_detected")

    # Check 3: URL date slug vs. claimed date
    source_url = item.get("source_url") or ""
    url_date_match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", source_url)
    if url_date_match:
        try:
            url_date = date(
                int(url_date_match.group(1)),
                int(url_date_match.group(2)),
                int(url_date_match.group(3)),
            )
            item_date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
            if abs((item_date - url_date).days) > 3:
                reasons.append(f"url_date_mismatch(url={url_date}, claimed={item_date})")
        except (ValueError, TypeError):
            pass

    # Check 4: main date vs. earliest also_covered_by date spread
    earliest = _earliest_source_date(item)
    if earliest:
        try:
            main_date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
            spread = (main_date - earliest).days
            if spread > 2:
                reasons.append(f"source_date_spread({earliest} to {main_date})")
        except (ValueError, TypeError):
            pass

    # Check 5: verified date vs. claimed date mismatch
    verified_str = item.get("_verified_date", "")
    if verified_str:
        try:
            verified_date = datetime.strptime(verified_str, "%Y-%m-%d").date()
            claimed_date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
            if abs((claimed_date - verified_date).days) > 2:
                reasons.append(f"verified_date_mismatch(verified={verified_date}, claimed={claimed_date})")
        except (ValueError, TypeError):
            pass

    # Check 6: no date evidence AND no verified date → unverifiable
    # This means the scout provided no evidence for its date claim AND we
    # couldn't independently verify it from the URL. High risk of fabrication.
    reason_str = "; ".join(reasons)
    if "no_date_evidence" in reason_str and not item.get("_verified_date"):
        reasons.append("unverifiable_date")

    return "; ".join(reasons) if reasons else None


def _earliest_source_date(item: dict) -> date | None:
    """Return the earliest date across the main date, also_covered_by, and _verified_date.

    Handles both old format (list[str] — ignored) and new structured format
    (list[dict] with "source" and "date" keys).
    """
    dates: list[date] = []
    # Verified date from URL extraction (strongest signal)
    try:
        dates.append(datetime.strptime(item.get("_verified_date", ""), "%Y-%m-%d").date())
    except (ValueError, TypeError):
        pass
    # Main date
    try:
        dates.append(datetime.strptime(item.get("date", ""), "%Y-%m-%d").date())
    except (ValueError, TypeError):
        pass
    # Secondary source dates
    for s in item.get("also_covered_by", []):
        if isinstance(s, dict):
            try:
                dates.append(datetime.strptime(s.get("date", ""), "%Y-%m-%d").date())
            except (ValueError, TypeError):
                pass
    return min(dates) if dates else None


def _oldest_secondary_source_date(item: dict) -> date | None:
    """Return the oldest date found in also_covered_by only."""
    dates: list[date] = []
    for s in item.get("also_covered_by", []):
        if isinstance(s, dict):
            try:
                dates.append(datetime.strptime(s.get("date", ""), "%Y-%m-%d").date())
            except (ValueError, TypeError):
                pass
    return min(dates) if dates else None


def _primary_item_date(item: dict) -> tuple[date | None, str]:
    """Primary date used for hard recency filtering.

    Priority:
    1) _verified_date (strongest)
    2) item.date (claimed)
    """
    try:
        return datetime.strptime(item.get("_verified_date", ""), "%Y-%m-%d").date(), "_verified_date"
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(item.get("date", ""), "%Y-%m-%d").date(), "date"
    except (ValueError, TypeError):
        pass
    return None, "none"


def _primary_item_timestamp(item: dict) -> tuple[datetime | None, str]:
    """Primary timestamp used for exact recency filtering when available."""
    raw_timestamp = item.get("published_at", "")
    if not raw_timestamp:
        return None, "none"

    try:
        timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None, "none"

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=GST)
    return timestamp.astimezone(GST), "published_at"


def _warn_date_filter_100pct_culls(
    kept: list[dict], dropped: list[dict]
) -> list[tuple[str, int]]:
    """Log WARN for any source whose items were 100% cut by the date filter.

    When every item from a source gets cut at date_filter on a run, that's a
    strong signal of either a stale listing page (source publishes
    infrequently but scraper keeps re-yielding old items) or a date-parsing
    regression. The 2026-04-15 audit found Khazna/G42/Presight all hit 100%
    cull silently; this surfaces it in the run log so the next audit is
    one `grep` away instead of a post-hoc SQL join on dropped_items.

    Returns a list of (source_name, dropped_count) tuples that hit 100% cull,
    useful for the caller to persist to pipeline_runs.source_errors.
    """
    if not dropped:
        return []

    kept_by_source: dict[str, int] = {}
    for item in kept:
        src = (item.get("source") or "").strip()
        if src:
            kept_by_source[src] = kept_by_source.get(src, 0) + 1

    dropped_by_source: dict[str, int] = {}
    for item in dropped:
        src = (item.get("source") or "").strip()
        if src:
            dropped_by_source[src] = dropped_by_source.get(src, 0) + 1

    full_culls: list[tuple[str, int]] = []
    for source, drop_count in dropped_by_source.items():
        if kept_by_source.get(source, 0) == 0 and drop_count > 0:
            full_culls.append((source, drop_count))
            logger.warning(
                "Date filter: %s — 100%% cull (%d/%d items dropped). "
                "Check listing page for stale items.",
                source, drop_count, drop_count,
            )
    return full_culls


def _build_date_drop_record(
    item: dict,
    primary_value: date | datetime,
    primary_field: str,
    drop_reason: str,
    oldest_secondary: date | None,
) -> dict:
    """Build the audit row for a date-based drop."""
    return {
        "headline": item.get("headline", ""),
        "source": item.get("source", ""),
        "source_url": item.get("source_url", ""),
        "claimed_date": item.get("date", ""),
        "verified_date": item.get("_verified_date", ""),
        "published_at": item.get("published_at", ""),
        "primary_date": primary_value.isoformat(),
        "primary_field": primary_field,
        "oldest_secondary_date": str(oldest_secondary) if oldest_secondary else None,
        "drop_reason": drop_reason,
    }


def _manual_entry_ids(rows: list[dict]) -> set[str]:
    """Return the Supabase ids for a set of manual-entry rows."""
    return {str(row["id"]) for row in rows}


def _selected_manual_entry_ids(items: list[dict]) -> set[str]:
    """Return the ids of manual entries already present in pipeline output."""
    return {
        str(item.get("_manual_entry_id"))
        for item in items
        if item.get("_manual_entry_id")
    }


def filter_items_by_date(
    items: list[dict], cutoff: datetime
) -> tuple[list[dict], list[dict], list[dict]]:
    """Filter scout items that are older than the lookback cutoff.

    Hard drop uses PRIMARY publish date only:
      - _verified_date when available
      - otherwise claimed item date

    Scraped (non-newsletter) sources get a grace period of
    SCRAPER_GRACE_HOURS extra hours, because articles may be published
    a day before the scraper picks them up from the website listing.

    Secondary source dates in also_covered_by do NOT auto-drop items.
    If secondary sources are older than cutoff while the primary date
    passes, item is kept and flagged as ambiguous for downstream review.

    Returns (kept_items, dropped_items, flagged_items).
    dropped_items include reason metadata for audit artifacts.
    flagged_items are items that passed the date filter but have
    suspicious date evidence — they get a _date_flag field added.
    """
    kept = []
    dropped: list[dict] = []
    flagged = []
    cutoff_date = cutoff.date()
    grace_cutoff = cutoff - timedelta(hours=SCRAPER_GRACE_HOURS)
    grace_cutoff_date = grace_cutoff.date()

    for item in items:
        primary_timestamp, primary_timestamp_field = _primary_item_timestamp(item)
        primary_date, primary_field = _primary_item_date(item)
        oldest_secondary = _oldest_secondary_source_date(item)

        # Scraped sources get a grace period; newsletters use strict cutoff
        is_newsletter = is_newsletter_origin(item)
        eff_cutoff = cutoff if is_newsletter else grace_cutoff
        eff_cutoff_date = cutoff_date if is_newsletter else grace_cutoff_date

        if primary_timestamp and primary_timestamp < eff_cutoff:
            logger.info(
                "Date filter dropped (primary %s=%s < cutoff %s%s): %s",
                primary_timestamp_field,
                primary_timestamp.isoformat(),
                eff_cutoff.isoformat(),
                "" if is_newsletter else " +grace",
                item.get("headline", "no headline")[:80]
            )
            dropped.append(
                _build_date_drop_record(
                    item,
                    primary_timestamp,
                    primary_timestamp_field,
                    f"primary_timestamp_before_cutoff ({primary_timestamp_field})",
                    oldest_secondary,
                )
            )
            continue

        if primary_date and primary_date < eff_cutoff_date:
            logger.info(
                "Date filter dropped (primary %s=%s < cutoff %s%s): %s",
                primary_field, primary_date, eff_cutoff_date,
                "" if is_newsletter else " +grace",
                item.get("headline", "no headline")[:80]
            )
            dropped.append(
                _build_date_drop_record(
                    item,
                    primary_date,
                    primary_field,
                    f"primary_date_before_cutoff ({primary_field})",
                    oldest_secondary,
                )
            )
            continue

        suspicion = flag_date_suspicious(item, cutoff_date)
        if oldest_secondary and primary_date and oldest_secondary < cutoff_date:
            extra_flag = (
                f"secondary_source_older_than_cutoff(oldest={oldest_secondary}, "
                f"primary={primary_date})"
            )
            suspicion = f"{suspicion}; {extra_flag}" if suspicion else extra_flag

        if not primary_date:
            extra_flag = "unparseable_primary_date"
            suspicion = f"{suspicion}; {extra_flag}" if suspicion else extra_flag

        if suspicion:
            item["_date_flag"] = suspicion
            flagged.append(item)
            logger.warning(
                "Date suspicious: [%s] %s -- %s",
                item.get("date", ""),
                item.get("headline", "")[:80],
                suspicion,
            )

        kept.append(item)

    return kept, dropped, flagged


# DEPRECATED 2026-04-15: Replaced by the Synthesis stage (pipeline/synthesis.py).
# Kept as dead code behind the SYNTHESIS_ENABLED flag for rollback safety.
# Remove once Synthesis has run cleanly in prod for 2 weeks.
# See .claude/plans/robust-sleeping-raven.md (Phase 2).
def flag_previous_brief_overlaps(
    items: list[dict],
) -> tuple[list[dict], list[dict], int]:
    """Check items against recent briefs for repeats.

    Two tiers:
      HARD DROP — headline/content clearly match a recent brief item.
      SOFT FLAG — likely overlap that still needs editorial scrutiny.

    Returns (kept_items, hard_dropped_rows, num_soft_flagged).
    """
    from difflib import SequenceMatcher

    HARD_DROP_HEADLINE_THRESHOLD = 0.70
    HARD_DROP_COMBINED_THRESHOLD = 0.78
    HARD_DROP_COMBINED_WITH_TOKEN_OVERLAP = 0.68
    HARD_DROP_HEADLINE_WITH_TOKEN_OVERLAP = 0.45
    SOFT_FLAG_COMBINED_THRESHOLD = 0.52
    TOKEN_OVERLAP_THRESHOLD = 4
    HARD_DROP_TOKEN_OVERLAP_THRESHOLD = 5
    SOFT_TOKEN_OVERLAP_THRESHOLD = 3
    STOPWORDS = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
        "as", "at", "by", "from", "into", "amid", "after", "before", "over",
        "under", "new", "this", "that", "their", "its", "his", "her", "us",
        "u.s", "uae", "ai", "gulf",
    }

    # Use the merged published + pending history so items the analyst
    # rejected yesterday also count as "already seen" — without this, the
    # deterministic tier only catches repeats of published items.
    headlines_json = get_recent_history_headlines()
    if "No previous brief" in headlines_json:
        return items, [], 0

    try:
        prev_headlines = json.loads(headlines_json)
    except (json.JSONDecodeError, TypeError):
        return items, [], 0

    # Normalize entity text: strip markdown bold, lowercase
    def norm(entity: str) -> str:
        return re.sub(r"\*+", "", entity).strip().lower()

    def normalize_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def distinctive_tokens(text: str) -> set[str]:
        return {
            token
            for token in normalize_text(text).split()
            if len(token) > 2 and token not in STOPWORDS
        }

    # Build previous brief entry sets
    prev_entries = []
    for ph in prev_headlines:
        ents = set(norm(e) for e in ph.get("entities", []))
        headline = ph.get("headline", "")
        main_bullet = ph.get("main_bullet", "")
        combined = " ".join(part for part in [headline, main_bullet] if part)
        prev_entries.append({
            "headline": headline,
            "headline_norm": normalize_text(headline),
            "combined_norm": normalize_text(combined),
            "brief_date": ph.get("brief_date", ""),
            "entities": ents,
            "tokens": distinctive_tokens(combined or headline),
        })

    kept = []
    hard_dropped: list[dict] = []
    soft_flagged = 0

    for item in items:
        item_headline = str(item.get("headline", "") or "")
        item_summary = str(item.get("summary", "") or "")
        item_main_bullet = str(item.get("main_bullet", "") or "")
        item_headline_norm = normalize_text(item_headline)
        item_combined_norm = normalize_text(
            " ".join(part for part in [item_headline, item_summary, item_main_bullet] if part)
        )
        item_ents = set(norm(e) for e in item.get("entities", []))
        item_tokens = distinctive_tokens(" ".join([item_headline, item_summary, item_main_bullet]))

        best_hard_score = 0.0
        best_hard_reason = ""
        best_hard_match = None
        best_soft_overlap = 0
        best_soft_match = None

        for prev in prev_entries:
            headline_sim = SequenceMatcher(None, item_headline_norm, prev["headline_norm"]).ratio()
            combined_sim = 0.0
            if item_combined_norm and prev["combined_norm"]:
                combined_sim = SequenceMatcher(None, item_combined_norm, prev["combined_norm"]).ratio()
            token_overlap = len(item_tokens & prev["tokens"])
            entity_overlap = len(item_ents & prev["entities"])

            is_hard = False
            reason = ""
            score = max(headline_sim, combined_sim)

            if headline_sim >= HARD_DROP_HEADLINE_THRESHOLD:
                is_hard = True
                reason = f"headline similarity {headline_sim:.2f}"
            elif combined_sim >= HARD_DROP_COMBINED_THRESHOLD:
                is_hard = True
                reason = f"content similarity {combined_sim:.2f}"
            elif combined_sim >= HARD_DROP_COMBINED_WITH_TOKEN_OVERLAP and token_overlap >= TOKEN_OVERLAP_THRESHOLD:
                is_hard = True
                reason = (
                    f"content similarity {combined_sim:.2f} with "
                    f"{token_overlap} shared key terms"
                )
            elif headline_sim >= HARD_DROP_HEADLINE_WITH_TOKEN_OVERLAP and token_overlap >= HARD_DROP_TOKEN_OVERLAP_THRESHOLD:
                is_hard = True
                reason = (
                    f"headline similarity {headline_sim:.2f} with "
                    f"{token_overlap} shared key terms"
                )

            if is_hard and score > best_hard_score:
                best_hard_score = score
                best_hard_reason = reason
                best_hard_match = prev

            if entity_overlap >= 2:
                if entity_overlap > best_soft_overlap:
                    best_soft_overlap = entity_overlap
                    best_soft_match = prev
            elif combined_sim >= SOFT_FLAG_COMBINED_THRESHOLD and token_overlap >= SOFT_TOKEN_OVERLAP_THRESHOLD:
                if token_overlap > best_soft_overlap:
                    best_soft_overlap = token_overlap
                    best_soft_match = prev

        # HARD DROP: clearly the same story as a recent brief
        if best_hard_match:
            logger.info(
                f"Previous-brief HARD DROP ({best_hard_reason}): "
                f"'{item.get('headline', '')[:60]}' ↔ "
                f"'{best_hard_match['headline'][:60]}' ({best_hard_match['brief_date']})"
            )
            hard_dropped.append({
                "headline": item.get("headline", ""),
                "composite_score": item.get("composite_score"),
                # PHASE 1: preserve source + URL so drop visibility has enough
                # info to display rows in the admin Drops view.
                "source": item.get("source") or item.get("source_name"),
                "source_url": item.get("source_url"),
                "drop_reason": (
                    f"Previous brief repeat — matches "
                    f"\"{best_hard_match['headline']}\" from {best_hard_match['brief_date']} "
                    f"({best_hard_reason})"
                ),
                "_matched_brief_date": best_hard_match["brief_date"],
                "_match_reason": best_hard_reason,
            })
            continue

        # SOFT FLAG: overlap but not strong enough to auto-drop
        if best_soft_match:
            item["_previous_brief_overlap"] = (
                f"Overlaps with \"{best_soft_match['headline']}\" "
                f"from {best_soft_match['brief_date']} brief"
            )
            logger.info(
                f"Previous-brief overlap: '{item.get('headline', '')[:60]}' ↔ "
                f"'{best_soft_match['headline'][:60]}' ({best_soft_match['brief_date']})"
            )
            soft_flagged += 1

        kept.append(item)

    return kept, hard_dropped, soft_flagged


# DEPRECATED 2026-04-15: Replaced by Synthesis continuity annotations.
# Kept as dead code behind SYNTHESIS_ENABLED for rollback safety.
def apply_continuity_penalty(items: list[dict]) -> int:
    """Penalize overlapping items so fresh stories outrank continuations."""
    penalized_count = 0
    for item in items:
        if item.get("_previous_brief_overlap"):
            original_score = item.get("significance", 0)
            try:
                original_score = float(original_score)
            except (ValueError, TypeError):
                original_score = 5.0
            item["significance"] = max(1.0, original_score - CONTINUITY_PENALTY)
            item["_continuity_penalized"] = True
            penalized_count += 1
    return penalized_count


def _build_raw_content_lookup(items: list[dict]) -> dict[str, list[dict]]:
    """Build a lookup dict for rejoining raw_content after Gatekeeper.

    Keys are source_url when available, otherwise source-name buckets;
    values are lists of {headline, raw_content,
    additional_context} dicts (lists because rare duplicate URLs exist).
    """
    lookup: dict[str, list[dict]] = {}
    for item in items:
        key = _raw_content_lookup_key(item)
        lookup.setdefault(key, []).append({
            "headline": item.get("headline", ""),
            "raw_content": item.get("raw_content", ""),
            "additional_context": item.get("additional_context", ""),
        })
    return lookup


# Smart-quote rewrite observed 2026-04-22: the Gatekeeper LLM silently
# normalises U+2019 / U+2018 / U+201C / U+201D to their ASCII counterparts
# when echoing URLs, breaking byte-exact rejoin lookup for scout URLs that
# contain curly quotes (common in WAM slugs). Normalise the lookup key —
# not the stored URL — so both sides agree.
_SMART_QUOTE_LOOKUP_MAP = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
})


def _raw_content_lookup_key(item: dict) -> str:
    """Return a stable lookup key for raw-content rejoin.

    We prefer source_url when present. Items without URLs (notably split
    newsletters) fall back to a source-scoped bucket so unrelated empty-URL
    stories do not collide into the same candidate pool.

    The URL is passed through _SMART_QUOTE_LOOKUP_MAP because upstream LLM
    stages rewrite smart quotes to ASCII when echoing URLs — see 2026-04-22
    s003 (DIFC) / s017 (ALTÉRRA) in the daily pipeline log.
    """
    url = (item.get("source_url") or "").strip().translate(_SMART_QUOTE_LOOKUP_MAP)
    if url:
        return f"url::{url}"
    source = (item.get("source") or item.get("source_name") or "").strip().lower()
    return f"source::{source}"


def _normalize_for_match(headline: str) -> str:
    """Normalize a headline for fuzzy matching during rejoin."""
    return re.sub(r"[^\w\s]", "", headline.lower()).strip()[:60]


def rejoin_raw_content(
    selected_items: list[dict],
    raw_content_lookup: dict[str, list[dict]],
) -> tuple[list[dict], list[str]]:
    """Rejoin raw_content and additional_context onto Gatekeeper-selected items.

    The Gatekeeper receives items without raw_content to save tokens.
    After selection, this reattaches the stripped fields using source_url
    as primary key and headline similarity as tiebreaker for duplicate URLs.
    """
    enriched = []
    warnings = []

    for item in selected_items:
        key = _raw_content_lookup_key(item)
        candidates = raw_content_lookup.get(key, [])

        if len(candidates) == 1:
            item["raw_content"] = candidates[0]["raw_content"]
            item["additional_context"] = candidates[0]["additional_context"]
        elif len(candidates) > 1:
            # Multiple items share this URL — match by headline similarity
            gk_norm = _normalize_for_match(item.get("headline", ""))
            best_match = None
            best_score = 0.0
            for cand in candidates:
                cand_norm = _normalize_for_match(cand["headline"])
                score = SequenceMatcher(None, gk_norm, cand_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_match = cand

            if best_match and best_score >= 0.5:
                item["raw_content"] = best_match["raw_content"]
                item["additional_context"] = best_match["additional_context"]
            else:
                item["raw_content"] = ""
                item["additional_context"] = ""
                warnings.append(
                    f"Rejoin skipped for '{item.get('headline', '')[:60]}' "
                    f"(best_score={best_score:.2f}, key={key})"
                )
        else:
            item["raw_content"] = ""
            item["additional_context"] = ""
            warnings.append(
                f"Rejoin FAILED: no lookup match for '{item.get('headline', '')[:60]}'"
            )

        enriched.append(item)

    return enriched, warnings


def assign_significance_level(score: float) -> str:
    """Map composite_score to a UI-facing significance tier."""
    if score >= 8.0:
        return "high"
    if score >= 6.0:
        return "medium"
    return "low"


def enrich_items(items: list[dict]) -> None:
    """Add deterministic frontend metadata to all items (in-place)."""
    for item in items:
        item["significance_level"] = assign_significance_level(
            item.get("composite_score", 0)
        )


def is_http_url(url: str | None) -> bool:
    """Return True when the value is a non-empty http(s) URL."""
    if not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def sanitize_additional_sources(sources: list | None) -> list[dict]:
    """Keep only additional sources that have a valid absolute URL."""
    cleaned: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for source in sources or []:
        if not isinstance(source, dict):
            continue
        name = str(source.get("name") or source.get("source") or "").strip()
        url = str(source.get("url") or source.get("source_url") or "").strip()
        if not name or not is_http_url(url):
            continue
        key = (name.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"name": name, "url": url})

    return cleaned


def is_newsletter_origin(item: dict) -> bool:
    """Return True when the item originated from a Gmail newsletter digest."""
    source_name = str(item.get("source_name") or item.get("source") or "").strip()
    if source_name in NEWSLETTER_SOURCE_NAMES:
        return True

    source_origin = str(item.get("source_origin") or "").strip().lower()
    if source_origin == "newsletter":
        return True

    date_evidence = str(item.get("date_evidence") or "").lower()
    return "gmail_api" in date_evidence


def build_source_metadata_lookup(selected: list[dict]) -> dict[str, dict]:
    """Build a deterministic source-metadata lookup from Gatekeeper items."""
    lookup: dict[str, dict] = {}

    for item in selected:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            continue
        primary_name = str(item.get("source") or item.get("source_name") or "").strip()
        primary_url = str(item.get("source_url") or "").strip()
        lookup[item_id] = {
            "source_name": primary_name or None,
            "source_url": primary_url if is_http_url(primary_url) else None,
            "source_origin": "newsletter" if is_newsletter_origin(item) else "canonical",
            "additional_sources": sanitize_additional_sources(
                item.get("also_covered_by")
            ),
            "_manual_entry_id": str(item.get("_manual_entry_id") or "").strip() or None,
        }

    return lookup


def apply_source_metadata(items: list[dict], source_lookup: dict[str, dict]) -> None:
    """Normalize source fields in-place and drop invalid clickable links."""
    for item in items:
        item_id = str(item.get("id") or "").strip()
        canonical = source_lookup.get(item_id, {})

        primary_name = canonical.get("source_name") or item.get("source_name")
        primary_url = canonical.get("source_url")
        source_origin = canonical.get("source_origin") or item.get("source_origin")
        current_url = str(item.get("source_url") or "").strip()
        if primary_url is None and is_http_url(current_url):
            primary_url = current_url

        item["source_name"] = primary_name or None
        item["source_url"] = primary_url or None
        item["source_origin"] = source_origin or ("newsletter" if is_newsletter_origin(item) else "canonical")

        if primary_url:
            item["source_domain"] = extract_domain(primary_url)
        elif not item.get("source_domain"):
            item["source_domain"] = None

        merged_sources = sanitize_additional_sources(item.get("additional_sources"))
        if canonical.get("additional_sources"):
            merged_sources = sanitize_additional_sources(
                [*canonical["additional_sources"], *merged_sources]
            )

        if primary_url:
            merged_sources = [
                src for src in merged_sources if src["url"] != primary_url
            ]

        item["additional_sources"] = merged_sources
        if canonical.get("_manual_entry_id"):
            item["_manual_entry_id"] = canonical["_manual_entry_id"]


_MANUAL_ITEM_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-m(.+)$")


def _trim_words(text: str, max_words: int) -> str:
    """Trim text to a maximum number of words."""
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    trimmed = " ".join(words[:max_words]).strip().rstrip(",;:")
    return f"{trimmed}…"


def _ensure_sentence(text: str) -> str:
    """Normalize whitespace and ensure the text ends like a sentence."""
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?]":
        cleaned += "."
    return cleaned


def _best_fallback_evidence(item: dict) -> str:
    """Pick the strongest available evidence text for a fallback brief item."""
    enriched_facts = item.get("enriched_facts")
    if isinstance(enriched_facts, dict):
        summary = _ensure_sentence(enriched_facts.get("summary", ""))
        if summary:
            return summary

    enriched_sources = item.get("enriched_sources") or []
    if isinstance(enriched_sources, list):
        for source in enriched_sources:
            if isinstance(source, dict):
                extract = _ensure_sentence(source.get("extract", ""))
                if extract:
                    return extract

    for field in ("raw_content", "additional_context", "summary"):
        text = _ensure_sentence(item.get(field, ""))
        if text:
            return text

    headline = _ensure_sentence(item.get("headline", ""))
    if headline:
        return headline

    return "Selected item preserved after writer-stage omission."


def _fallback_depth(score: float) -> str:
    """Map a composite score to the closest brief depth."""
    if score >= 8.0:
        return "full"
    if score >= 7.0:
        return "standard"
    return "brief"


def _build_fallback_context(item: dict) -> str | None:
    """Construct a minimal context line from source metadata."""
    summary = item.get("summary", "")
    if summary and len(summary) > 50:
        return _ensure_sentence(_trim_words(summary, 40))
    return None


def _build_fallback_implication(item: dict) -> str | None:
    """Construct a minimal implication line from enriched facts."""
    enriched = item.get("enriched_facts")
    if isinstance(enriched, dict):
        imp = enriched.get("implication") or enriched.get("significance") or ""
        if imp:
            return _ensure_sentence(_trim_words(imp, 40))
    return None


def build_fallback_final_brief_item(
    source_item: dict,
    source_lookup: dict[str, dict],
    fallback_rank: int,
) -> dict:
    """Build a minimal final-brief item when an LLM stage omitted one."""
    item_id = str(source_item.get("id") or "").strip()
    canonical = source_lookup.get(item_id, {})
    source_url = canonical.get("source_url")
    source_name = canonical.get("source_name") or source_item.get("source") or None
    score = float(source_item.get("composite_score") or 0)

    evidence = _best_fallback_evidence(source_item)
    main_bullet = _ensure_sentence(_trim_words(evidence, 55))
    if source_url:
        main_bullet = f"{main_bullet} [Source: {source_url}]"

    fallback = {
        "id": item_id,
        "rank": int(source_item.get("rank") or fallback_rank),
        "section": normalize_section_name(source_item.get("brief_section")) or "UAE",
        "headline": str(source_item.get("headline") or "Recovered brief item").strip(),
        "source_domain": extract_domain(source_url) if source_url else None,
        "source_name": source_name,
        "source_url": source_url,
        "additional_sources": sanitize_additional_sources(
            canonical.get("additional_sources")
        ),
        "main_bullet": main_bullet,
        "context": _build_fallback_context(source_item),
        "implication": _build_fallback_implication(source_item),
        "entities": list(source_item.get("entities") or []),
        "composite_score": score,
        "significance_level": assign_significance_level(score),
        "cluster": source_item.get("cluster"),
        "continuity": source_item.get("continuity"),
        "is_model_release": bool(source_item.get("is_model_release")),
        "model_release_data": source_item.get("model_release_data"),
        "depth": _fallback_depth(score),
    }
    if canonical.get("_manual_entry_id") or source_item.get("_manual_entry_id"):
        fallback["_manual_entry_id"] = (
            canonical.get("_manual_entry_id") or source_item.get("_manual_entry_id")
        )
    return fallback


def reconcile_final_brief_with_selected(
    final_brief: dict,
    selected_items: list[dict],
    source_lookup: dict[str, dict],
    edit_log: list[dict] | None = None,
) -> list[str]:
    """Restore any selected items that vanished before final brief save."""
    items = list(final_brief.get("items", []) or [])
    present_ids = {
        str(item.get("id") or "").strip()
        for item in items
        if str(item.get("id") or "").strip()
    }
    restored_ids: list[str] = []

    for fallback_rank, source_item in enumerate(selected_items, start=1):
        item_id = str(source_item.get("id") or "").strip()
        if not item_id or item_id in present_ids:
            continue

        restored_item = build_fallback_final_brief_item(
            source_item,
            source_lookup,
            fallback_rank=fallback_rank,
        )
        items.append(restored_item)
        present_ids.add(item_id)
        restored_ids.append(item_id)

        if edit_log is not None:
            edit_log.append(
                {
                    "entry": restored_item.get("headline", item_id),
                    "type": "pipeline_recovery",
                    "original": "",
                    "corrected": "Restored missing item from selected evidence",
                    "reason": (
                        "Item was selected upstream but disappeared in a later LLM stage. "
                        "The pipeline restored it from structured source evidence to preserve coverage."
                    ),
                }
            )

    if restored_ids:
        items.sort(
            key=lambda item: (
                int(item.get("rank") or 999),
                str(item.get("id") or ""),
            )
        )
        final_brief["items"] = items

    return restored_ids


def extract_included_manual_entry_ids(items: list[dict]) -> set[str]:
    """Return manual entry ids that actually made it into a brief."""
    included: set[str] = set()
    for item in items:
        manual_entry_id = str(item.get("_manual_entry_id") or "").strip()
        if manual_entry_id:
            included.add(manual_entry_id)
            continue

        item_id = str(item.get("id") or "").strip()
        match = _MANUAL_ITEM_ID_RE.match(item_id)
        if match:
            included.add(match.group(1))

    return included


def manual_entry_ids_ready_to_mark(
    pending_manual_ids: set[str],
    items: list[dict],
) -> list[str]:
    """Return pending manual entry ids that are actually present in the saved brief."""
    return sorted(pending_manual_ids & extract_included_manual_entry_ids(items))


def format_cost(total_input: int, total_output: int) -> str:
    """Format token usage and estimated cost for console output."""
    input_cost = (total_input / 1_000_000) * INPUT_COST_PER_M
    output_cost = (total_output / 1_000_000) * OUTPUT_COST_PER_M
    total_cost = estimate_cost_usd(total_input, total_output)
    return (
        f"Token usage: {total_input:,} input, {total_output:,} output | "
        f"Estimated cost: ${total_cost:.2f} "
        f"(${input_cost:.2f} in + ${output_cost:.2f} out)"
    )


def build_retry_correction(stage: str, error: Exception) -> str:
    """Build a corrective retry suffix after parse/validation failures."""
    err = str(error).replace("{", "(").replace("}", ")").strip()
    if len(err) > 900:
        err = err[:900] + "..."
    return (
        "\n\nCRITICAL RETRY INSTRUCTION:\n"
        f"Your previous {stage} output was invalid and failed schema checks.\n"
        f"Validation error: {err}\n"
        "Return ONLY valid JSON (no markdown, no commentary) that strictly "
        "matches the required output format and includes every required field."
    )


def normalize_scout_contract(items: list[dict]) -> int:
    """Normalize scout fields to the canonical schema. Returns fixes applied."""
    fixes = 0
    for item in items:
        date_evidence = item.get("date_evidence")
        if not isinstance(date_evidence, str) or not date_evidence.strip():
            item["date_evidence"] = NO_DATE_EVIDENCE
            fixes += 1
        else:
            clean = date_evidence.strip()
            if clean != date_evidence:
                item["date_evidence"] = clean
                fixes += 1

        if not isinstance(item.get("also_covered_by"), list):
            item["also_covered_by"] = []
            fixes += 1
    return fixes


def normalize_section_name(section: str | None) -> str | None:
    """Normalize a section label to canonical BRIEF_SECTIONS."""
    if not isinstance(section, str):
        return None
    key = re.sub(r"\s+", " ", section.strip().lower())
    return SECTION_NAME_MAP.get(key)


def normalize_sections(
    items: list[dict],
    field: str,
    stage_name: str,
) -> tuple[list[dict], list[str]]:
    """Normalize section names and reject unknown values."""
    normalized_items: list[dict] = []
    warnings: list[str] = []
    for item in items:
        original = item.get(field)
        normalized = normalize_section_name(original)
        if not normalized:
            warnings.append(
                f"{stage_name}: dropped unknown section '{original}' "
                f"for item '{item.get('headline', '')[:60]}'"
            )
            continue
        item[field] = normalized
        normalized_items.append(item)
    return normalized_items, warnings


def extract_domain(url: str) -> str:
    """Extract and normalize domain from URL."""
    if not isinstance(url, str) or not url.strip():
        return ""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def demerge_selected_items(
    selected: list[dict],
    scout_items: list[dict],
) -> tuple[list[dict], int]:
    """Split gatekeeper-selected items that contain semicolon-merged headlines.

    The gatekeeper model consistently merges distinct scout items into single
    selections with semicolon-joined headlines (e.g., "Trump signals end to
    Iran war; oil falls below $100").  This step detects these, splits them,
    and maps each part back to the original scout item via fuzzy headline
    matching.

    Returns (demerged_selected, merge_count) where merge_count is the number
    of merged items that were split.
    """
    if not scout_items:
        return selected, 0

    result: list[dict] = []
    merge_count = 0

    for item in selected:
        headline = item.get("headline", "")

        # Detection: semicolons that separate distinct statements.
        # Skip semicolons inside quotes or parentheses to avoid false positives.
        if ";" not in headline:
            result.append(item)
            continue

        parts = [p.strip() for p in headline.split(";") if p.strip()]
        if len(parts) < 2:
            result.append(item)
            continue

        # Try to match each part back to a scout item.
        matched_any = False
        demerged_items = []

        for part in parts:
            part_norm = _normalize_for_match(part)
            best_match = None
            best_score = 0.0

            for scout in scout_items:
                scout_headline = scout.get("headline", "")
                scout_norm = _normalize_for_match(scout_headline)
                score = SequenceMatcher(None, part_norm, scout_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_match = scout

            if best_match and best_score >= 0.4:
                matched_any = True
                # Create a new selected item inheriting gatekeeper metadata
                # but with the original scout item's identity fields.
                new_item = dict(item)  # shallow copy of gatekeeper scoring
                new_item["headline"] = best_match.get("headline", part)
                new_item["source"] = best_match.get("source", item.get("source", ""))
                new_item["source_url"] = best_match.get("source_url", item.get("source_url", ""))
                new_item["summary"] = best_match.get("summary", "")
                new_item["entities"] = best_match.get("entities", [])
                new_item["raw_content"] = best_match.get("raw_content", "")
                new_item["additional_context"] = best_match.get("additional_context", "")
                new_item["date"] = best_match.get("date", item.get("date", ""))
                new_item["date_evidence"] = best_match.get("date_evidence", item.get("date_evidence", ""))
                new_item["also_covered_by"] = best_match.get("also_covered_by", [])
                # Clear ID so assign_gatekeeper_ids can re-assign
                new_item.pop("id", None)
                demerged_items.append(new_item)
            else:
                # Part doesn't match any scout item — create item from the
                # gatekeeper's data with just this headline fragment.
                new_item = dict(item)
                new_item["headline"] = part
                new_item.pop("id", None)
                demerged_items.append(new_item)

        if matched_any and len(demerged_items) >= 2:
            result.extend(demerged_items)
            merge_count += 1
            logger.info(
                f"Demerge: split '{headline[:60]}' → "
                f"{len(demerged_items)} items"
            )
        else:
            # Couldn't match — keep original merged item as-is.
            result.append(item)

    # Re-number ranks sequentially.
    for i, item in enumerate(result, start=1):
        item["rank"] = i

    return result, merge_count


def assign_gatekeeper_ids(selected: list[dict], today: str) -> None:
    """Assign deterministic item IDs for the Ghostwriter ID contract."""
    for i, item in enumerate(selected, start=1):
        if not item.get("id"):
            item["id"] = f"{today}-s{i:03d}"


async def dedup_selected_pool(
    selected: list[dict], today: str, client
) -> list[dict]:
    """Re-dedup the post-Gatekeeper selected pool before Ghostwriter.

    Stage 1+2 dedup runs once on raw collected items, but two items with
    very different raw headlines can both pass Gatekeeper and then be
    rewritten by Ghostwriter into near-identical headlines (e.g. the
    2026-04-17 alpha.G42.ai pair shared a source URL but distinct raw
    titles). Running the same dedup pipeline on the selected pool catches
    these before Ghostwriter cost is incurred. Drops are appended to the
    existing dropped_by_dedup audit file so ingest tags them under the
    "dedup" stage like the early-stage drops.
    """
    if len(selected) < 2:
        return selected
    before = len(selected)
    deduped, num_merged, _, drops = await deduplicate_items(selected, client)
    if num_merged == 0:
        return selected
    print(
        f"{timestamp()} Post-Gatekeeper dedup: {before} \u2192 {len(deduped)} "
        f"selected ({num_merged} duplicate(s) merged)"
    )
    existing = load_intermediate(f"dropped_by_dedup_{today}.json") or {}
    existing_drops = existing.get("dropped", []) if isinstance(existing, dict) else []
    save_intermediate(
        f"dropped_by_dedup_{today}.json",
        {
            "dropped_count": len(existing_drops) + len(drops),
            "dropped": existing_drops + drops,
        },
    )
    return deduped


def assign_candidate_ids(items: list[dict], today: str) -> None:
    """Assign stable pre-gatekeeper IDs used for dropped-item recovery."""
    for i, item in enumerate(items, start=1):
        if not item.get("id"):
            item["id"] = f"{today}-c{i:03d}"


# Max chars of summary/raw_content to send per item. Sized so a 600-item
# run adds ~180K chars (~45K tokens) to triage input — comfortably inside
# Haiku's 200K context. The summary is what lets Haiku tell a robotics
# demo from a sports result when the headline alone is ambiguous.
#
# Widened 150 → 300 on 2026-04-23 after a real-scale reproduction showed
# Musk's MBZ phone-call item was dropped because the first 150 chars of
# an enriched WAM body are eaten by the "UAE President His Highness …
# received a phone call from American entrepreneur …" run-up, leaving the
# substantive "AI, advanced technology, space" signal outside the window.
_TRIAGE_SUMMARY_SNIPPET_CHARS = 300


def _build_triage_line(index: int, item: dict) -> str:
    """Build one numbered input line for the triage LLM call.

    Extracted so it can be unit-tested without mocking the full Haiku
    call. See `prompts/triage_prompt.md` for the input format the prompt
    expects (`"{n}. {headline} — {summary}"`).
    """
    headline = item.get("headline", "(no headline)")
    line = f"{index + 1}. {headline}"
    summary = (item.get("summary") or item.get("raw_content") or "").strip()
    if summary:
        snippet = summary[:_TRIAGE_SUMMARY_SNIPPET_CHARS].strip()
        if snippet:
            line += f" — {snippet}"
    return line


# PHASE 3 (chunked triage, 2026-04-23): the legacy single-call path put
# all 400-600 collected items into one Haiku prompt. Production data
# showed ~50% false-positive rate on "non-news junk" drops (Apple CEO
# transition, Iran-skips-talks, etc. wrongly dropped as junk). Live
# A/B testing confirmed: same prompt + same model + smaller batch →
# much better recall. Root cause matches the chunked Gatekeeper fix:
# Haiku tail-recall degrades on long inputs, and emitting a long index
# list tilts the model toward conservative drops.
#
# Constants control the chunk path. Sized to mirror
# `pipeline.section_classifier`'s existing parallel-Haiku-batches-with-
# semaphore pattern (CANDIDATE_BATCH_SIZE=30, CANDIDATE_CONCURRENCY=5).
# Triage chunks can be larger because each item is just a headline +
# 300-char snippet (~50 input tokens vs section classifier's richer
# payload), so 60 items per chunk fits comfortably in Haiku's window
# without recall loss.
TRIAGE_SINGLE_CALL_THRESHOLD = 60   # ≤60 items → single call (no chunk overhead)
TRIAGE_CHUNK_SIZE = 60              # chunk size for parallel batches
TRIAGE_CONCURRENCY = 5              # mirrors section_classifier
TRIAGE_SANITY_SAMPLE_SIZE = 40      # how many drops to re-score per run
TRIAGE_SANITY_ALERT_THRESHOLD = 0.10  # disagreement rate above which to alert
TRIAGE_SANITY_EDITORIAL_SAMPLE_FLOOR = 0.5  # ≥50% of sanity sample must be editorial-source drops when any exist


# Source-aware floor — paid editorial wires that should never silently lose
# a hard-news item to triage flakiness.
#
# On 2026-04-24 the chunked Haiku triage dropped a TechCrunch Meta layoff
# headline ("Meta to cut 10% of jobs, or 8,000 employees") as "obvious
# non-news junk" — alongside three copies of the Dubai $9B Metro Gold Line
# expansion and three copies of the DOJ marijuana reclassification (all
# from paid wires).
#
# On 2026-04-27 the same flakiness took out four copies of "Trump cancels
# Pakistan envoy trip" (WSJ x2, Bloomberg, WAM) plus the Semafor merge
# winner that survived to history_dedup. The bypass regex did not catch
# them because v1 covered $ amounts / % / M&A / personnel only — not
# diplomatic verbs. The "Reuters Daily Briefing" copy also missed because
# the source set was exact-match, not prefix-match.
#
# Editorial-wire items skip the Haiku triage call entirely. Phase 1.5
# (post-Phase-1 inverted-default cleanup): the wide `BYPASS_HEADLINE_PATTERN`
# regex is gone — the inverted-default policy already auto-keeps every
# editorial item that doesn't match the JUNK pattern, so the regex was
# only doing useful work in the narrow case where a headline matched
# BOTH a hard-news pattern AND the junk pattern. That narrow case is now
# handled by `_TRIAGE_HARD_NEWS_OVERRIDE` (~5 patterns), which kicks in
# only when junk also fires.

# Editorial-wire source prefixes. A source is editorial if its name equals
# or begins with one of these. Prefix matching (vs the previous frozenset
# exact-match) is required because newsletter variants like "Reuters Daily
# Briefing" don't equal the bare wire name "Reuters". The trailing space
# on `"FT "` is intentional: distinguishes "FT Briefing"/"FT Edit" from a
# hypothetical "FTSE 100" feed.
TRIAGE_BYPASS_SOURCE_PREFIXES = (
    "Bloomberg", "WSJ", "FT ", "Financial Times", "Reuters", "Semafor",
    "Axios", "TechCrunch", "The National",
)

# Backward-compatible: a few code paths (sanity-check stratification, drop
# audit) still read this set. Kept as the subset of exact-wire names so
# `source in TRIAGE_BYPASS_SOURCES` membership tests behave the same for
# observed source names; `_source_is_editorial` is the canonical check.
TRIAGE_BYPASS_SOURCES = frozenset({
    "Bloomberg Briefing", "WSJ Briefing", "FT Briefing", "FT Edit",
    "Reuters", "Reuters Daily Briefing",
    "Semafor Flagship", "Semafor Gulf", "Axios AM/PM", "Axios AI+",
    "TechCrunch", "The National",
})

# Hard-news markers that OVERRIDE the junk-pattern drop for editorial
# wires. Applied only when `TRIAGE_JUNK_PATTERN` also matches — the
# override turns a would-be `default_drop` into a `bypass_keep`.
#
# Tiny by design: post-Phase-1 inverted-default policy already keeps
# every editorial-source item that doesn't match the junk pattern. The
# override only needs to handle the narrow "headline matches BOTH hard-
# news AND junk patterns" case (e.g. "Marathon Pharma raises $500M
# Series F" — `marathon` = junk, `$500M` = hard news; the override
# wins).
#
# The previous v3 regex (post-2026-04-27) enumerated diplomacy verbs,
# military verbs, layoffs, M&A, funding rounds, ceasefire shapes etc.
# — all redundant under inverted default because none of them overlap
# with `TRIAGE_JUNK_PATTERN`. Slimmed to ~5 patterns covering the
# realistic overlap classes only.
_TRIAGE_HARD_NEWS_OVERRIDE = re.compile(
    "|".join((
        # Currency amounts ≥ million scale. Anything sub-million
        # ("$13.61 cocktail price") deliberately doesn't match — small
        # dollar amounts in junk-shaped headlines are rarely news.
        r"\$\d+(?:\.\d+)?\s*(?:billion|trillion|million|[BMT]\b)",
        r"€\d+(?:\.\d+)?\s*(?:bn|billion|m|million)",
        r"£\d+(?:\.\d+)?\s*(?:bn|billion|m|million)",
        # Percentages — bounded by `%` literal.
        r"\d+%",
        # Hard-news event nouns whose presence outweighs a junk match.
        r"\blayoffs?\b|\bacquisition\b|\bsanction\b|\bindict\b",
    )),
    re.IGNORECASE,
)


# Inverted triage default — bounded, explicit junk pattern. Editorial-wire
# items that don't match any hard-news pattern AND don't match a junk pattern
# default to KEEP. Paid wires don't run human-sport recaps or restaurant
# openings as headline news, so the failure cost of dropping a hard-news
# item we didn't enumerate is much higher than the cost of letting an
# occasional commentary piece through (gatekeeper is the next gate).
#
# The junk pattern stays deliberately small — sports/lifestyle/ceremonial
# shapes that are unambiguous. Anything borderline is left for downstream
# stages to filter.
TRIAGE_JUNK_PATTERN = re.compile(
    "|".join((
        # Sports / leisure. `\bmarathon\b` matches even robotics-marathon
        # demos here; the `_triage_classify` Python override checks for
        # robotics keywords anywhere in the headline FIRST and short-
        # circuits before the junk-pattern check, so those still survive.
        # Variable-width lookbehind isn't well-supported by Python `re`,
        # so the override happens at the function level.
        r"\bmarathon\b",
        r"\bjudo\b|\btaekwondo\b|\bsailing\b|\bgolf\b|\bcricket\b|\btennis\b|\brugby\b",
        r"\bhotels?\s+record\b|\bhotel\s+occupancy\b",
        r"\bcocktail\s+price\b|\brestaurant\s+(?:opens|opening)\b",
        r"\bcelebrity\b|\bfashion\s+week\b",
        # Ceremonial / congratulatory
        r"\bcondolences\b|\bcongratulat\w+\s+(?:call|message)\b",
        r"\bhonours?\s+innovators\b|\bribbon[- ]cutting\b",
        r"\bmedal\s+tally\b|\bmedals\s+at\b",
        # Travel / cultural fluff
        r"\bhorseback\b|\bart\s+festival\b|\bcultural\s+festival\b",
        # Pure social-media / event-listing scraps
        r"\bjoin\s+us\s+(?:in|at)\b|\bexcited\s+to\s+(?:be|announce)\b",
        r"#[A-Z][A-Za-z]+\d{0,4}",  # camelcase hashtags like #ICMRES2026
    )),
    re.IGNORECASE,
)


def _source_is_editorial(source: str | None) -> bool:
    """True iff `source` is a paid editorial wire eligible for triage bypass.

    Prefix-match against `TRIAGE_BYPASS_SOURCE_PREFIXES`. A source matches
    if it equals the prefix exactly OR starts with the prefix (so newsletter
    variants like "Reuters Daily Briefing", "Bloomberg Markets Briefing",
    or "FT Briefing International" all match without listing each variant
    explicitly).
    """
    s = (source or "").strip()
    if not s:
        return False
    return any(
        s == p.rstrip() or s.startswith(p)
        for p in TRIAGE_BYPASS_SOURCE_PREFIXES
    )


# Triage bucket labels. `Literal` would be tighter but the codebase uses
# string sentinels broadly; keep it as plain strings for now.
_TRIAGE_BUCKET_BYPASS_KEEP = "bypass_keep"
_TRIAGE_BUCKET_DEFAULT_KEEP = "default_keep"
_TRIAGE_BUCKET_DEFAULT_DROP = "default_drop"
_TRIAGE_BUCKET_NEEDS_TRIAGE = "needs_triage"

# Robotics / AI-capability override. Items whose headlines mention a robot,
# humanoid, autonomous system, or AI agent are news regardless of any
# superficial junk-pattern match (e.g. "Humanoid robot completes Beijing
# half-marathon" — the marathon framing is incidental to a capability demo).
# Mirrors the protective clause in `prompts/triage_prompt.md` for the
# Haiku-judged path. Applied as a Python-level override before the JUNK
# pattern check, since variable-width lookbehind isn't well-supported by
# Python `re` and the robotics keyword can appear before OR after the
# junk match in the headline.
_TRIAGE_ROBOTICS_OVERRIDE = re.compile(
    r"\b(?:robot|robots|robotic|humanoid|autonomous|ai\s+agent)\b",
    re.IGNORECASE,
)


def _triage_classify(item: dict) -> str:
    """Classify an item into one of four triage buckets BEFORE the LLM call.

    Returns one of:
      - "bypass_keep"   — editorial source AND hard-news pattern matches.
                          Auto-keep, skip Haiku entirely. (Existing bypass.)
      - "default_keep"  — editorial source AND no junk pattern matches.
                          Auto-keep under inverted-default policy. The
                          assumption: paid wires don't publish junk under
                          headline news, so absent an explicit junk shape,
                          KEEP and let downstream stages filter.
      - "default_drop"  — editorial source AND junk pattern matches.
                          Auto-drop without an LLM call (sports / lifestyle /
                          ceremonial shapes — unambiguous).
      - "needs_triage"  — non-editorial source. Runs through the existing
                          Haiku triage path with the existing prompt.

    The asymmetry matches the cost structure: missing a hard-news item from
    a paid wire is much worse than admitting a piece of editorial commentary
    that gatekeeper will deselect anyway.
    """
    source = item.get("source") or item.get("source_name") or ""
    headline = item.get("headline") or ""
    if not _source_is_editorial(source):
        return _TRIAGE_BUCKET_NEEDS_TRIAGE
    if not headline:
        return _TRIAGE_BUCKET_NEEDS_TRIAGE
    # Robotics override: a robot/humanoid/autonomous/AI-agent capability
    # demo is news regardless of incidental sports/lifestyle framing
    # ("Humanoid robot completes Beijing half-marathon"). Applied BEFORE
    # the junk check so the marathon clause doesn't drop it.
    if _TRIAGE_ROBOTICS_OVERRIDE.search(headline):
        return _TRIAGE_BUCKET_DEFAULT_KEEP
    if TRIAGE_JUNK_PATTERN.search(headline):
        # Junk match — but hard-news markers OVERRIDE the drop for
        # editorial wires. Narrow-purpose override: $X billion / €Xbn /
        # £Xm amounts, percentages, layoffs/acquisition/sanction/indict.
        # See _TRIAGE_HARD_NEWS_OVERRIDE for the full list.
        if _TRIAGE_HARD_NEWS_OVERRIDE.search(headline):
            return _TRIAGE_BUCKET_BYPASS_KEEP
        return _TRIAGE_BUCKET_DEFAULT_DROP
    # No junk match — inverted default does the work. Editorial wires
    # auto-keep every headline that isn't unambiguously sports/lifestyle/
    # ceremonial. Diplomacy / military / personnel / M&A / funding /
    # regulatory all reach this branch via default_keep without any
    # pattern enumeration.
    return _TRIAGE_BUCKET_DEFAULT_KEEP


def _is_triage_bypass_eligible(item: dict) -> bool:
    """Backward-compatible: True iff bucket is `bypass_keep`.

    Existing callers and tests expect a single boolean signal for "skips
    Haiku triage entirely." With the inverted-default rollout this is no
    longer the only auto-keep path (`default_keep` also skips Haiku), but
    the tests for the original bypass shape still need the narrow signal.
    """
    return _triage_classify(item) == _TRIAGE_BUCKET_BYPASS_KEEP


def _partition_triage_bypass(
    items: list[dict],
) -> tuple[set[int], list[dict], dict[int, int]]:
    """Backward-compatible 2-bucket partition: (auto-keep, needs-triage).

    Combines `bypass_keep` AND `default_keep` AND `default_drop` into the
    "skip Haiku" set so callers don't need to know about the 4-bucket
    classification. The `default_drop` items are emitted as drops by
    `_save_triage_drops` via the auxiliary `_partition_triage_buckets`
    call; this thin wrapper preserves the original signature.
    """
    auto_keep_or_drop, triage_items, local_to_global = (
        set(), [], {}
    )
    for global_idx, item in enumerate(items):
        bucket = _triage_classify(item)
        if bucket == _TRIAGE_BUCKET_NEEDS_TRIAGE:
            local_to_global[len(triage_items)] = global_idx
            triage_items.append(item)
        elif bucket in (_TRIAGE_BUCKET_BYPASS_KEEP, _TRIAGE_BUCKET_DEFAULT_KEEP):
            auto_keep_or_drop.add(global_idx)
        # default_drop falls through — it's neither auto-kept nor sent to
        # Haiku. Caller's downstream `kept` set therefore excludes it,
        # matching production "drop" semantics.
    return auto_keep_or_drop, triage_items, local_to_global


def _partition_triage_buckets(
    items: list[dict],
) -> tuple[set[int], set[int], set[int], list[dict], dict[int, int]]:
    """Full 4-bucket partition for the inverted-triage path.

    Returns ``(bypass_keep, default_keep, default_drop, needs_triage_items,
    local_to_global)``:
      - ``bypass_keep``   — global indices auto-kept via hard-news bypass.
      - ``default_keep``  — global indices auto-kept via inverted default.
      - ``default_drop``  — global indices auto-dropped via junk pattern.
      - ``needs_triage_items`` — items going through the Haiku triage path,
        indexed locally 0..len-1.
      - ``local_to_global`` — map from local idx in needs_triage_items
        back to the global idx in `items`.
    """
    bypass_keep: set[int] = set()
    default_keep: set[int] = set()
    default_drop: set[int] = set()
    triage_items: list[dict] = []
    local_to_global: dict[int, int] = {}
    for global_idx, item in enumerate(items):
        bucket = _triage_classify(item)
        if bucket == _TRIAGE_BUCKET_BYPASS_KEEP:
            bypass_keep.add(global_idx)
        elif bucket == _TRIAGE_BUCKET_DEFAULT_KEEP:
            default_keep.add(global_idx)
        elif bucket == _TRIAGE_BUCKET_DEFAULT_DROP:
            default_drop.add(global_idx)
        else:  # _TRIAGE_BUCKET_NEEDS_TRIAGE
            local_to_global[len(triage_items)] = global_idx
            triage_items.append(item)
    return bypass_keep, default_keep, default_drop, triage_items, local_to_global


async def _triage_single_call(
    chunk: list[dict],
    client: anthropic.AsyncAnthropic,
    *,
    label: str,
    offset: int,
) -> tuple[set[int], dict]:
    """Run one Haiku triage call for a single chunk.

    Returns ``(kept_global_indices, chunk_log)`` where:
      - ``kept_global_indices`` is a set of 0-based indices INTO THE
        ORIGINAL items list (i.e. local indices have been offset back
        to global).
      - ``chunk_log`` is the per-chunk attempt diagnostics for the
        merged ``triage_output_{date}.json`` file.

    Fails open on API/parse errors: returns ALL global indices for the
    chunk so a single-chunk failure can't drop legitimate items from
    the pipeline. Same fail-open philosophy as the legacy single-call
    triage — triage is a coarse pre-filter.
    """
    if not chunk:
        return set(), {"label": label, "input_count": 0, "kept_count": 0,
                       "status": "empty"}

    # Build chunk-local 1-based numbered list. The model sees indices
    # 1..len(chunk); we map them back to global via `offset` after parse.
    headline_list = "\n".join(
        _build_triage_line(i, item) for i, item in enumerate(chunk)
    )
    chunk_log: dict = {
        "label": label,
        "input_count": len(chunk),
        "approx_input_chars": len(headline_list),
        "approx_input_tokens_estimate": math.ceil(len(headline_list) / 4),
        "status": "pending",
        "attempts": [],
    }
    triage_system = load_prompt("triage_prompt.md")
    fail_open_keep_set = {offset + i for i in range(len(chunk))}

    correction = ""
    for attempt in range(2):
        attempt_log = {
            "attempt": attempt + 1,
            "correction_applied": bool(correction),
            "model": "claude-haiku-4-5-20251001",
        }
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4000,
                system=triage_system,
                messages=[{"role": "user", "content": headline_list + correction}],
                timeout=120,
            )
        except Exception as e:
            attempt_log["request_error"] = str(e)
            chunk_log["attempts"].append(attempt_log)
            chunk_log["status"] = "request_failed_open"
            chunk_log["error"] = str(e)
            chunk_log["kept_count"] = len(chunk)
            logger.warning(
                f"Triage [{label}] request failed (non-fatal, passing chunk through): {e}"
            )
            return fail_open_keep_set, chunk_log

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        attempt_log["raw_response"] = raw
        attempt_log["raw_response_chars"] = len(raw)

        try:
            parsed = safe_parse_json(raw)
            attempt_log["parsed_top_level_type"] = type(parsed).__name__
            keep_indices_local = _parse_triage_keep_indices(parsed)
            # Local 1-based → 0-based → global 0-based via offset.
            keep_set_global = {
                offset + (idx - 1)
                for idx in keep_indices_local
                if isinstance(idx, int) and 1 <= idx <= len(chunk)
            }
            chunk_log["attempts"].append(attempt_log)
            chunk_log["status"] = "ok"
            chunk_log["kept_count"] = len(keep_set_global)
            chunk_log["dropped_count"] = len(chunk) - len(keep_set_global)
            return keep_set_global, chunk_log

        except ValueError as e:
            attempt_log["parse_error"] = str(e)
            chunk_log["attempts"].append(attempt_log)
            if attempt == 0:
                logger.warning(
                    f"Triage [{label}] parse failed on attempt 1: {e}. Retrying..."
                )
                correction = (
                    "\n\nCRITICAL RETRY INSTRUCTION:\n"
                    "Return ONLY a JSON array of 1-based integer indices to KEEP.\n"
                    "Do not wrap the array in an object.\n"
                    "Example: [1, 2, 5]"
                )
                continue
            # Both attempts failed parsing. Fail open so the chunk's items
            # pass through to the downstream content filter rather than
            # dropping a whole batch on a JSON glitch.
            chunk_log["status"] = "parse_failed_open"
            chunk_log["error"] = str(e)
            chunk_log["kept_count"] = len(chunk)
            logger.warning(
                f"Triage [{label}] parse failed twice; passing chunk through (fail-open)."
            )
            return fail_open_keep_set, chunk_log

    return fail_open_keep_set, chunk_log


async def triage_collected_items(
    items: list[dict],
    client: anthropic.AsyncAnthropic,
) -> list[dict]:
    """Quick Haiku triage to drop obviously irrelevant items before dedup.

    Items eligible for the source-aware bypass (paid editorial wires
    with hard-news headlines — see `_is_triage_bypass_eligible`) are
    auto-kept and skip the LLM call entirely. Everything else flows
    through the normal triage path:

      - Fast path: ``len(triage_items) <= TRIAGE_SINGLE_CALL_THRESHOLD``
        runs a single Haiku call (no parallelism overhead).
      - Chunked path: otherwise, split into ``TRIAGE_CHUNK_SIZE``
        batches and run in parallel via
        ``asyncio.Semaphore(TRIAGE_CONCURRENCY)`` + ``gather``. Each
        chunk uses the existing prompt and returns 1-based local
        indices to KEEP.

    Returns the kept items in original order (bypass + LLM-kept merged
    by original index).

    After primary triage finishes, a sanity-check sub-pass re-scores a
    random sample of dropped items with an inverse Haiku prompt. When
    ``TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL`` is enabled (default true),
    items from `TRIAGE_BYPASS_SOURCES` that the inverse prompt rescues
    are auto-restored to the kept set. The disagreement-rate alert is
    preserved as before.
    """
    if not items:
        return items

    today = get_today_date()

    # 4-bucket triage classifier (post-2026-04-27 inverted-default fix):
    #   bypass_keep   — editorial source + hard-news pattern -> auto-keep
    #   default_keep  — editorial source + no junk pattern -> auto-keep
    #                   (NEW: inverted default for paid wires)
    #   default_drop  — editorial source + junk pattern -> auto-drop
    #   needs_triage  — non-editorial source -> existing Haiku path
    (
        bypass_keep, default_keep, default_drop, triage_items, local_to_global
    ) = _partition_triage_buckets(items)
    bypass_count = len(bypass_keep)
    default_keep_count = len(default_keep)
    default_drop_count = len(default_drop)

    # Auto-keep set: union of bypass + default-keep. These items skip the
    # Haiku call entirely.
    auto_keep_set: set[int] = bypass_keep | default_keep

    if not triage_items:
        # All items routed to auto-keep / default-drop buckets. Skip Haiku.
        triage_log = {
            "total_input": len(items),
            "bypassed_count": bypass_count,
            "default_keep_count": default_keep_count,
            "default_drop_count": default_drop_count,
            "kept": len(auto_keep_set),
            "dropped": default_drop_count,
            "status": "all-bucketed",
            "chunked": False,
            "chunk_count": 0,
            "chunk_size": TRIAGE_CHUNK_SIZE,
            "concurrency": 0,
            "per_chunk": [],
        }
        save_intermediate(f"triage_output_{today}.json", triage_log)
        _save_triage_drops(items, auto_keep_set, today,
                           default_drop_set=default_drop)
        return [item for i, item in enumerate(items) if i in auto_keep_set]

    # Fast path — single call for small inputs (no parallelism overhead).
    if len(triage_items) <= TRIAGE_SINGLE_CALL_THRESHOLD:
        local_keep_set, chunk_log = await _triage_single_call(
            triage_items, client, label="single", offset=0
        )
        chunk_telemetry = [chunk_log]
        triage_status = chunk_log.get("status", "ok")
        chunked = False
        chunk_count = 1
        concurrency = 1
    else:
        # Chunked path — split into TRIAGE_CHUNK_SIZE batches, run in
        # parallel. Offset is local-to-`triage_items`, not global, so the
        # per-chunk keep_set is in `triage_items` index space.
        sem = asyncio.Semaphore(TRIAGE_CONCURRENCY)
        chunks = [
            (start, triage_items[start:start + TRIAGE_CHUNK_SIZE])
            for start in range(0, len(triage_items), TRIAGE_CHUNK_SIZE)
        ]

        async def _run_one(start: int, chunk: list[dict]):
            async with sem:
                return await _triage_single_call(
                    chunk, client, label=f"chunk-{start}", offset=start
                )

        chunk_outputs = await asyncio.gather(
            *[_run_one(s, c) for s, c in chunks]
        )

        local_keep_set = set()
        chunk_telemetry = []
        for kept_local_indices, chunk_log in chunk_outputs:
            local_keep_set.update(kept_local_indices)
            chunk_telemetry.append(chunk_log)
        triage_status = "ok"
        chunked = True
        chunk_count = len(chunks)
        concurrency = TRIAGE_CONCURRENCY

    # Map local kept indices to global, then union with the auto-keep set
    # (bypass + default_keep). default_drop indices are intentionally NOT
    # in keep_set, so `_save_triage_drops` records them as dropped.
    keep_set: set[int] = set(auto_keep_set)
    for local_i in local_keep_set:
        keep_set.add(local_to_global[local_i])

    kept = [item for i, item in enumerate(items) if i in keep_set]

    triage_log = {
        "total_input": len(items),
        "bypassed_count": bypass_count,
        "default_keep_count": default_keep_count,
        "default_drop_count": default_drop_count,
        "kept": len(kept),
        "dropped": len(items) - len(kept),
        "status": triage_status,
        "chunked": chunked,
        "chunk_count": chunk_count,
        "chunk_size": TRIAGE_CHUNK_SIZE,
        "concurrency": concurrency,
        "per_chunk": chunk_telemetry,
    }
    save_intermediate(f"triage_output_{today}.json", triage_log)
    _save_triage_drops(items, keep_set, today, default_drop_set=default_drop)

    if chunked:
        print(
            f"{timestamp()} Triage (chunked): {len(items)} items "
            f"({bypass_count} bypassed, {default_keep_count} default-kept, "
            f"{default_drop_count} default-dropped, {len(triage_items)} triaged "
            f"across {chunk_count} chunk(s)) → {len(kept)} kept, "
            f"{len(items) - len(kept)} dropped"
        )

    # Sanity-check pass — secondary verdict on a random sample of dropped
    # items. Stratifies sampling toward editorial-source drops and (when
    # `TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL=true`) auto-rescues high-
    # confidence inverse-prompt KEEPs whose source is in
    # `TRIAGE_BYPASS_SOURCES`. Rescued indices are added to keep_set
    # in-place by `triage_sanity_check`.
    await triage_sanity_check(items, keep_set, client, today)

    # Re-materialise kept list after potential sanity-check rescues.
    return [item for i, item in enumerate(items) if i in keep_set]


def _save_triage_drops(
    items: list[dict],
    keep_set: set[int],
    today: str,
    default_drop_set: set[int] | None = None,
) -> None:
    """Persist triage drops to the shared `dropped_by_*_{date}.json`
    pattern so ingest_brief picks them up for the admin Drops view.

    `default_drop_set` (optional) marks indices auto-dropped by the
    inverted-default JUNK pattern (post-2026-04-27). These get a distinct
    drop_reason so /admin/drops can tell them apart from Haiku-judged
    drops — useful for tuning the JUNK pattern without sifting through
    Haiku-attributed drops.
    """
    default_drop_set = default_drop_set or set()
    triage_drop_rows = [
        {
            "headline": items[i].get("headline", ""),
            "source": items[i].get("source") or items[i].get("source_name"),
            "source_url": items[i].get("source_url"),
            "drop_reason": (
                "Triage: editorial-source junk-pattern match"
                if i in default_drop_set
                else "Triage: removed as obvious non-news junk"
            ),
            "index": i,
        }
        for i in range(len(items))
        if i not in keep_set
    ]
    save_intermediate(
        f"dropped_by_triage_{today}.json",
        {
            "dropped_count": len(triage_drop_rows),
            "dropped": triage_drop_rows,
        },
    )


def _parse_triage_keep_indices(payload) -> list[int]:
    """Accept either the original array contract or a dict wrapper around it."""
    if isinstance(payload, list):
        if all(isinstance(idx, int) for idx in payload):
            return payload
        raise ValueError("Expected an array of integers from triage")

    if isinstance(payload, dict):
        for key in ("keep", "keep_indices", "indices", "indices_to_keep", "relevant_indices"):
            value = payload.get(key)
            if isinstance(value, list) and all(isinstance(idx, int) for idx in value):
                return value

        list_values = [
            value
            for value in payload.values()
            if isinstance(value, list) and all(isinstance(idx, int) for idx in value)
        ]
        if len(list_values) == 1:
            return list_values[0]

    raise ValueError(f"Unsupported triage JSON shape: {type(payload).__name__}")


# Sanity check: re-score N random dropped items with an inverse Haiku
# prompt. Stratifies the sample toward editorial-source drops and
# (when `TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL=true`, default) auto-rescues
# high-confidence inverse KEEPs whose source is in TRIAGE_BYPASS_SOURCES.
_TRIAGE_SANITY_DEFAULT_ENABLED = "true"
_TRIAGE_SANITY_AUTO_RESCUE_DEFAULT = "true"


def _build_sanity_check_sample_indices(
    dropped_pool: list[dict],
    sample_size: int,
) -> list[int]:
    """Stratified sample: floor share from editorial-source drops if any exist.

    Editorial-source drops are exactly the failure mode this stage is
    meant to catch (Meta layoff, Dubai $9B Metro, DOJ marijuana on
    2026-04-24). When they exist in the drop pool, we want them sampled
    disproportionately so the inverse-prompt has a chance to flag them.

    Args:
        dropped_pool: list of dicts ``{"global_index": int, "is_editorial": bool}``.
        sample_size: total sample size cap.
    Returns:
        List of `global_index` values, length <= ``sample_size``.
    """
    editorial = [d["global_index"] for d in dropped_pool if d["is_editorial"]]
    other = [d["global_index"] for d in dropped_pool if not d["is_editorial"]]

    if not editorial:
        # No editorial-source drops — uniform sample from `other`.
        return random.sample(other, min(sample_size, len(other)))

    editorial_target = max(
        1, int(sample_size * TRIAGE_SANITY_EDITORIAL_SAMPLE_FLOOR)
    )
    editorial_take = min(editorial_target, len(editorial))
    other_take = min(sample_size - editorial_take, len(other))
    chosen_editorial = random.sample(editorial, editorial_take)
    chosen_other = random.sample(other, other_take) if other_take else []

    # If the sample isn't full (small `other` pool), back-fill from the
    # remaining editorial pool.
    leftover = sample_size - editorial_take - other_take
    if leftover > 0:
        pool_extra = [g for g in editorial if g not in set(chosen_editorial)]
        extra = random.sample(pool_extra, min(leftover, len(pool_extra)))
    else:
        extra = []

    return chosen_editorial + chosen_other + extra


async def triage_sanity_check(
    items: list[dict],
    keep_set: set[int],
    client: anthropic.AsyncAnthropic,
    today: str,
    sample_size: int = TRIAGE_SANITY_SAMPLE_SIZE,
) -> None:
    """Re-score a sample of triage drops with an inverse prompt.

    Reads ``TRIAGE_SANITY_CHECK_ENABLED`` env var (default true). When
    enabled, samples up to ``sample_size`` items from the dropped pool,
    stratified to favour editorial-source drops (the failure mode we
    care about most), and sends them through
    ``prompts/triage_sanity_check_prompt.md`` (inverse-stance: "could
    be news" vs "definitely noise").

    Auto-rescue: when ``TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL`` is true
    (default), items the inverse prompt rescues whose source is in
    ``TRIAGE_BYPASS_SOURCES`` are added to ``keep_set`` (mutated
    in-place) so the caller's downstream ``kept`` list reflects the
    rescue. Rescues are logged for human review.

    Always writes ``triage_sanity_check_{today}.json`` with the full
    sample, suspected-FP rows, and per-item rescue status. Logs a
    warning when the disagreement rate exceeds
    ``TRIAGE_SANITY_ALERT_THRESHOLD``.

    Args:
        items: original ordered list of items.
        keep_set: set of global indices currently kept; mutated in-place
            when auto-rescue triggers a rescue.
        client: AsyncAnthropic client.
        today: date stamp for the artifact filename.
        sample_size: maximum sample size for the inverse-prompt call.
    """
    if os.getenv(
        "TRIAGE_SANITY_CHECK_ENABLED", _TRIAGE_SANITY_DEFAULT_ENABLED
    ).lower() != "true":
        return

    auto_rescue_enabled = os.getenv(
        "TRIAGE_SANITY_AUTO_RESCUE_EDITORIAL", _TRIAGE_SANITY_AUTO_RESCUE_DEFAULT
    ).lower() == "true"

    # Build the dropped-index pool with editorial flag for stratification.
    # Uses prefix matching so "Reuters Daily Briefing", "Bloomberg Markets
    # Briefing" etc. count as editorial.
    dropped_pool = [
        {
            "global_index": i,
            "is_editorial": _source_is_editorial(
                items[i].get("source") or items[i].get("source_name")
            ),
        }
        for i in range(len(items))
        if i not in keep_set
    ]
    if len(dropped_pool) < sample_size:
        # Not enough drops to be meaningful; skip without saving anything.
        # Mirrors pre-stratification behaviour so callers passing an
        # explicit `sample_size` get the same "skip on tiny pool" contract.
        return

    sample_indices = _build_sanity_check_sample_indices(
        dropped_pool, sample_size,
    )
    if not sample_indices:
        return
    sample_items = [items[i] for i in sample_indices]

    sanity_system = load_prompt("triage_sanity_check_prompt.md")
    headline_block = "\n".join(
        _build_triage_line(j, item) for j, item in enumerate(sample_items)
    )

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=sanity_system,
            messages=[{"role": "user", "content": headline_block}],
            timeout=60,
        )
    except Exception as e:
        logger.warning(f"Triage sanity check API call failed (non-fatal): {e}")
        return

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = safe_parse_json(raw)
        keep_indices_local = _parse_sanity_check_verdicts(parsed)
    except ValueError as e:
        logger.warning(
            f"Triage sanity check parse failed (non-fatal): {e}; raw='{raw[:200]}'"
        )
        return

    # Items the secondary call said "could be news" but primary triage
    # dropped → suspected false positives. Map local 1-based → global.
    # When `auto_rescue_enabled` and the source is editorial, also rescue
    # the item back into keep_set (mutated by caller).
    rescued_global: list[int] = []
    suspected_fp: list[dict] = []
    for v in keep_indices_local:
        if not isinstance(v, int) or v < 1 or v > len(sample_items):
            continue
        local_idx = v - 1
        item = sample_items[local_idx]
        global_idx = sample_indices[local_idx]
        source = (item.get("source") or item.get("source_name") or "").strip()
        is_editorial = _source_is_editorial(source)
        rescue = bool(auto_rescue_enabled and is_editorial)
        suspected_fp.append({
            "headline": item.get("headline", ""),
            "source": source,
            "source_url": item.get("source_url"),
            "primary_drop_reason": "Triage: removed as obvious non-news junk",
            "secondary_verdict": "could be news",
            "is_editorial": is_editorial,
            "rescued": rescue,
            "global_index": global_idx,
        })
        if rescue:
            rescued_global.append(global_idx)

    # Apply rescues by mutating keep_set in-place. Caller rebuilds the
    # downstream `kept` list from keep_set after this function returns.
    for global_idx in rescued_global:
        keep_set.add(global_idx)

    sample_n = len(sample_indices)
    disagreement_rate = len(suspected_fp) / max(1, sample_n)
    alerted = disagreement_rate > TRIAGE_SANITY_ALERT_THRESHOLD
    save_intermediate(
        f"triage_sanity_check_{today}.json",
        {
            "sample_size": sample_n,
            "disagreement_count": len(suspected_fp),
            "disagreement_rate": disagreement_rate,
            "alert_threshold": TRIAGE_SANITY_ALERT_THRESHOLD,
            "alerted": alerted,
            "auto_rescue_enabled": auto_rescue_enabled,
            "rescued_count": len(rescued_global),
            "suspected_false_positives": suspected_fp,
            "raw_response": raw[:500],
        },
    )

    if rescued_global:
        rescued_lines = "\n".join(
            f"  - [{fp['source']}] {fp['headline']}"
            for fp in suspected_fp if fp.get("rescued")
        )
        logger.warning(
            "Triage sanity check: rescued %d editorial-source drop(s) via "
            "inverse-prompt secondary verdict:\n%s",
            len(rescued_global),
            rescued_lines,
        )
        print(
            f"{timestamp()} \U0001f198 Triage rescue: "
            f"{len(rescued_global)} editorial-source drop(s) restored to keep set"
        )

    if alerted:
        logger.warning(
            "Triage sanity check: %d/%d sampled drops flagged as 'could be news' "
            "by secondary call (%.0f%% disagreement, threshold %.0f%%). "
            "Review backend/output/triage_sanity_check_%s.json.",
            len(suspected_fp),
            sample_n,
            disagreement_rate * 100,
            TRIAGE_SANITY_ALERT_THRESHOLD * 100,
            today,
        )
        print(
            f"{timestamp()} \u26a0\ufe0f  Triage sanity check: "
            f"{len(suspected_fp)}/{sample_n} drops may be false positives "
            f"({disagreement_rate * 100:.0f}% disagreement)"
        )


def _parse_sanity_check_verdicts(payload) -> list[int]:
    """Parse the secondary sanity-check response into a list of 1-based
    keep indices.

    Defensively accepts:
      - bare list of integers (same as primary triage output shape)
      - {"keep_indices": [...]} (the documented prompt shape)
      - {"keep": [...]} / {"indices": [...]} variants

    Raises ``ValueError`` if no list of integers can be extracted.
    """
    return _parse_triage_keep_indices(payload)


def _sanitize_content_filter_items(items: list[dict]) -> list[dict]:
    keep_fields = {
        "headline",
        "source",
        "source_url",
        "date",
        "summary",
        "category",
        "also_covered_by",
    }
    BODY_EXCERPT_MAX = 500
    sanitized = []
    for index, item in enumerate(items):
        clean = {key: value for key, value in item.items() if key in keep_fields}
        clean["id"] = index
        # Include a truncated body excerpt when the raw_content provides
        # substance beyond the headline. This lets the content filter
        # evaluate article body text (e.g. WAM subtitles) rather than
        # judging solely on headline tone.
        raw = item.get("raw_content", "")
        headline = item.get("headline", "")
        if raw and raw.strip().lower() != headline.strip().lower() and len(raw) > len(headline):
            clean["body_excerpt"] = raw[:BODY_EXCERPT_MAX]
        sanitized.append(clean)
    return sanitized


def _normalize_content_filter_verdict(verdict: dict, batch_start: int, batch_end: int) -> dict:
    normalized = dict(verdict)

    local_index = normalized.get("index")
    global_id = normalized.get("id")
    if isinstance(global_id, int):
        if not (batch_start <= global_id < batch_end) and isinstance(local_index, int):
            normalized["id"] = batch_start + local_index
    elif isinstance(local_index, int):
        normalized["id"] = batch_start + local_index

    duplicate_of = normalized.get("duplicate_of")
    if isinstance(duplicate_of, int) and not (batch_start <= duplicate_of < batch_end):
        normalized["duplicate_of"] = batch_start + duplicate_of

    return normalized


def _content_filter_batch_ranges(total_items: int) -> list[tuple[int, int]]:
    """Split content-filter work into balanced ranges, targeting 40-50 items when possible."""
    if total_items <= 0:
        return []
    if total_items <= CONTENT_FILTER_MAX_BATCH_SIZE:
        return [(0, total_items)]

    min_batches = math.ceil(total_items / CONTENT_FILTER_MAX_BATCH_SIZE)
    max_batches = total_items // CONTENT_FILTER_MIN_BATCH_SIZE

    if min_batches <= max_batches:
        batch_count = min_batches
    else:
        # Some totals (for example 51-79) cannot be split into all-40-50 batches.
        # Fall back to evenly sized chunks that stay close to the target batch size.
        batch_count = max(1, round(total_items / CONTENT_FILTER_TARGET_BATCH_SIZE))
        batch_count = max(batch_count, min_batches)

    base_size, remainder = divmod(total_items, batch_count)
    ranges: list[tuple[int, int]] = []
    start = 0
    for batch_index in range(batch_count):
        batch_size = base_size + (1 if batch_index < remainder else 0)
        end = start + batch_size
        ranges.append((start, end))
        start = end
    return ranges


async def run_content_filter_batched(
    client: anthropic.AsyncAnthropic,
    items: list[dict],
    prompt_filename: str = "content_filter_prompt.md",
) -> tuple[list[dict], list[dict], list[dict], dict, list[dict]]:
    """Run the content filter in smaller batches to avoid timeout cascades.

    `prompt_filename` defaults to the production prompt but can be pointed at
    an alternate prompt file (absolute path or relative to PROMPTS_DIR) by
    the shadow-replay harness in backend/scripts/content_filter_shadow_replay.py.
    """
    sanitized = _sanitize_content_filter_items(items)
    all_verdicts: list[dict] = []
    content_filter_drops: list[dict] = []
    batch_summaries: list[dict] = []
    total_input_tokens = 0
    total_output_tokens = 0
    batch_ranges = _content_filter_batch_ranges(len(sanitized))

    for batch_number, (batch_start, batch_end) in enumerate(batch_ranges, start=1):
        batch = sanitized[batch_start:batch_end]
        batch_json = json.dumps(batch, indent=2, ensure_ascii=False)
        cf_correction = ""
        batch_result = None
        batch_error: Exception | None = None

        print(
            f"{timestamp()}   Content Filter batch {batch_number}: "
            f"items {batch_start + 1}-{batch_end}"
        )

        for attempt in range(2):
            if attempt > 0:
                wait = 2 + random.uniform(0, 1)
                print(f"{timestamp()}     Backing off {wait:.1f}s before batch retry...")
                await asyncio.sleep(wait)
            try:
                cf_prompt = load_prompt(
                    prompt_filename,
                    items_json=batch_json,
                ) + cf_correction
                batch_result, cf_usage = await run_content_filter(client, cf_prompt)
                total_input_tokens += cf_usage["input_tokens"]
                total_output_tokens += cf_usage["output_tokens"]
                break
            except Exception as e:
                batch_error = e
                if attempt == 0:
                    logger.warning(
                        "Content Filter batch %s attempt 1 failed: %s. Retrying...",
                        batch_number,
                        e,
                    )
                    print(
                        f"{timestamp()}     ⚠️  Content Filter batch {batch_number} "
                        f"failed, retrying..."
                    )
                    cf_correction = build_retry_correction("content_filter", e)
                else:
                    logger.error(
                        "Content Filter batch %s failed after 2 attempts: %s",
                        batch_number,
                        e,
                        exc_info=True,
                    )

        if not batch_result:
            print(
                f"{timestamp()}     ⚠️  Content Filter batch {batch_number} failed after "
                "2 attempts. Passing this batch through unfiltered."
            )
            batch_summaries.append(
                {
                    "batch": batch_number,
                    "start_index": batch_start,
                    "end_index": batch_end - 1,
                    "status": "failed_open",
                    "error": str(batch_error) if batch_error else "unknown",
                    "item_count": len(batch),
                }
            )
            continue

        normalized_verdicts = [
            _normalize_content_filter_verdict(verdict, batch_start, batch_end)
            for verdict in batch_result.get("verdicts", [])
        ]
        all_verdicts.extend(normalized_verdicts)
        batch_summaries.append(
            {
                "batch": batch_number,
                "start_index": batch_start,
                "end_index": batch_end - 1,
                "status": "ok",
                "item_count": len(batch),
                "verdict_count": len(normalized_verdicts),
            }
        )

    verdict_map = {}
    for verdict in all_verdicts:
        key = verdict.get("id") if verdict.get("id") is not None else verdict.get("index")
        if key is not None:
            verdict_map[key] = verdict

    news_items = []
    for index, item in enumerate(items):
        verdict = verdict_map.get(index)
        if verdict:
            # New prompt emits `decision` ("KEEP"/"DROP"). Legacy prompts emit
            # `keep` (bool) or `verdict` ("NEWS"/"NOT_NEWS"). Prefer the new
            # field and fall back for rollback/shadow-mode compatibility.
            decision = verdict.get("decision")
            if decision == "DROP":
                should_drop = True
            elif decision == "KEEP":
                should_drop = False
            elif verdict.get("keep") is not None:
                should_drop = not verdict["keep"]
            else:
                should_drop = verdict.get("verdict") == "NOT_NEWS"
        else:
            should_drop = False

        if should_drop:
            # The new prompt folds date/duplicate/category concerns out of
            # scope (see prompts/content_filter_prompt.md) — a DROP verdict
            # from the new prompt always means "not a concrete news event",
            # which we label `news_test_fail` for continuity with the legacy
            # audit stream. Legacy fields (duplicate_of, category) are still
            # surfaced when emitted, for the transitional period where old
            # and new outputs coexist.
            reasons = []
            if verdict.get("decision") == "DROP" or verdict.get("news_test") == "fail":
                reasons.append("news_test_fail")
            if verdict.get("duplicate_of") is not None:
                reasons.append(f"duplicate_of_{verdict['duplicate_of']}")
            if verdict.get("category"):
                reasons.append(verdict["category"])
            if not reasons:
                reasons.append("filtered")
            reason_str = ", ".join(reasons)

            # Prefer the new `evaluation` field (one-sentence structured
            # reasoning) for audit context; fall back to legacy `reason`.
            explanation = verdict.get("evaluation") or verdict.get("reason", "")

            content_filter_drops.append(
                {
                    "headline": item.get("headline", ""),
                    "source": item.get("source"),
                    "source_url": item.get("source_url"),
                    "composite_score": None,
                    "drop_reason": f"Content filter: {reason_str} — {explanation}",
                }
            )
            print(f"{timestamp()}   FILTERED [{reason_str}]: {item.get('headline', '')[:60]}")
        else:
            news_items.append(item)

    usage = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
    }
    return news_items, content_filter_drops, all_verdicts, usage, batch_summaries




def ensure_all_sections(final_brief: dict, today: str) -> dict:
    """Ensure all 5 canonical sections are represented in the final brief.

    For any section with 0 items, inserts a placeholder item so the
    frontend always renders all sections.
    """
    items = final_brief.get("items", [])

    normalized_items: list[dict] = []
    rejected_unknown = 0
    for item in items:
        normalized = normalize_section_name(item.get("section"))
        if not normalized:
            rejected_unknown += 1
            logger.warning(
                "Final assembly rejected unknown section '%s' for '%s'",
                item.get("section"),
                item.get("headline", "")[:80],
            )
            continue
        item["section"] = normalized
        normalized_items.append(item)
    items = normalized_items
    present_sections = {item.get("section") for item in items}

    for section in BRIEF_SECTIONS:
        if section not in present_sections:
            slug = section.lower().replace(" & ", "-").replace(" ", "-")
            items.append({
                "id": f"{today}-empty-{slug}",
                "rank": 999,
                "section": section,
                "headline": "No relevant news to report",
                "source_domain": None,
                "source_name": None,
                "source_url": None,
                "additional_sources": [],
                "main_bullet": "No items met the relevance threshold for this section today.",
                "context": None,
                "implication": None,
                "entities": [],
                "composite_score": 0,
                "significance_level": None,
                "cluster": None,
                "continuity": None,
                "is_model_release": False,
                "model_release_data": None,
                "depth": "placeholder",
                "is_placeholder": True,
            })

    final_brief["items"] = items

    # Recount section_counts from actual items (Editor counts may be stale
    # after merging brief items that bypassed the Editor).
    metadata = final_brief.get("brief_metadata", {})
    real_items = [i for i in items if not i.get("is_placeholder")]
    section_counts = {section: 0 for section in BRIEF_SECTIONS}
    for item in real_items:
        sec = item.get("section", "")
        if sec in section_counts:
            section_counts[sec] += 1
    real_item_ids = {
        str(item.get("id") or "").strip()
        for item in real_items
        if str(item.get("id") or "").strip()
    }
    metadata["section_counts"] = section_counts
    metadata["total_items"] = len(real_items)
    if real_items and metadata.get("lead_story_id") not in real_item_ids:
        metadata["lead_story_id"] = real_items[0].get("id")
    metadata["rejected_unknown_sections"] = rejected_unknown
    final_brief["brief_metadata"] = metadata

    return final_brief


def validate_final_brief(brief: dict) -> list[str]:
    """Run quality checks on the final brief. Returns list of warning strings."""
    warnings = []
    for item in brief.get("items", []):
        if item.get("is_placeholder"):
            continue
        headline = item.get("headline", "")

        # Headline length
        if len(headline.split()) > 15:
            warnings.append(f"Headline >15 words: '{headline[:60]}...'")

        # Source URL present
        if not item.get("source_url") and item.get("source_origin") != "newsletter":
            warnings.append(f"Missing source_url: '{headline[:60]}'")

        # Main bullet present and substantive
        main_bullet = item.get("main_bullet", "")
        if not main_bullet or len(main_bullet.split()) < 10:
            warnings.append(f"Weak main_bullet (<10 words): '{headline[:60]}'")

        # Word count vs depth budget
        depth = item.get("depth", "standard")
        budgets = {"full": 160, "standard": 100, "brief": 70}
        if depth in budgets:
            total_words = len(" ".join(filter(None, [
                main_bullet,
                item.get("context", ""),
                item.get("implication", ""),
            ])).split())
            if total_words > budgets[depth]:
                warnings.append(
                    f"Over budget ({total_words}w, depth={depth}): '{headline[:50]}'"
                )

    return warnings


async def run_editor_in_chief(
    client,
    all_gw_items: list[dict],
    today: str,
) -> tuple[list[dict], dict]:
    """Run Editor-in-Chief to select items for the curation slate.

    Returns (surfaced_items, usage). surfaced_items have rank attached.
    """
    # Strip large fields to keep prompt within budget
    lightweight = []
    for item in all_gw_items:
        light = {k: v for k, v in item.items()
                 if k not in ("raw_content", "additional_context", "enriched_sources",
                              "enriched_facts", "compiled_packet")}
        lightweight.append(light)

    items_json = json.dumps(lightweight, indent=2, ensure_ascii=False)

    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "editor_in_chief_prompt.md"
    raw_prompt = prompt_path.read_text(encoding="utf-8")
    prompt_text = raw_prompt.replace("{all_items_json}", items_json)

    response = await client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=600,
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    text = "\n".join(b.text for b in response.content if b.type == "text")
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    parsed = safe_parse_json(cleaned)

    # Match selected IDs back to full ghostwriter items
    gw_by_id = {str(i.get("id", "")).strip(): i for i in all_gw_items}
    selected_info = parsed.get("selected_items", [])

    surfaced = []
    for entry in sorted(selected_info, key=lambda x: x.get("rank", 999)):
        item_id = str(entry.get("id", "")).strip()
        if item_id in gw_by_id:
            item = dict(gw_by_id[item_id])
            item["rank"] = entry.get("rank", len(surfaced) + 1)
            item["eic_selection_reason"] = entry.get("reason", "")
            surfaced.append(item)
        else:
            logger.warning("Editor-in-Chief returned unknown ID: %s", item_id)

    return surfaced, usage


async def _run_pre_gatekeeper_enrichment(all_items: list[dict]) -> int:
    """Fetch content for thin URL-only items so Gatekeeper has something to score.

    Many sources (WAM sitemap, TII, G42, Presight) only provide headlines.
    The gatekeeper penalises these for thin content before the full enricher
    runs. A quick trafilatura fetch of the source URL gives the gatekeeper a
    real summary to score. No API calls — just HTTP + HTML parsing.

    Mutates items in place: sets `raw_content` and `summary` for items whose
    source URL yields a trafilatura extract. Returns the number of items
    successfully enriched. Idempotent by construction — `is_thin` filters
    out items that already have enough content, so a second call after a
    previous enrichment only targets still-thin items.

    Called from both the normal path (after date-filter / continuity
    penalty) and the --from-stage=gatekeeper resume path (after the pre-
    Gatekeeper section classifier). The resume path would otherwise run
    Gatekeeper on un-enriched items, tanking the selection count.
    """
    PRE_GK_CONCURRENCY = 6
    PRE_GK_MAX_ITEMS = 40

    thin_with_url = [
        (i, item) for i, item in enumerate(all_items)
        if is_thin(item) and item.get("source_url")
    ]
    if not thin_with_url:
        return 0

    targets = thin_with_url[:PRE_GK_MAX_ITEMS]
    print(
        f"{timestamp()} Pre-gatekeeper enrichment: "
        f"{len(targets)} thin item(s) with URLs "
        f"(of {len(thin_with_url)} total, cap {PRE_GK_MAX_ITEMS})"
    )
    sem = asyncio.Semaphore(PRE_GK_CONCURRENCY)

    async def _prefetch(idx: int, item: dict):
        async with sem:
            return idx, await fetch_source_url(item["source_url"])

    results = await asyncio.gather(
        *[_prefetch(idx, item) for idx, item in targets],
        return_exceptions=True,
    )
    enriched_count = 0
    for result in results:
        if isinstance(result, Exception):
            continue
        idx, fetched = result
        if not fetched or not fetched.get("extract"):
            continue
        extract_text = fetched["extract"]
        all_items[idx]["raw_content"] = extract_text
        all_items[idx]["summary"] = extract_text[:300]
        enriched_count += 1
    print(
        f"{timestamp()} Pre-gatekeeper enrichment: "
        f"{enriched_count}/{len(targets)} item(s) now have content"
    )
    return enriched_count


async def run_pipeline(from_stage: str | None = None):
    """Execute the full intelligence briefing pipeline.

    Args:
        from_stage: If provided, skip stages before this one and load
                    cached intermediate results. One of: 'scout', 'gatekeeper',
                    'ghostwriter', 'editor'.
    """
    pipeline_started_at = datetime.now(GST)
    pipeline_start = time.time()
    today = get_today_date()
    total_input_tokens = 0
    total_output_tokens = 0
    manual_entry_ids_to_mark: set[str] = set()

    print(f"{timestamp()} Starting pipeline for {today}...")
    if from_stage and from_stage != "scout":
        print(f"{timestamp()} Resuming from stage: {from_stage}")

    client = anthropic.AsyncAnthropic()

    # === STEP 1: Collect articles (deterministic HTTP scrapers + Gmail API) ===
    if not from_stage or from_stage == "scout":
        print(f"{timestamp()} Running deterministic collectors (no Claude API calls)...")
        collected_articles = await run_all_collectors()

        # Split newsletter articles into individual stories via Haiku
        newsletter_articles = [a for a in collected_articles if a.category == "newsletter"]
        non_newsletter = [a for a in collected_articles if a.category != "newsletter"]
        if newsletter_articles:
            print(f"{timestamp()} Splitting {len(newsletter_articles)} newsletters via Haiku...")
            split_stories = await split_all_newsletters(client, newsletter_articles)
            collected_articles = non_newsletter + split_stories

        # === STEP 1b: Regional Research Scout (Claude + web_search) ===
        print(f"{timestamp()} Running regional research scout...")
        try:
            existing_headlines = [a.title for a in collected_articles]
            scout_articles, scout_summary = await run_regional_scout(
                client, existing_headlines
            )
            if scout_articles:
                collected_articles.extend(scout_articles)
                print(f"{timestamp()} Regional scout: {len(scout_articles)} candidates")
            else:
                print(f"{timestamp()} Regional scout: 0 candidates")
            total_input_tokens += scout_summary.get("input_tokens", 0)
            total_output_tokens += scout_summary.get("output_tokens", 0)
        except Exception as e:
            logger.warning(f"Regional research scout failed (non-fatal): {e}")
            print(f"{timestamp()} Regional scout failed (non-fatal): {e}")

        # Transform CollectedArticle → ScoutItem dict format
        all_items = []
        items_by_scout: dict[str, int] = {}
        scout_search_log: list[dict] = []

        for article in collected_articles:
            item = {
                "headline": article.title,
                "source": article.source_name,
                "source_url": article.url,
                "date": article.published_date,
                "published_at": article.published_at,
                "date_evidence": (
                    f"Published date from {article.collected_via} collector"
                    if article.published_date
                    else NO_DATE_EVIDENCE
                ),
                "summary": article.snippet,
                "raw_content": article.raw_text,
                "additional_context": None,
                "entities": [],
                "category": article.category or "",
                "significance": None,
                "also_covered_by": [],
                "source_scout": (
                    article.scout_mapping[0] if article.scout_mapping else "unknown"
                ),
            }
            all_items.append(item)
            # Count by each scout mapping (an article may map to multiple scouts)
            for scout_key in article.scout_mapping:
                items_by_scout[scout_key] = items_by_scout.get(scout_key, 0) + 1

        # No API tokens used for collection stage
        scout_search_log.append({
            "stage": "collector",
            "total_articles": len(collected_articles),
            "items_by_source": {
                src: sum(1 for a in collected_articles if a.source_name == src)
                for src in sorted(set(a.source_name for a in collected_articles))
            },
        })

        print(f"{timestamp()} All collectors complete. {len(all_items)} raw items total.")
        for sk, count in sorted(items_by_scout.items(), key=lambda x: -x[1]):
            print(f"{timestamp()}   {sk}: {count} items")

        normalized_count = normalize_scout_contract(all_items)
        if normalized_count:
            print(
                f"{timestamp()} Scout schema normalization: fixed {normalized_count} "
                f"missing/invalid field(s)"
            )

        # Persist the pre-triage payload so early-stage decisions can be replayed.
        save_intermediate(f"collected_raw_{today}.json", all_items)

        # === Required scout validation ===
        # For split scouts: fail only if ALL sub-calls returned 0 items
        failed_required = [
            sk for sk in REQUIRED_SCOUTS
            if items_by_scout.get(sk, 0) == 0
        ]
        if failed_required:
            print(f"{timestamp()} \u274c CRITICAL: Required scout(s) failed: "
                  f"{', '.join(failed_required)}")
            print(f"{timestamp()} Brief cannot proceed without UAE coverage. Aborting.")
            print(f"{timestamp()} Re-run the pipeline when API is available.")
            return False

        # === Pre-triage WAM body fill ===
        # WAM sitemap items frequently arrive with raw_content equal to the
        # headline because the article isn't on any of the listing pages
        # the collector enriches from. Thin bodies get misread as
        # "ceremonial/protocol" by Haiku triage even when substantive
        # (see 2026-04-23 MBZ-Musk incident). Fetch real bodies via
        # GetArticleBySlug before triage runs.
        wam_enrich_log = await fill_thin_wam_bodies(all_items)
        if wam_enrich_log.get("candidates"):
            print(
                f"{timestamp()} WAM pre-triage fill: "
                f"{wam_enrich_log['enriched']} enriched / "
                f"{wam_enrich_log['failed']} failed / "
                f"{wam_enrich_log['skipped']} skipped "
                f"(of {wam_enrich_log['candidates']} candidates)"
            )
        save_intermediate(f"wam_enrichment_log_{today}.json", wam_enrich_log)

        # === Haiku triage (drop obviously irrelevant items) ===
        before_triage = len(all_items)
        all_items = await triage_collected_items(all_items, client)
        num_triaged = before_triage - len(all_items)
        if num_triaged > 0:
            print(f"{timestamp()} Triage: {before_triage} → {len(all_items)} items "
                  f"({num_triaged} dropped as irrelevant)")

        # === URL-based date verification (best-effort enrichment) ===
        # Partition out sources whose collector already stamps an authoritative
        # date AND whose URLs empirically never yield a parseable meta-tag date
        # (see VERIFY_DATES_BYPASS_SOURCES for rationale). These items keep
        # their collector date and skip the HTTP fetch entirely.
        verify_bypass = [it for it in all_items if _skips_date_verify(it)]
        verify_candidates = [it for it in all_items if not _skips_date_verify(it)]
        if verify_bypass:
            bypass_sources = sorted({
                (it.get("source") or it.get("source_name") or "") for it in verify_bypass
            })
            print(
                f"{timestamp()} Skipping verify_dates for {len(verify_bypass)} "
                f"item(s) from authoritative sources: {', '.join(bypass_sources)}"
            )

        print(f"{timestamp()} Verifying publication dates via source URLs...")
        try:
            num_verified, num_fetch_failed = await verify_dates(verify_candidates)
            print(f"{timestamp()} Date verification: {num_verified} verified, "
                  f"{num_fetch_failed} unavailable "
                  f"(out of {len(verify_candidates)} candidates; "
                  f"{len(verify_bypass)} bypassed)")
        except Exception as e:
            logger.warning(f"Date verification failed (non-fatal): {e}")
            print(f"{timestamp()} ⚠️  Date verification failed (non-fatal): {e}")

        # === Date filtering ===
        cutoff = get_lookback_cutoff_date()
        all_items, dropped_by_date, flagged_items = filter_items_by_date(all_items, cutoff)
        num_dropped = len(dropped_by_date)
        if num_dropped > 0:
            print(f"{timestamp()} Date filter: dropped {num_dropped} items older than {cutoff}")
        full_culls = _warn_date_filter_100pct_culls(all_items, dropped_by_date)
        for source, drop_count in full_culls:
            print(
                f"{timestamp()} ⚠️  {source}: {drop_count}/{drop_count} items "
                f"culled by date_filter (100%) — likely a stale listing page"
            )
        if flagged_items:
            print(f"{timestamp()} Date skepticism: {len(flagged_items)} items flagged as suspicious dates")
            for fi in flagged_items:
                print(f"{timestamp()}   WARNING: '{fi.get('headline', '')[:60]}' -- {fi.get('_date_flag')}")
        save_intermediate(f"dropped_by_date_{today}.json", {
            "stage": "scout",
            "cutoff": cutoff.isoformat(),
            "dropped_count": num_dropped,
            "flagged_count": len(flagged_items),
            "dropped": dropped_by_date,
            "flagged": [
                {
                    "headline": i.get("headline", ""),
                    "source_url": i.get("source_url", ""),
                    "date": i.get("date", ""),
                    "verified_date": i.get("_verified_date", ""),
                    "date_flag": i.get("_date_flag", ""),
                }
                for i in flagged_items
            ],
        })
        print(f"{timestamp()} {len(all_items)} items remain after date filtering.")

        if not all_items:
            print(f"{timestamp()} \u274c No items collected from any scout. Aborting.")
            return False

        # === Event-tuple extraction (Phase 2 of structural plan) ===
        # Mutates each item in place, adding `_event_tuple`. Phase 3
        # (within-day dedup) and Phase 4 (history_dedup) consume the
        # tuples for mechanical event-fingerprint comparison instead of
        # asking another Haiku judge to reason from headline strings.
        # Fails open: chunks that don't extract leave items without
        # tuples, and downstream stages fall back to legacy LLM-judged
        # paths.
        print(f"{timestamp()} Extracting event tuples for {len(all_items)} items...")
        all_items, tuple_telem = await extract_event_tuples(client, all_items)
        total_input_tokens += tuple_telem.get("input_tokens", 0)
        total_output_tokens += tuple_telem.get("output_tokens", 0)
        save_intermediate(
            f"event_tuples_{today}.json",
            {
                "status": tuple_telem.get("status"),
                "tuples_extracted": tuple_telem.get("tuples_extracted"),
                "tuples_failed": tuple_telem.get("tuples_failed"),
                "input_tokens": tuple_telem.get("input_tokens"),
                "output_tokens": tuple_telem.get("output_tokens"),
                "chunks": tuple_telem.get("chunks"),
            },
        )
        print(
            f"{timestamp()} Event tuples: "
            f"{tuple_telem.get('tuples_extracted')}/{tuple_telem.get('total_items')} "
            f"items tagged ({tuple_telem.get('status')})"
        )

        # === Two-stage dedup (fuzzy headline + Haiku semantic) ===
        before_dedup = len(all_items)
        all_items, num_deduped, dedup_log, dedup_drops = await deduplicate_items(
            all_items, client
        )
        if num_deduped > 0:
            print(f"{timestamp()} Dedup: {before_dedup} \u2192 {len(all_items)} items "
                  f"({num_deduped} duplicates merged)")
            for entry in dedup_log:
                print(f"{timestamp()}   Merged {entry['merged_count']} items -> "
                      f"'{entry['kept_headline'][:60]}'")
        # PHASE 1 (drop visibility): persist dedup losers so they surface in
        # dropped_items. Until this, dedup merges were silent — the 2026-04-15
        # UAE audit found 69 silent losses at this stage.
        save_intermediate(
            f"dropped_by_dedup_{today}.json",
            {
                "dropped_count": len(dedup_drops),
                "dropped": dedup_drops,
            },
        )
        print(f"{timestamp()} {len(all_items)} items remain after deduplication.")

        # === Web-search date verification for newsletter items without URLs ===
        # Newsletter-origin items (AINews, TLDR AI, etc.) frequently lack a
        # source_url, so date_verify above can't fetch a publish date for
        # them. Without this check, a newsletter re-surfacing 5-week-old
        # model-release coverage would slip through to the Gatekeeper with
        # its newsletter arrival date treated as publish date. Runs here —
        # after dedup, before the rest of the pipeline — so Gatekeeper,
        # history dedup, and the drop-chunk pool all see fresh items only.
        print(
            f"{timestamp()} Web search date verification on {len(all_items)} items..."
        )
        before_ws = len(all_items)
        all_items, ws_dropped = await verify_dates_via_search(all_items, cutoff)
        if ws_dropped:
            print(
                f"{timestamp()} Web search dropped {len(ws_dropped)} stale "
                f"newsletter items (before Gatekeeper):"
            )
            for d in ws_dropped:
                print(
                    f"{timestamp()}   {d['headline'][:70]} "
                    f"(median date: {d['web_search_median_date']})"
                )
        else:
            print(f"{timestamp()} Web search: all items pass freshness check")
        save_intermediate(
            f"dropped_by_web_search_{today}.json",
            {
                "dropped_count": len(ws_dropped),
                "dropped": ws_dropped,
            },
        )
        if before_ws != len(all_items):
            print(f"{timestamp()} {len(all_items)} items remain after web search verification.")
        after_dedup_count = len(all_items)

        # Save raw (post-dedup, pre-content-filter) for --from-stage content_filter
        save_intermediate(f"scout_output_raw_{today}.json", all_items)
        save_intermediate(f"scout_search_log_{today}.json", scout_search_log)

    elif from_stage == "content_filter":
        # Load cached raw scout output (post-dedup, pre-content-filter)
        all_items = load_intermediate(f"scout_output_raw_{today}.json")
        if not all_items:
            # Fall back to scout_output if raw doesn't exist
            all_items = load_intermediate(f"scout_output_{today}.json")
        if not all_items:
            print(f"{timestamp()} \u274c No cached scout output found for {today}. Run from scout stage first.")
            return False
        print(f"{timestamp()} Loaded cached raw scout output: {len(all_items)} items")
        after_dedup_count = len(all_items)  # loaded items are already post-dedup

        normalized_count = normalize_scout_contract(all_items)
        if normalized_count:
            print(
                f"{timestamp()} Scout schema normalization (cached): fixed "
                f"{normalized_count} field(s)"
            )

        # Re-verify dates (items from cache may not have _verified_date yet)
        print(f"{timestamp()} Verifying publication dates via source URLs...")
        try:
            num_verified, num_fetch_failed = await verify_dates(all_items)
            print(f"{timestamp()} Date verification: {num_verified} verified, "
                  f"{num_fetch_failed} unavailable")
        except Exception as e:
            logger.warning(f"Date verification failed (non-fatal): {e}")
            print(f"{timestamp()} ⚠️  Date verification failed (non-fatal): {e}")

        # Re-apply date filter (cutoff may have changed since scout run)
        cutoff = get_lookback_cutoff_date()
        all_items, dropped_by_date, flagged_items = filter_items_by_date(all_items, cutoff)
        num_dropped = len(dropped_by_date)
        if num_dropped > 0:
            print(f"{timestamp()} Date filter (re-applied): dropped {num_dropped} items older than {cutoff}")
        full_culls = _warn_date_filter_100pct_culls(all_items, dropped_by_date)
        for source, drop_count in full_culls:
            print(
                f"{timestamp()} ⚠️  {source}: {drop_count}/{drop_count} items "
                f"culled by date_filter (100%) — likely a stale listing page"
            )
        if flagged_items:
            for fi in flagged_items:
                print(f"{timestamp()}   WARNING: '{fi.get('headline', '')[:60]}' -- {fi.get('_date_flag')}")
        save_intermediate(f"dropped_by_date_{today}.json", {
            "stage": "content_filter_resume",
            "cutoff": cutoff.isoformat(),
            "dropped_count": num_dropped,
            "flagged_count": len(flagged_items),
            "dropped": dropped_by_date,
            "flagged": [
                {
                    "headline": i.get("headline", ""),
                    "source_url": i.get("source_url", ""),
                    "date": i.get("date", ""),
                    "verified_date": i.get("_verified_date", ""),
                    "date_flag": i.get("_date_flag", ""),
                }
                for i in flagged_items
            ],
        })
        print(f"{timestamp()} {len(all_items)} items remain after date filtering.")

    else:
        # from_stage is gatekeeper, ghostwriter, or editor — load post-filter output
        all_items = load_intermediate(f"scout_output_{today}.json")
        if not all_items:
            print(f"{timestamp()} \u274c No cached scout output found for {today}. Run from scout stage first.")
            return False
        print(f"{timestamp()} Loaded cached scout output: {len(all_items)} items")
        after_dedup_count = len(all_items)  # best available approximation from cache

        normalized_count = normalize_scout_contract(all_items)
        if normalized_count:
            print(
                f"{timestamp()} Scout schema normalization (cached): fixed "
                f"{normalized_count} field(s)"
            )

        if from_stage == "gatekeeper":
            # PHASE 2: when resuming from a cached scout_output (e.g. --from-stage
            # gatekeeper), the Synthesis stage did NOT run over this data, so
            # there are no cluster annotations on disk. We skip cluster reasoning
            # on the resume path and fall back to the legacy fuzzy filter — the
            # resume path is for debugging, not production runs.
            # Hard-drop repeat stories, soft-flag borderline overlaps
            all_items, previous_brief_drops, num_soft = flag_previous_brief_overlaps(all_items)
            num_hard = len(previous_brief_drops)
            if num_hard:
                print(f"{timestamp()} Previous-brief dedup: hard-dropped {num_hard} repeat(s)")
                # PHASE 1 (drop visibility): persist previous-brief overlap drops
                # so they surface in the admin Drops view instead of being lost.
                save_intermediate(
                    f"dropped_by_previous_brief_overlap_{today}.json",
                    {
                        "dropped_count": num_hard,
                        "dropped": previous_brief_drops,
                    },
                )
            if num_soft:
                print(f"{timestamp()} Previous-brief overlap: flagged {num_soft} item(s)")
                for item in all_items:
                    if item.get("_previous_brief_overlap"):
                        print(f"{timestamp()}   \u26a0\ufe0f  '{item.get('headline', '')[:55]}' — {item['_previous_brief_overlap']}")

            # Penalize overlapping items so fresh stories get priority
            penalized_count = apply_continuity_penalty(all_items)
            if penalized_count:
                print(f"{timestamp()} Continuity penalty: {penalized_count} item(s) penalized (-{CONTINUITY_PENALTY} significance)")
                for item in all_items:
                    if item.get("_continuity_penalized"):
                        print(f"{timestamp()}   ⚠️  '{item.get('headline', '')[:60]}'")

            _raw_content_lookup = _build_raw_content_lookup(all_items)

            # Phase 2 — pre-Gatekeeper section classifier also runs on resume
            # from cache. Idempotent: short-circuits if the cached scout_output
            # already carries canonical brief_section on every item (i.e. the
            # prior run was post-Phase-2). Only re-runs when resuming from a
            # pre-Phase-2 cache or a cache written before the classifier stage.
            print(f"{timestamp()} Pre-Gatekeeper section classification (resume)...")
            await classify_candidate_sections(client, all_items)

            # Pre-Gatekeeper enrichment also runs on resume. The main path
            # writes enrichment back to memory but not always to disk (fixed
            # below), so cached artifacts from pre-2026-04-20 runs carry
            # un-enriched thin items. Running here guarantees Gatekeeper has
            # content to score regardless of how the cache was populated.
            print(f"{timestamp()} Pre-gatekeeper enrichment (resume)...")
            enriched_count = await _run_pre_gatekeeper_enrichment(all_items)
            if enriched_count:
                save_intermediate(f"scout_output_{today}.json", all_items)

            lightweight_items = [
                {k: v for k, v in item.items() if k in GATEKEEPER_KEEP_FIELDS}
                for item in all_items
            ]
            scout_output_json = json.dumps(lightweight_items, indent=2, ensure_ascii=False)
        else:
            # ghostwriter or editor — gatekeeper output loaded from cache
            # (already has rejoined raw_content from previous run)
            scout_output_json = json.dumps(all_items, indent=2, ensure_ascii=False)

    # === STEP 1.5: Content Filter Agent ===
    content_filter_drops = []  # Track for audit trail
    _raw_content_lookup: dict[str, list[dict]] = {}
    # Re-keyer + rewrite-rate accounting for the Gatekeeper stage; populated
    # inside the Gatekeeper block and read by pipeline_stats later. Stays
    # None on --from-stage=ghostwriter/editor resume paths where the
    # Gatekeeper isn't invoked.
    gk_drop_accounting: Optional[dict] = None
    if not from_stage or from_stage in ("scout", "content_filter"):
        print(f"{timestamp()} Running Content Filter...")

        # Split off bypass-listed sources before the Haiku gate — these are
        # low-volume, hand-curated feeds (see CONTENT_FILTER_BYPASS_SOURCES)
        # whose posts should always reach the Gatekeeper on merit, even when
        # the NEWS/NOT_NEWS prompt would otherwise flag them as exec
        # characterization or trend commentary.
        pre_filter_items = list(all_items)
        bypass_items = [it for it in pre_filter_items if _is_content_filter_bypass(it)]
        filterable_items = [it for it in pre_filter_items if not _is_content_filter_bypass(it)]
        if bypass_items:
            bypass_sources = sorted({
                (it.get("source") or it.get("source_name") or "") for it in bypass_items
            })
            print(
                f"{timestamp()}   Bypassing content filter for {len(bypass_items)} "
                f"item(s) from trusted sources: {', '.join(bypass_sources)}"
            )

        print(
            f"{timestamp()}   Batching {len(filterable_items)} items into chunks of "
            f"{CONTENT_FILTER_MIN_BATCH_SIZE}-{CONTENT_FILTER_MAX_BATCH_SIZE} "
            "for Content Filter"
        )

        filtered_items, content_filter_drops, verdicts, cf_usage, batch_summaries = (
            await run_content_filter_batched(client, filterable_items)
        )
        total_input_tokens += cf_usage["input_tokens"]
        total_output_tokens += cf_usage["output_tokens"]

        # Merge bypass + kept-filterable back into all_items, preserving
        # original collection order. Dropped items fall out.
        kept_ids = {id(it) for it in bypass_items} | {id(it) for it in filtered_items}
        all_items = [it for it in pre_filter_items if id(it) in kept_ids]

        print(
            f"{timestamp()} \u2705 Content Filter: {len(all_items)} kept "
            f"({len(filtered_items)} passed filter + {len(bypass_items)} bypassed), "
            f"{len(content_filter_drops)} filtered"
        )
        save_intermediate(f"content_filter_output_{today}.json", {
            "verdicts": verdicts,
            "news_count": len(all_items),
            "filtered_count": len(content_filter_drops),
            "bypass_count": len(bypass_items),
            "bypass_sources": sorted({
                (it.get("source") or it.get("source_name") or "") for it in bypass_items
            }),
            "batches": batch_summaries,
        })

        save_intermediate(f"dropped_by_content_filter_{today}.json", {
            "dropped_count": len(content_filter_drops),
            "dropped": content_filter_drops,
        })

        # Save post-filter items (full items for rejoin after Gatekeeper)
        save_intermediate(f"scout_output_{today}.json", all_items)

        # === History Dedup (semantic cross-day repeat filter) ===
        # Catches items the deterministic fuzzy filter misses — rewritten
        # headlines, day-late wire pickups, paraphrased coverage of stories
        # that the analyst was shown (published OR pending) in the last
        # 3 days. Runs before Synthesis so cluster reasoning is spent on
        # fresh items only. Fail-open: on any error, pass items through
        # unchanged rather than block the pipeline.
        if HISTORY_DEDUP_ENABLED and all_items:
            recent_history_json = get_recent_history_headlines()
            if "No previous brief" in recent_history_json:
                print(f"{timestamp()} History dedup: no history available, skipping")
            else:
                print(f"{timestamp()} Running History Dedup...")
                # Phase 4: tuple-aware first pass (no LLM call). Items
                # whose tuples match a historical entry's tuple get an
                # immediate REPEAT verdict; items lacking tuples are
                # left for the Haiku fallback.
                try:
                    recent_history_list_for_tuples = json.loads(recent_history_json)
                    if not isinstance(recent_history_list_for_tuples, list):
                        recent_history_list_for_tuples = []
                except (ValueError, TypeError):
                    recent_history_list_for_tuples = []
                tuple_result, tuple_telem = run_tuple_aware_history_dedup(
                    all_items, recent_history_list_for_tuples
                )
                tuple_verdicts = tuple_result.get("verdicts", [])
                logger.info(
                    "History dedup (tuple): %d items_with_tuples, "
                    "%d history_with_tuples, %d drops, %d skipped_no_tuple",
                    tuple_telem.get("items_with_tuples", 0),
                    tuple_telem.get("history_with_tuples", 0),
                    tuple_telem.get("drops", 0),
                    tuple_telem.get("skipped_no_tuple", 0),
                )
                # If every item was covered by tuple comparison AND
                # history had at least some tuple data, we can skip Haiku
                # entirely. Otherwise run Haiku and merge.
                tuple_covered_all = (
                    tuple_telem.get("skipped_no_tuple", 1) == 0
                    and tuple_telem.get("history_with_tuples", 0) > 0
                )
                if tuple_covered_all:
                    print(
                        f"{timestamp()} History dedup: tuple path covered all "
                        f"{tuple_telem['items_with_tuples']} items "
                        f"({tuple_telem['drops']} drops); skipping Haiku"
                    )
                hd_result = None
                hd_correction = ""
                if not tuple_covered_all:
                    for attempt in range(2):
                        if attempt > 0:
                            wait = 2 + random.uniform(0, 1)
                            print(f"{timestamp()}   Backing off {wait:.1f}s before retry...")
                            await asyncio.sleep(wait)
                        try:
                            # Lightweight view — index position IS the id the
                            # agent reasons about, matching Synthesis's pattern.
                            hd_items_view = [
                                {
                                    "id": i,
                                    "headline": item.get("headline", ""),
                                    "summary": item.get("summary", ""),
                                    "entities": item.get("entities", []),
                                    "source": item.get("source"),
                                    "date": item.get("date") or item.get("_verified_date"),
                                }
                                for i, item in enumerate(all_items)
                            ]
                            hd_prompt = load_prompt(
                                "history_dedup_prompt.md",
                                items_json=json.dumps(
                                    hd_items_view, indent=2, ensure_ascii=False
                                ),
                            ) + hd_correction
                            hd_result, hd_usage = await run_history_dedup(
                                client, hd_prompt
                            )
                            total_input_tokens += hd_usage["input_tokens"]
                            total_output_tokens += hd_usage["output_tokens"]
                            break
                        except Exception as e:
                            if attempt == 0:
                                logger.warning(
                                    f"History dedup attempt 1 failed: {e}. Retrying..."
                                )
                                print(f"{timestamp()} ⚠️  History dedup failed, retrying...")
                                hd_correction = build_retry_correction("history_dedup", e)
                            else:
                                logger.error(
                                    f"History dedup attempt 2 failed: {e}", exc_info=True
                                )
                                print(
                                    f"{timestamp()} ⚠️  History dedup failed after 2 attempts — "
                                    "passing items through untouched (fail-open)"
                                )
                                hd_result = None

                # Phase 4: pick the verdict source.
                #   - If tuple path covered every item AND history had
                #     tuples available, use the tuple verdicts directly.
                #   - Else if Haiku ran successfully, merge tuple
                #     verdicts (primary) with Haiku verdicts (fallback).
                #   - Else if Haiku failed, fall back to tuple verdicts
                #     alone (which may be empty for items that lacked
                #     tuples — fail-open behavior preserved).
                if tuple_covered_all:
                    final_verdicts = tuple_verdicts
                    hd_result = {"verdicts": final_verdicts}
                elif hd_result:
                    final_verdicts = merge_history_dedup_verdicts(
                        primary=tuple_verdicts,
                        fallback=hd_result.get("verdicts", []),
                    )
                    hd_result = {"verdicts": final_verdicts}
                elif tuple_verdicts:
                    final_verdicts = tuple_verdicts
                    hd_result = {"verdicts": final_verdicts}

                if hd_result:
                    verdicts = hd_result.get("verdicts", [])
                    before_count = len(all_items)
                    # Parse the history view back to a list so the
                    # coherence check in apply_history_dedup_verdicts can
                    # verify the judge's cited matched_headline actually
                    # appears in the inputs it saw (guards against
                    # hallucinated cites — see 2026-04-20 incident).
                    try:
                        recent_history_list = json.loads(recent_history_json)
                        if not isinstance(recent_history_list, list):
                            recent_history_list = None
                    except (ValueError, TypeError):
                        recent_history_list = None
                    all_items, history_dedup_drops = apply_history_dedup_verdicts(
                        all_items, verdicts, recent_history=recent_history_list
                    )
                    num_dropped = len(history_dedup_drops)
                    print(
                        f"{timestamp()} ✅ History Dedup: {num_dropped} repeat(s) dropped, "
                        f"{len(all_items)} remain (from {before_count})"
                    )
                    save_intermediate(
                        f"history_dedup_output_{today}.json",
                        {
                            "verdicts": verdicts,
                            "dropped_count": num_dropped,
                            "kept_count": len(all_items),
                        },
                    )
                    if num_dropped:
                        # Drop visibility: persist drops so they surface on
                        # /admin/drops with a "History dedup (semantic)"
                        # prefix — distinct from the deterministic tier's
                        # "Previous brief repeat" prefix.
                        save_intermediate(
                            f"dropped_by_history_dedup_{today}.json",
                            {
                                "dropped_count": num_dropped,
                                "dropped": history_dedup_drops,
                            },
                        )
                        # Refresh the cached scout_output so downstream
                        # resume (--from-stage=gatekeeper) doesn't pull
                        # back the items we just dropped.
                        save_intermediate(f"scout_output_{today}.json", all_items)

        # PHASE 2: Synthesis stage — clusters related items by event and
        # annotates continuity against prior briefs. Replaces the fuzzy-
        # string overlap filter (legacy path kept behind SYNTHESIS_ENABLED
        # flag for rollback). See .claude/plans/robust-sleeping-raven.md.
        if SYNTHESIS_ENABLED:
            print(f"{timestamp()} Running Synthesis...")
            synthesis_result = None
            syn_correction = ""
            for attempt in range(2):
                if attempt > 0:
                    wait = 2 + random.uniform(0, 1)
                    print(f"{timestamp()}   Backing off {wait:.1f}s before retry...")
                    await asyncio.sleep(wait)
                try:
                    # Lightweight view of each item. Index position IS the
                    # item_id the Synthesis agent reasons about.
                    synthesis_items = [
                        {
                            "id": i,
                            "headline": item.get("headline", ""),
                            "summary": item.get("summary", ""),
                            "entities": item.get("entities", []),
                            "source": item.get("source"),
                            "date": item.get("date") or item.get("_verified_date"),
                        }
                        for i, item in enumerate(all_items)
                    ]
                    synthesis_prompt = load_prompt(
                        "synthesis_prompt.md",
                        items_json=json.dumps(
                            synthesis_items, indent=2, ensure_ascii=False
                        ),
                    ) + syn_correction
                    synthesis_result, syn_usage = await run_synthesis(
                        client, synthesis_prompt
                    )
                    total_input_tokens += syn_usage["input_tokens"]
                    total_output_tokens += syn_usage["output_tokens"]
                    break
                except Exception as e:
                    if attempt == 0:
                        logger.warning(f"Synthesis attempt 1 failed: {e}. Retrying...")
                        print(f"{timestamp()} ⚠️  Synthesis failed, retrying...")
                        syn_correction = build_retry_correction("synthesis", e)
                    else:
                        logger.error(
                            f"Synthesis attempt 2 failed: {e}", exc_info=True
                        )
                        print(
                            f"{timestamp()} ⚠️  Synthesis failed after 2 attempts — "
                            "passing items through un-annotated (fail-open)"
                        )
                        synthesis_result = None

            if synthesis_result:
                annotated, unannotated = apply_synthesis_annotations(
                    all_items, synthesis_result
                )
                num_clusters = len(synthesis_result.get("clusters", []))
                head_of_state_clusters = sum(
                    1 for c in synthesis_result.get("clusters", [])
                    if c.get("significance_tier") == "head_of_state"
                )
                continuation_clusters = sum(
                    1 for c in synthesis_result.get("clusters", [])
                    if c.get("continuity_status") == "continuation"
                )
                restatement_clusters = sum(
                    1 for c in synthesis_result.get("clusters", [])
                    if c.get("continuity_status") == "restatement"
                )
                print(
                    f"{timestamp()} ✅ Synthesis: {num_clusters} cluster(s) "
                    f"({head_of_state_clusters} head_of_state, "
                    f"{continuation_clusters} continuation, "
                    f"{restatement_clusters} restatement); "
                    f"{annotated} item(s) annotated, {unannotated} unannotated"
                )
                save_intermediate(
                    f"synthesis_output_{today}.json", synthesis_result
                )
            else:
                # Fail-open: clear annotations on every item so Gatekeeper
                # sees a consistent None-everywhere schema rather than a
                # partial/messy mix from a failed run.
                clear_synthesis_annotations(all_items)
                save_intermediate(
                    f"synthesis_output_{today}.json",
                    {"error": "Synthesis failed — passed through un-annotated"},
                )
        else:
            # LEGACY PATH (SYNTHESIS_ENABLED=false) — fuzzy-string overlap
            # filter + continuity penalty. DEPRECATED 2026-04-15; kept for
            # rollback. Remove once Synthesis has run cleanly in prod for
            # 2 weeks. See .claude/plans/robust-sleeping-raven.md.
            all_items, previous_brief_drops, num_soft = flag_previous_brief_overlaps(all_items)
            num_hard = len(previous_brief_drops)
            if num_hard:
                print(f"{timestamp()} Previous-brief dedup: hard-dropped {num_hard} repeat(s)")
                # PHASE 1 (drop visibility): persist previous-brief overlap
                # drops so they surface in the admin Drops view.
                save_intermediate(
                    f"dropped_by_previous_brief_overlap_{today}.json",
                    {
                        "dropped_count": num_hard,
                        "dropped": previous_brief_drops,
                    },
                )
            if num_soft:
                print(f"{timestamp()} Previous-brief overlap: flagged {num_soft} item(s)")
                for item in all_items:
                    if item.get("_previous_brief_overlap"):
                        print(f"{timestamp()}   \u26a0\ufe0f  '{item.get('headline', '')[:55]}' — {item['_previous_brief_overlap']}")

            penalized_count = apply_continuity_penalty(all_items)
            if penalized_count:
                print(f"{timestamp()} Continuity penalty: {penalized_count} item(s) penalized (-{CONTINUITY_PENALTY} significance)")
                for item in all_items:
                    if item.get("_continuity_penalized"):
                        print(f"{timestamp()}   ⚠️  '{item.get('headline', '')[:60]}'")

        # --- Pre-gatekeeper lightweight enrichment for headline-only items ---
        enriched_count = await _run_pre_gatekeeper_enrichment(all_items)
        if enriched_count:
            # Persist so --from-stage=gatekeeper resume loads enriched items.
            # History Dedup uses the same pattern at its save site above.
            save_intermediate(f"scout_output_{today}.json", all_items)

        _raw_content_lookup = _build_raw_content_lookup(all_items)
        # Assign stable indices before the Gatekeeper sees items. The
        # gatekeeper echoes _idx back on both selected AND dropped items,
        # so we can rejoin metadata (source, source_url, source_scout)
        # by index instead of fragile headline matching.
        for i, item in enumerate(all_items):
            item["_idx"] = i

        # Phase 2 (curation rewrite) — pre-Gatekeeper section classifier.
        # Haiku assigns each candidate to one of the five canonical
        # sections so Gatekeeper can enforce per-section quotas
        # (top-15-per-section) instead of a flat top-10-overall. Items
        # gain both `brief_section` (Gatekeeper schema) and `section`
        # (downstream schema) so the assignment carries through unchanged.
        # Idempotent: on --from-stage=gatekeeper resume, the classifier
        # short-circuits if items already carry canonical sections.
        print(f"{timestamp()} Pre-Gatekeeper section classification...")
        await classify_candidate_sections(client, all_items)
        section_counts: dict[str, int] = {}
        for item in all_items:
            section_counts[item.get("brief_section", "?")] = (
                section_counts.get(item.get("brief_section", "?"), 0) + 1
            )
        for s in CANONICAL_SECTIONS:
            print(f"{timestamp()}   {s}: {section_counts.get(s, 0)}")
        save_intermediate(
            f"section_classifier_output_{today}.json",
            {
                "counts": section_counts,
                "items": [
                    {
                        "_idx": item.get("_idx"),
                        "headline": item.get("headline", "")[:200],
                        "brief_section": item.get("brief_section"),
                    }
                    for item in all_items
                ],
            },
        )

        # Strip raw_content and additional_context for Gatekeeper (saves ~50% input tokens)
        lightweight_items = [
            {k: v for k, v in item.items() if k in GATEKEEPER_KEEP_FIELDS}
            for item in all_items
        ]
        full_size = len(json.dumps(all_items, ensure_ascii=False))
        light_size = len(json.dumps(lightweight_items, ensure_ascii=False))
        logger.info(
            f"Gatekeeper input stripped: {len(all_items)} items, "
            f"full={full_size:,} chars → light={light_size:,} chars "
            f"({100 - light_size * 100 // full_size}% reduction)"
        )
        scout_output_json = json.dumps(lightweight_items, indent=2, ensure_ascii=False)

    assign_candidate_ids(all_items, today)

    # === STEP 2: Gatekeeper ===
    if not from_stage or from_stage in ("scout", "content_filter", "gatekeeper"):
        print(f"{timestamp()} Running Gatekeeper (chunk-by-section)...")

        # PHASE 3 (chunked Gatekeeper, 2026-04-23): the legacy single-call
        # path silently dropped ~38 items/day (recorded as
        # `gatekeeper_implicit` in `dropped_items`) because Sonnet's recall
        # degrades on inputs >100 items. `run_chunked_gatekeeper` runs one
        # call per `brief_section` (already populated upstream by the
        # Haiku section classifier) in parallel via `asyncio.gather`,
        # retries each chunk up to 2× when the addressed-item count drops
        # below 85% completeness, then runs `reconcile_cross_section_clusters`
        # to re-apply the cluster-aware preservation rule globally. The
        # rekeyer + implicit-drop set-diff below still runs against the
        # merged pool, so the existing audit trail is unchanged.
        gatekeeper_chunked_telemetry: dict = {}
        try:
            gatekeeper_result, gk_usage, gatekeeper_chunked_telemetry = (
                await run_chunked_gatekeeper(
                    client=client,
                    lightweight_items=lightweight_items,
                )
            )
            total_input_tokens += gk_usage["input_tokens"]
            total_output_tokens += gk_usage["output_tokens"]
        except Exception as e:
            logger.error(
                f"Gatekeeper (chunked) failed: {e}", exc_info=True
            )
            print(f"{timestamp()} \u274c Gatekeeper (chunked) failed: {e}")
            print(f"{timestamp()} Saving partial results (scout output only).")
            return False

        if gatekeeper_result is None:
            logger.error("Gatekeeper (chunked) returned no items at all.")
            print(
                f"{timestamp()} \u274c Gatekeeper (chunked) returned no items. "
                f"Saving partial results."
            )
            return False

        # Inject deterministic after_deduplication count (LLM can't know this)
        if "brief_summary" in gatekeeper_result:
            gatekeeper_result["brief_summary"]["after_deduplication"] = after_dedup_count

        selected = gatekeeper_result.get("selected", [])
        dropped = gatekeeper_result.get("dropped", [])
        gatekeeper_model_drops = list(dropped)

        # PHASE 2 (drop visibility, 2026-04-21): implicit-drop detection
        # now runs in two stages:
        #
        #   1. Haiku re-keyer (`pipeline/gk_rekeyer`) attaches `_idx` to
        #      every Gatekeeper output item by semantic matching against the
        #      input pool. This replaces the unreliable expectation that the
        #      Sonnet Gatekeeper echoes `_idx` back itself (0% rate on
        #      selected in production; variable on dropped).
        #   2. Implicit drops are computed as a set-diff on integer `_idx`
        #      values, with a fuzzy-headline fallback for any output items
        #      the re-keyer couldn't match.
        #
        # Historic behavior was an exact `lower()+strip()` headline diff,
        # which misread every Gatekeeper headline refinement as an implicit
        # drop. Variance was huge (0 → 216 → 131 across 04-15/16/17) while
        # the real silent-drop count was stable at ~5-15/day. This section
        # intentionally re-uses `_normalize_for_match` (already imported
        # above; strips punctuation + caps at 60 chars) plus SequenceMatcher
        # at threshold 0.55 for the fallback — same tool already used in
        # `demerge_selected_items` and `rejoin_raw_content` elsewhere in
        # this file.
        rekey_report = await rekey_gatekeeper_output(
            client, lightweight_items, selected, gatekeeper_model_drops,
        )
        print(
            f"{timestamp()} Re-keyer: {rekey_report['matched']}"
            f"/{rekey_report['total']} matched "
            f"(trusted={rekey_report['trusted_existing']}, "
            f"haiku={rekey_report['matched_by_haiku']}, "
            f"unmatched={rekey_report['unmatched']})"
        )

        def _norm_headline(h: str) -> str:
            """Legacy exact-match normalization — kept for the rewrite-rate
            metric (how often the model's output headline differs from its
            source by more than trivial casing/whitespace)."""
            return (h or "").strip().lower()

        _gk_idx_lookup = {
            int(item["_idx"]): item
            for item in lightweight_items
            if item.get("_idx") is not None
        }

        # Pool indexed by normalized-match key for fuzzy fallback. Used both
        # for (a) implicit-drop fallback and (b) metadata rejoin when the
        # re-keyer couldn't attach _idx.
        _gk_headline_norm_lookup = {
            _normalize_for_match(item.get("headline", "")): item
            for item in lightweight_items
            if item.get("headline")
        }
        _fallback_candidates = list(_gk_headline_norm_lookup.items())

        def _fuzzy_best_match(headline: str, used_idx: set[int]) -> Optional[dict]:
            """Fallback: best fuzzy match in lightweight_items whose _idx
            is not already claimed. Threshold 0.55."""
            if not headline:
                return None
            needle = _normalize_for_match(headline)
            if not needle:
                return None
            best_item = None
            best_score = 0.0
            for cand_norm, cand_item in _fallback_candidates:
                cand_idx = cand_item.get("_idx")
                if cand_idx is not None and int(cand_idx) in used_idx:
                    continue
                score = SequenceMatcher(None, needle, cand_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_item = cand_item
            return best_item if best_score >= 0.55 else None

        # Build the `used_idx` set from whatever _idx values the re-keyer
        # successfully attached. The fuzzy fallback must not re-claim these.
        used_idx: set[int] = set()
        for out_item in list(selected) + list(gatekeeper_model_drops):
            oi = out_item.get("_idx")
            if oi is not None:
                try:
                    used_idx.add(int(oi))
                except (TypeError, ValueError):
                    pass

        # Metadata rejoin — fill source/source_url/source_scout on drops
        # whose re-keyer match gave us _idx. Where the re-keyer came up
        # empty, try the fuzzy fallback and attach _idx if found.
        rejoined_by_idx = 0
        rejoined_by_fuzzy = 0
        rejoin_unmatched = 0
        rewrite_count = 0  # exact-match failures against input pool
        for drop in gatekeeper_model_drops:
            src_item = None
            drop_idx = drop.get("_idx")
            if drop_idx is not None:
                try:
                    src_item = _gk_idx_lookup.get(int(drop_idx))
                    if src_item:
                        rejoined_by_idx += 1
                except (ValueError, TypeError):
                    pass
            if not src_item:
                src_item = _fuzzy_best_match(drop.get("headline", ""), used_idx)
                if src_item is not None:
                    rejoined_by_fuzzy += 1
                    matched_idx = src_item.get("_idx")
                    if matched_idx is not None:
                        try:
                            matched_int = int(matched_idx)
                            drop["_idx"] = matched_int
                            used_idx.add(matched_int)
                        except (TypeError, ValueError):
                            pass
            if not src_item:
                rejoin_unmatched += 1
                continue
            # Track rewrite rate: how often the drop's headline doesn't
            # exactly match its source's headline even after normalization.
            if _norm_headline(drop.get("headline", "")) != _norm_headline(
                src_item.get("headline", "")
            ):
                rewrite_count += 1
            if not drop.get("source"):
                drop["source"] = src_item.get("source") or src_item.get("source_name")
            if not drop.get("source_url"):
                drop["source_url"] = src_item.get("source_url")
            if not drop.get("source_scout"):
                drop["source_scout"] = src_item.get("source_scout")
        logger.info(
            "Gatekeeper drop rejoin: %d by _idx, %d by fuzzy, %d unmatched (of %d drops)",
            rejoined_by_idx, rejoined_by_fuzzy, rejoin_unmatched,
            len(gatekeeper_model_drops),
        )

        # Also run the fuzzy fallback on `selected` items that still lack
        # _idx after the re-keyer — both to attach _idx (so the implicit
        # set-diff below is accurate) and to measure rewrite rate on the
        # selected side.
        for sel_item in selected:
            if sel_item.get("_idx") is None:
                fuzz = _fuzzy_best_match(sel_item.get("headline", ""), used_idx)
                if fuzz is not None:
                    matched_idx = fuzz.get("_idx")
                    if matched_idx is not None:
                        try:
                            matched_int = int(matched_idx)
                            sel_item["_idx"] = matched_int
                            used_idx.add(matched_int)
                        except (TypeError, ValueError):
                            pass
            # Rewrite metric for selected
            sel_idx = sel_item.get("_idx")
            if sel_idx is not None:
                try:
                    src = _gk_idx_lookup.get(int(sel_idx))
                    if src and _norm_headline(
                        sel_item.get("headline", "")
                    ) != _norm_headline(src.get("headline", "")):
                        rewrite_count += 1
                except (ValueError, TypeError):
                    pass

        # Final implicit-drop detection: pure set-diff on integer _idx.
        input_idx_set = {
            int(i["_idx"]) for i in lightweight_items if i.get("_idx") is not None
        }
        output_idx_set = {
            int(x["_idx"])
            for x in list(selected) + list(gatekeeper_model_drops)
            if x.get("_idx") is not None
        }
        implicit_missing = input_idx_set - output_idx_set
        gatekeeper_implicit_drops = []
        if implicit_missing:
            for item in lightweight_items:
                item_idx = item.get("_idx")
                if item_idx is None:
                    continue
                try:
                    if int(item_idx) not in implicit_missing:
                        continue
                except (TypeError, ValueError):
                    continue
                gatekeeper_implicit_drops.append({
                    "headline": item.get("headline", ""),
                    "source": item.get("source"),
                    "source_url": item.get("source_url"),
                    "drop_reason": "Gatekeeper implicit (not returned in selected or dropped)",
                    "composite_score": None,
                    "_idx": int(item_idx),
                })
            print(
                f"{timestamp()} Gatekeeper implicit drops: "
                f"{len(gatekeeper_implicit_drops)} item(s) truly silent "
                f"(after re-keyer + fuzzy fallback)"
            )

        # Stash drop-accounting metrics for pipeline_stats later on.
        total_output_items = len(selected) + len(gatekeeper_model_drops)
        gk_drop_accounting = {
            "rekeyer": rekey_report,
            "rewrite_count": rewrite_count,
            "rewrite_rate": (
                rewrite_count / total_output_items if total_output_items else 0.0
            ),
            "true_silent_count": len(gatekeeper_implicit_drops),
            "rejoined_by_idx": rejoined_by_idx,
            "rejoined_by_fuzzy": rejoined_by_fuzzy,
            "rejoin_unmatched": rejoin_unmatched,
            # PHASE 3: chunk-by-section telemetry from run_chunked_gatekeeper.
            # Empty {} when the legacy single-call path ran (e.g. resume from
            # cached gatekeeper output skips the live call entirely).
            "chunked": gatekeeper_chunked_telemetry,
        }

        selected, rejoin_warnings = rejoin_raw_content(selected, _raw_content_lookup)
        gatekeeper_result["selected"] = selected
        if rejoin_warnings:
            for warning in rejoin_warnings:
                logger.warning(f"Rejoin: {warning}")
                print(f"{timestamp()}   \u26a0\ufe0f  {warning}")

        # Merge deterministic pipeline drops into gatekeeper dropped array for unified audit trail
        pipeline_drops = []
        if content_filter_drops:
            pipeline_drops.extend(content_filter_drops)
        if pipeline_drops:
            dropped = pipeline_drops + dropped
            gatekeeper_result["dropped"] = dropped

        # Normalize legacy section naming drift and reject unknown sections.
        selected, section_warnings = normalize_sections(
            selected, "brief_section", "Gatekeeper"
        )
        gatekeeper_result["selected"] = selected
        for w in section_warnings:
            logger.warning(w)
            print(f"{timestamp()}   \u26a0\ufe0f  {w}")

        # Phase 2 (curation rewrite) — per-section cap of 15.
        # Gatekeeper is instructed to cap at 15 per section, but defensively
        # truncate if it overshoots. Within each section, keep the top 15
        # by composite_score; demoted items are added to `dropped` with a
        # distinct reason so the Drops admin view can audit them.
        SECTION_CAP = 15
        per_section: dict[str, list[dict]] = {s: [] for s in CANONICAL_SECTIONS}
        for item in selected:
            per_section.setdefault(item.get("brief_section") or "?", []).append(item)
        capped_selected: list[dict] = []
        section_cap_drops: list[dict] = []
        for section, items in per_section.items():
            items.sort(
                key=lambda x: float(x.get("composite_score") or 0.0),
                reverse=True,
            )
            keep = items[:SECTION_CAP]
            demote = items[SECTION_CAP:]
            capped_selected.extend(keep)
            for d in demote:
                d_copy = dict(d)
                d_copy["drop_reason"] = (
                    f"Section cap: {section} exceeded {SECTION_CAP} items "
                    f"(ranked below top {SECTION_CAP} by composite_score)"
                )
                d_copy["_stage"] = "section_cap"
                section_cap_drops.append(d_copy)
        if section_cap_drops:
            selected = capped_selected
            dropped = list(dropped) + section_cap_drops
            gatekeeper_result["selected"] = selected
            gatekeeper_result["dropped"] = dropped
            print(
                f"{timestamp()} Section cap: trimmed "
                f"{len(section_cap_drops)} overflow(s) to {SECTION_CAP}/section"
            )
        # Log per-section selected counts (post-cap).
        post_cap_counts = {s: 0 for s in CANONICAL_SECTIONS}
        for item in selected:
            sec = item.get("brief_section")
            if sec in post_cap_counts:
                post_cap_counts[sec] += 1
        for s in CANONICAL_SECTIONS:
            print(f"{timestamp()}   Selected in {s}: {post_cap_counts[s]}")

        # Demerge: split semicolon-joined headlines back into separate items.
        selected, demerge_count = demerge_selected_items(selected, all_items)
        gatekeeper_result["selected"] = selected
        if demerge_count:
            print(f"{timestamp()} Demerge: split {demerge_count} merged item(s) → {len(selected)} total")

        assign_gatekeeper_ids(selected, today)
        selected = await dedup_selected_pool(selected, today, client)
        gatekeeper_result["selected"] = selected

        # Final repeat guard after Gatekeeper has rewritten/normalized headlines.
        # PHASE 2: when SYNTHESIS_ENABLED, the Synthesis stage has already
        # flagged restatements upstream and the Gatekeeper has been told to
        # drop them with an explicit drop_reason. The fuzzy-string post-guard
        # is obsolete (and was the proximate cause of the 2026-04-15 Crown
        # Prince miss). Only run it on the legacy path for rollback safety.
        if not SYNTHESIS_ENABLED:
            selected, post_gatekeeper_repeat_drops, post_gatekeeper_soft = flag_previous_brief_overlaps(selected)
            if post_gatekeeper_repeat_drops:
                # PHASE 1 (drop visibility): tag drops so ingest_brief
                # classifies them as "post_gatekeeper_overlap" instead of
                # lumping with Gatekeeper model drops.
                for drop in post_gatekeeper_repeat_drops:
                    drop["_stage"] = "post_gatekeeper_overlap"
                    original_reason = drop.get("drop_reason", "")
                    if not original_reason.startswith("Post-Gatekeeper overlap:"):
                        drop["drop_reason"] = f"Post-Gatekeeper overlap: {original_reason}"
                dropped.extend(post_gatekeeper_repeat_drops)
                gatekeeper_result["selected"] = selected
                gatekeeper_result["dropped"] = dropped
                print(
                    f"{timestamp()} Post-Gatekeeper repeat check: hard-dropped "
                    f"{len(post_gatekeeper_repeat_drops)} selected repeat(s)"
                )
            if post_gatekeeper_soft:
                print(
                    f"{timestamp()} Post-Gatekeeper repeat check: flagged "
                    f"{post_gatekeeper_soft} borderline overlap(s)"
                )

        print(f"{timestamp()} \u2705 Gatekeeper complete: {len(selected)} selected, "
              f"{len(dropped)} dropped (incl. {len(content_filter_drops)} from content filter)")

        save_intermediate(f"dropped_by_gatekeeper_{today}.json", {
            "gatekeeper_model_dropped": gatekeeper_model_drops,
            "section_normalization_dropped": section_warnings,
            "content_filter_dropped": content_filter_drops,
            "final_dropped": dropped,
            # PHASE 1 (drop visibility): the implicit drop list — items that
            # entered the Gatekeeper and silently disappeared (not in selected
            # or dropped). ingest_brief._parse_dropped_items reads this key
            # and tags rows as dropped_at_stage="gatekeeper_implicit".
            "implicit_dropped": gatekeeper_implicit_drops,
            # PHASE 2 (drop accounting, 2026-04-21): re-keyer report for
            # the Drops admin view and the Pipeline Runs dashboard.
            "rekeyer_report": gk_drop_accounting.get("rekeyer"),
            "rewrite_count": gk_drop_accounting.get("rewrite_count"),
            "rewrite_rate": gk_drop_accounting.get("rewrite_rate"),
            "true_silent_count": gk_drop_accounting.get("true_silent_count"),
            # PHASE 3 (chunk-by-section, 2026-04-23): per-section
            # input/output counts, retry counts, missing counts, and
            # cross-section cluster demotions. Empty when the legacy
            # single-call path ran.
            "chunked_telemetry": gk_drop_accounting.get("chunked", {}),
        })

        gatekeeper_output_json = json.dumps(gatekeeper_result, indent=2, ensure_ascii=False)
        save_intermediate(f"gatekeeper_output_{today}.json", gatekeeper_result)
    else:
        # Load cached gatekeeper output, preferring the enriched variant when present
        gatekeeper_result = load_intermediate(f"enriched_gatekeeper_output_{today}.json")
        loaded_cache_name = "enriched gatekeeper output"
        if not gatekeeper_result:
            gatekeeper_result = load_intermediate(f"gatekeeper_output_{today}.json")
            loaded_cache_name = "gatekeeper output"
        if not gatekeeper_result:
            print(f"{timestamp()} \u274c No cached gatekeeper output found for {today}.")
            return False
        selected = gatekeeper_result.get("selected", [])
        selected, section_warnings = normalize_sections(
            selected, "brief_section", "Gatekeeper cache"
        )
        gatekeeper_result["selected"] = selected
        for w in section_warnings:
            logger.warning(w)
            print(f"{timestamp()}   \u26a0\ufe0f  {w}")

        dropped = gatekeeper_result.get("dropped", [])
        gatekeeper_model_drops = list(dropped)
        assign_gatekeeper_ids(selected, today)
        selected = await dedup_selected_pool(selected, today, client)
        gatekeeper_result["selected"] = selected

        gatekeeper_output_json = json.dumps(gatekeeper_result, indent=2, ensure_ascii=False)
        print(f"{timestamp()} Loaded cached {loaded_cache_name}: {len(selected)} selected items")

    if not selected:
        print(f"{timestamp()} \u274c Gatekeeper selected 0 items. Nothing to write.")
        return False

    # === Manual Entry Injection ===
    # Manual entries bypass triage/content_filter/gatekeeper but flow through
    # ghostwriter and editor. Fetched live from Supabase so they work regardless
    # of --from-stage value (already-ingested entries won't re-appear).
    try:
        expire_old_entries()
        manual_rows = fetch_pending_manual_entries(today)
        if manual_rows:
            pending_manual_ids = _manual_entry_ids(manual_rows)
            existing_manual_ids = _selected_manual_entry_ids(selected)
            manual_entry_ids_to_mark.update(pending_manual_ids)

            fresh_rows = [
                row for row in manual_rows if str(row["id"]) not in existing_manual_ids
            ]
            if fresh_rows:
                manual_items = convert_to_gatekeeper_shape(fresh_rows, today)
                selected.extend(manual_items)
                gatekeeper_result["selected"] = selected
                print(f"{timestamp()} \u2705 Injected {len(manual_items)} manual entries")
            elif pending_manual_ids:
                print(
                    f"{timestamp()} Reusing {len(pending_manual_ids)} pending manual "
                    "entries already present in cached output"
                )
    except Exception as manual_err:
        logger.warning("Manual entry injection failed (non-fatal): %s", manual_err)
        print(f"{timestamp()}   \u26a0\ufe0f  Manual entry injection skipped: {manual_err}")

    source_metadata_lookup = build_source_metadata_lookup(selected)

    # === Content Enrichment (thin items only) ===
    print(f"{timestamp()} Checking for thin items to enrich...")
    selected, enrichment_usage = await enrich_selected_items(selected, client)
    gatekeeper_result["selected"] = selected
    total_input_tokens += enrichment_usage["input_tokens"]
    total_output_tokens += enrichment_usage["output_tokens"]

    # Web search date verification now runs earlier (pre-Gatekeeper); see
    # the call right after deduplicate_items() above.

    # Re-serialize with enrichment data for ghostwriter/editor
    gatekeeper_output_json = json.dumps(gatekeeper_result, indent=2, ensure_ascii=False)
    save_intermediate(f"enriched_gatekeeper_output_{today}.json", gatekeeper_result)

    # Brief Rationalization was removed — the per-section cap (15/section)
    # + section classifier provide sufficient balance. The analyst in the
    # curation workspace is the portfolio reviewer.

    # Recompute brief_summary to reflect post-processing mutations
    # (demerge, section normalization, repeat guard, rationalization)
    if "brief_summary" in gatekeeper_result:
        summary = gatekeeper_result["brief_summary"]
        summary["selected"] = len(selected)
        summary["dropped"] = len(dropped)
        section_dist = {}
        for item in selected:
            sec = item.get("brief_section", "")
            if sec in BRIEF_SECTIONS:
                section_dist[sec] = section_dist.get(sec, 0) + 1
        summary["section_distribution"] = section_dist

    # Re-serialize after rationalization
    gatekeeper_output_json = json.dumps(gatekeeper_result, indent=2, ensure_ascii=False)

    # === STEP 3: Ghostwriter ===
    if not from_stage or from_stage in ("scout", "content_filter", "gatekeeper", "ghostwriter"):
        print(f"{timestamp()} Running Ghostwriter — {len(selected)} items (Sonnet)")

        # --- Run the Ghostwriter via the chunked-by-section wrapper.
        #     Phase 2: up to 15 items per section × 5 sections = up to 75
        #     items overflows a single Sonnet call's 32k output budget, so
        #     fan out per section via asyncio.gather. Fast-path for small
        #     slates (≤15 items) runs a single call with no overhead.
        gw_result, gw_usage = await run_chunked_card_batches(
            client=client,
            gatekeeper_payload=gatekeeper_result,
            today=today,
            include_dropped=False,
        )
        total_input_tokens += gw_usage["input_tokens"]
        total_output_tokens += gw_usage["output_tokens"]

        if not gw_result:
            print(f"{timestamp()} \u274c Ghostwriter failed. Aborting.")
            return False

        all_gw_items = gw_result.get("items", [])
        print(f"{timestamp()}   \u2705 {len(all_gw_items)}/{len(selected)} items written")

        # Normalize/reject section drift before Editor.
        all_gw_items, gw_section_warnings = normalize_sections(
            all_gw_items, "section", "Ghostwriter"
        )
        for w in gw_section_warnings:
            logger.warning(w)
            print(f"{timestamp()}   \u26a0\ufe0f  {w}")

        apply_source_metadata(all_gw_items, source_metadata_lookup)
        ghostwriter_result = {"date": today, "items": all_gw_items}
        print(f"{timestamp()} \u2705 Ghostwriter complete: {len(all_gw_items)} items written")

        save_intermediate(f"ghostwriter_output_{today}.json", ghostwriter_result)
    else:
        # Load cached ghostwriter output
        ghostwriter_result = load_intermediate(f"ghostwriter_output_{today}.json")
        if not ghostwriter_result:
            print(f"{timestamp()} \u274c No cached ghostwriter output found for {today}.")
            return False
        cached_items = ghostwriter_result.get("items", [])
        cached_items, gw_section_warnings = normalize_sections(
            cached_items, "section", "Ghostwriter cache"
        )
        ghostwriter_result["items"] = cached_items
        for w in gw_section_warnings:
            logger.warning(w)
            print(f"{timestamp()}   \u26a0\ufe0f  {w}")
        apply_source_metadata(cached_items, source_metadata_lookup)
        print(f"{timestamp()} Loaded cached ghostwriter output: {len(ghostwriter_result.get('items', []))} items")

    # === Entity Classifier ===
    # Classifies each item's primary_entity into one of the 10 categories
    # aligned with entity_logos.category. The frontend uses the category
    # to pick an industry-appropriate lucide-react icon when the entity
    # doesn't have a curated logo in the entity_logos table.
    # Fail-open: on error, items pass through with
    # primary_entity_category=None and the frontend falls back to a
    # generic icon. Controlled by ENTITY_CLASSIFIER_ENABLED env flag.
    all_gw_items = ghostwriter_result.get("items", [])
    if ENTITY_CLASSIFIER_ENABLED and all_gw_items:
        unclassified = [
            it for it in all_gw_items
            if not it.get("primary_entity_category")
        ]
        classifiable = build_classifier_input_items(unclassified)
        if classifiable:
            print(f"{timestamp()} Running Entity Classifier on {len(classifiable)} item(s)...")
            classifier_result = None
            cls_correction = ""
            for attempt in range(2):
                if attempt > 0:
                    wait = 2 + random.uniform(0, 1)
                    print(f"{timestamp()}   Backing off {wait:.1f}s before retry...")
                    await asyncio.sleep(wait)
                try:
                    classifier_prompt = load_prompt(
                        "entity_classifier_prompt.md",
                        items_json=json.dumps(
                            classifiable, indent=2, ensure_ascii=False
                        ),
                    ) + cls_correction
                    classifier_result, cls_usage = await run_entity_classifier(
                        client, classifier_prompt
                    )
                    total_input_tokens += cls_usage["input_tokens"]
                    total_output_tokens += cls_usage["output_tokens"]
                    break
                except Exception as e:
                    if attempt == 0:
                        logger.warning(
                            f"Entity Classifier attempt 1 failed: {e}. Retrying..."
                        )
                        print(f"{timestamp()} ⚠️  Entity Classifier failed, retrying...")
                        cls_correction = build_retry_correction("entity_classifier", e)
                    else:
                        logger.error(
                            f"Entity Classifier attempt 2 failed: {e}", exc_info=True
                        )
                        print(
                            f"{timestamp()} ⚠️  Entity Classifier failed after 2 attempts — "
                            "items will lack category (fail-open)"
                        )
                        classifier_result = None

            annotated, unannotated = apply_entity_classifications(
                all_gw_items, classifier_result
            )
            print(
                f"{timestamp()} ✅ Entity Classifier: {annotated} classified, "
                f"{unannotated} un-annotated"
            )
            # Persist categories to the cached ghostwriter_output file so
            # downstream resumes and ingest pick them up.
            save_intermediate(f"ghostwriter_output_{today}.json", ghostwriter_result)
        else:
            # Every item already has a category (cache reload). Normalize so
            # absent items get an explicit None.
            apply_entity_classifications(all_gw_items, None)
    else:
        if not ENTITY_CLASSIFIER_ENABLED:
            print(
                f"{timestamp()} Entity Classifier skipped "
                "(ENTITY_CLASSIFIER_ENABLED=false)"
            )
        apply_entity_classifications(all_gw_items, None)

    # === Enrich all Ghostwriter items ===
    enrich_items(all_gw_items)  # Add deterministic UI metadata (code-based)

    ghostwriter_output_json = json.dumps(
        {"date": today, "items": all_gw_items}, indent=2, ensure_ascii=False
    )

    # === DRAFT MODE: Write draft slate instead of publishing ===
    # Hybrid curation is now the default production path. Setting
    # PIPELINE_DRAFT_MODE=false is only for explicit maintenance/backfill flows.
    PIPELINE_DRAFT_MODE = os.getenv("PIPELINE_DRAFT_MODE", "true").lower() == "true"

    if PIPELINE_DRAFT_MODE:
        # Phase 4 (2026-04-17): draft slate is exactly the main-Ghostwriter
        # output. Gatekeeper's per-section cap (up to 15/section) already
        # gave the analyst a complete slate; the old drop-Ghostwriter rescue
        # stage double-counted by re-classifying drops and stuffing them into
        # already-full sections, pushing pending_items past the 15/section
        # promise. Removed entirely — the analyst sees Gatekeeper's picks,
        # nothing else.
        draft_slate = list(all_gw_items)

        # Phase 4: back-attach event tuples from `all_items` (the
        # pre-ghostwriter set, which carries `_event_tuple` from the
        # Phase 2 extraction stage) onto the draft slate. The tuple
        # then flows into pending_items via raw_item JSONB, which
        # config._load_recent_pending_entries_from_supabase reads when
        # building the history-dedup baseline.
        # Match by source_url first (most reliable), fall back to item id.
        _tuple_by_url = {
            it.get("source_url"): it.get("_event_tuple")
            for it in all_items
            if it.get("_event_tuple") and it.get("source_url")
        }
        _tuple_by_id = {
            str(it.get("id", "")).strip(): it.get("_event_tuple")
            for it in all_items
            if it.get("_event_tuple") and it.get("id")
        }
        _attached = 0
        for gw_item in draft_slate:
            if gw_item.get("_event_tuple"):
                continue
            url = gw_item.get("source_url")
            if url and _tuple_by_url.get(url):
                gw_item["_event_tuple"] = _tuple_by_url[url]
                _attached += 1
                continue
            iid = str(gw_item.get("id", "")).strip()
            if iid and _tuple_by_id.get(iid):
                gw_item["_event_tuple"] = _tuple_by_id[iid]
                _attached += 1
        logger.info(
            "Phase 4: back-attached event tuples to %d/%d draft slate items "
            "(by source_url or id lookup against pre-ghostwriter all_items)",
            _attached, len(draft_slate),
        )

        # Warn if any analyst-added manual entries were dropped by Gatekeeper.
        # They used to be silently rescued by the drop-Ghostwriter; now they
        # just don't appear, and the analyst may need to re-add them. Keeping
        # this log so the regression is visible in operational review.
        dropped_manual_headlines: list[str] = []
        gw_ids = {str(i.get("id", "")).strip() for i in all_gw_items}
        for item in all_items:
            if not item.get("_manual_entry_id"):
                continue
            if str(item.get("id", "")).strip() in gw_ids:
                continue
            dropped_manual_headlines.append(item.get("headline", "")[:80])
        if dropped_manual_headlines:
            logger.warning(
                "Phase 4: %d manual entry/entries did not make the draft slate "
                "(Gatekeeper-dropped or rationalized away). Analyst may need to "
                "re-add: %s",
                len(dropped_manual_headlines),
                dropped_manual_headlines,
            )
            for h in dropped_manual_headlines:
                print(f"{timestamp()}   ⚠️  Manual entry dropped: {h}")

        print(f"{timestamp()} Draft slate: {len(draft_slate)} items "
              f"(Gatekeeper per-section selection; no drop-rescue)")

        # 6. Save pipeline stats
        pipeline_stats = {
            "run_date": today,
            "started_at": pipeline_started_at.isoformat(timespec="seconds"),
            "completed_at": current_gst_timestamp(),
            "duration_seconds": int(round(time.time() - pipeline_start)),
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_cost_usd": round(
                (total_input_tokens * INPUT_COST_PER_M + total_output_tokens * OUTPUT_COST_PER_M) / 1_000_000, 4
            ),
            # Gatekeeper drop accounting (added 2026-04-21). These surface
            # re-keyer compliance and Gatekeeper rewrite drift to the admin
            # Pipeline Runs view. Absent on --from-stage=ghostwriter/editor
            # resume paths where the Gatekeeper didn't re-run this invocation.
            "gatekeeper_rekeyer_match_rate": (
                gk_drop_accounting.get("rekeyer", {}).get("match_rate")
                if gk_drop_accounting else None
            ),
            "gatekeeper_rewrite_rate": (
                gk_drop_accounting.get("rewrite_rate")
                if gk_drop_accounting else None
            ),
            "gatekeeper_true_silent_count": (
                gk_drop_accounting.get("true_silent_count")
                if gk_drop_accounting else None
            ),
            # PHASE 3 (chunk-by-section, 2026-04-23): records whether the
            # chunked path ran, per-section input/output counts, retries,
            # post-retry silent counts, and cross-section cluster demotions.
            # Empty when the legacy single-call path ran or on resume.
            "gatekeeper_chunked_telemetry": (
                gk_drop_accounting.get("chunked", {})
                if gk_drop_accounting else {}
            ),
        }
        save_intermediate(f"pipeline_stats_{today}.json", pipeline_stats)

        # 7. Ingest the draft slate directly (no EiC selection step)
        from ingest_draft import ingest_draft, _get_supabase_client as _get_draft_sb
        sb = _get_draft_sb()
        ok = ingest_draft(
            sb,
            today,
            ghostwriter_items=draft_slate,
            pipeline_stats=pipeline_stats,
            gatekeeper_result=gatekeeper_result,
            source_metadata_lookup=source_metadata_lookup,
        )
        if ok:
            if manual_entry_ids_to_mark:
                try:
                    included_manual_ids = manual_entry_ids_ready_to_mark(
                        manual_entry_ids_to_mark,
                        draft_slate,
                    )
                    if included_manual_ids:
                        mark_entries_ingested(included_manual_ids)
                    skipped_manual_ids = sorted(
                        manual_entry_ids_to_mark - set(included_manual_ids)
                    )
                    if skipped_manual_ids:
                        logger.warning(
                            "Left %d manual entries pending because they were not present in the ingested draft slate: %s",
                            len(skipped_manual_ids),
                            skipped_manual_ids,
                        )
                except Exception as manual_mark_err:
                    logger.warning(
                        "Failed to mark manual entries ingested after draft ingest: %s",
                        manual_mark_err,
                    )
            print(f"{timestamp()} ✅ Draft slate ingested: {len(draft_slate)} items (all with prose)")
        else:
            print(f"{timestamp()} ❌ Draft slate ingest failed")
        return ok

    # === STEP 4: Editor ===
    print(f"{timestamp()} Running Editor on {len(all_gw_items)} items...")

    editor_result = None
    ed_correction = ""
    for attempt in range(2):
        if attempt > 0:
            wait = 2 + random.uniform(0, 1)
            print(f"{timestamp()}   Backing off {wait:.1f}s before retry...")
            await asyncio.sleep(wait)
        try:
            editor_prompt = load_prompt(
                "editor_prompt.md",
                gatekeeper_output=gatekeeper_output_json,
                ghostwriter_output=ghostwriter_output_json,
            ) + ed_correction
            editor_result, ed_usage = await run_editor(client, editor_prompt)
            total_input_tokens += ed_usage["input_tokens"]
            total_output_tokens += ed_usage["output_tokens"]
            break
        except Exception as e:
            if attempt == 0:
                logger.warning(f"Editor attempt 1 failed: {e}. Retrying...")
                print(f"{timestamp()} \u26a0\ufe0f  Editor failed, retrying...")
                ed_correction = build_retry_correction("editor", e)
            else:
                logger.error(f"Editor attempt 2 failed: {e}", exc_info=True)
                print(f"{timestamp()} \u274c Editor failed after 2 attempts: {e}")
                print(f"{timestamp()} Saving enriched Ghostwriter output as fallback brief.")
                completed_at = current_gst_timestamp()
                fallback = {
                    "brief_metadata": {
                        "date": today,
                        "generated_at": completed_at,
                    },
                    "items": all_gw_items,
                }
                restored_ids = reconcile_final_brief_with_selected(
                    fallback,
                    selected,
                    source_metadata_lookup,
                )
                if restored_ids:
                    print(
                        f"{timestamp()}   ⚠️  Restored {len(restored_ids)} missing selected "
                        "item(s) into fallback brief"
                    )
                apply_source_metadata(fallback.get("items", []), source_metadata_lookup)
                elapsed = time.time() - pipeline_start
                save_intermediate(
                    f"pipeline_stats_{today}.json",
                    {
                        "run_date": today,
                        "started_at": pipeline_started_at.isoformat(timespec="seconds"),
                        "completed_at": completed_at,
                        "duration_seconds": int(round(elapsed)),
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "total_cost_usd": round(
                            estimate_cost_usd(total_input_tokens, total_output_tokens), 4
                        ),
                    },
                )
                save_intermediate(f"brief_{today}.json", fallback)
                if manual_entry_ids_to_mark:
                    try:
                        included_manual_ids = manual_entry_ids_ready_to_mark(
                            manual_entry_ids_to_mark,
                            fallback.get("items", []),
                        )
                        if included_manual_ids:
                            mark_entries_ingested(included_manual_ids)
                        skipped_manual_ids = sorted(
                            manual_entry_ids_to_mark - set(included_manual_ids)
                        )
                        if skipped_manual_ids:
                            logger.warning(
                                "Left %d manual entries pending because they were not present in the fallback brief: %s",
                                len(skipped_manual_ids),
                                skipped_manual_ids,
                            )
                    except Exception as manual_mark_err:
                        logger.warning(
                            "Failed to mark manual entries ingested after fallback save: %s",
                            manual_mark_err,
                        )
                return False

    # Extract edit log stats
    edit_log = editor_result.get("edit_log", [])
    edits_count = len([e for e in edit_log if e.get("type") != "flag_for_listener"])
    print(f"{timestamp()} \u2705 Editor complete: {edits_count} edits made")

    final_brief = editor_result.get("final_brief", editor_result)

    # === STEP 5: Save final brief ===
    completed_at = current_gst_timestamp()
    final_brief.setdefault("brief_metadata", {})
    final_brief["brief_metadata"]["generated_at"] = completed_at
    restored_ids = reconcile_final_brief_with_selected(
        final_brief,
        selected,
        source_metadata_lookup,
        edit_log=edit_log,
    )
    if restored_ids:
        logger.warning(
            "Restored %d selected item(s) missing from final brief: %s",
            len(restored_ids),
            restored_ids,
        )
        print(
            f"{timestamp()}   ⚠️  Restored {len(restored_ids)} missing selected item(s) "
            "before final brief save"
        )
    final_brief = ensure_all_sections(final_brief, today)
    apply_source_metadata(final_brief.get("items", []), source_metadata_lookup)

    # Quality validation
    quality_warnings = validate_final_brief(final_brief)
    if quality_warnings:
        edit_log.extend(
            {
                "entry": "Brief-level",
                "type": "flag_for_listener",
                "original": "",
                "corrected": "",
                "reason": warning,
            }
            for warning in quality_warnings
        )
        print(f"{timestamp()} \u26a0\ufe0f  {len(quality_warnings)} quality warnings:")
        for w in quality_warnings:
            print(f"{timestamp()}   {w}")
    else:
        print(f"{timestamp()} \u2705 Quality checks passed (no warnings)")

    editor_result["edit_log"] = edit_log

    # Save intermediate editor output (full response including persisted warnings)
    save_intermediate(f"editor_output_{today}.json", editor_result)

    brief_path = save_intermediate(f"brief_{today}.json", final_brief)
    print(f"{timestamp()} Brief saved to {brief_path.relative_to(OUTPUT_DIR.parent)}")

    elapsed = time.time() - pipeline_start
    save_intermediate(
        f"pipeline_stats_{today}.json",
        {
            "run_date": today,
            "started_at": pipeline_started_at.isoformat(timespec="seconds"),
            "completed_at": completed_at,
            "duration_seconds": int(round(elapsed)),
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_cost_usd": round(
                estimate_cost_usd(total_input_tokens, total_output_tokens), 4
            ),
        },
    )
    if manual_entry_ids_to_mark:
        try:
            included_manual_ids = manual_entry_ids_ready_to_mark(
                manual_entry_ids_to_mark,
                final_brief.get("items", []),
            )
            if included_manual_ids:
                mark_entries_ingested(included_manual_ids)
            skipped_manual_ids = sorted(
                manual_entry_ids_to_mark - set(included_manual_ids)
            )
            if skipped_manual_ids:
                logger.warning(
                    "Left %d manual entries pending because they were not present in the final brief: %s",
                    len(skipped_manual_ids),
                    skipped_manual_ids,
                )
        except Exception as manual_mark_err:
            logger.warning(
                "Failed to mark manual entries ingested after brief save: %s",
                manual_mark_err,
            )
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    print(f"{timestamp()} Pipeline complete in {minutes}m {seconds}s.")
    print(f"{timestamp()} {format_cost(total_input_tokens, total_output_tokens)}")
    return True
