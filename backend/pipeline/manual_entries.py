"""
Fetch pending manual entries from Supabase and convert them
into pipeline-compatible item shapes (post-gatekeeper format).

Manual entries bypass triage, content filter, and gatekeeper but
flow through ghostwriter and editor for consistent prose quality.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from supabase import create_client, Client

logger = logging.getLogger(__name__)
GST = ZoneInfo("Asia/Dubai")

# The 5 canonical brief sections (mirrored from orchestrator)
BRIEF_SECTIONS = [
    "UAE",
    "Regional Research & Academic Events",
    "International Politics & Policy",
    "International Business & Technology",
    "Model Releases & Technical Developments",
]


def _get_supabase_client() -> Client:
    """Create a Supabase client using the service role key."""
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY"
        )
    return create_client(url, key)


def fetch_pending_manual_entries(target_date: str) -> list[dict]:
    """
    Query manual_entries where status='pending' and target_date matches.

    Args:
        target_date: Date string in YYYY-MM-DD format (GST).

    Returns:
        List of row dicts from the manual_entries table.
    """
    sb = _get_supabase_client()
    result = (
        sb.table("manual_entries")
        .select("*")
        .eq("status", "pending")
        .eq("target_date", target_date)
        .execute()
    )
    return result.data or []


def convert_to_gatekeeper_shape(entries: list[dict], today: str) -> list[dict]:
    """
    Convert manual entry rows into post-gatekeeper item dicts.

    Each item gets a stable ID derived from the manual_entries row id
    (e.g. '2026-03-18-m123' or '2026-03-18-m550e8400-e29b-41d4...').
    This keeps IDs collision-free across resume runs, even when only a
    subset of pending rows is converted after cached output already exists.
    """
    items = []
    for entry in entries:
        section = entry.get("brief_section") or ""
        if section not in BRIEF_SECTIONS:
            section = "UAE"  # safe fallback; ghostwriter can reassign

        # Derive placeholder headline from URL if not provided
        headline = entry.get("headline") or ""
        if not headline and entry.get("source_url"):
            domain = urlparse(entry["source_url"]).netloc.replace("www.", "")
            headline = f"Manual: {domain}"
        elif not headline:
            headline = "Manual entry"

        manual_entry_id = str(entry["id"])

        item = {
            "id": f"{today}-m{manual_entry_id}",
            "headline": headline,
            "summary": entry.get("summary", ""),
            "raw_content": entry.get("summary", ""),
            "source_url": entry.get("source_url", ""),
            "source": "Manual Entry",
            "source_scout": "manual",
            "brief_section": section,
            "composite_score": 8.0,
            "gatekeeper_override": True,
            "notes": entry.get("notes", ""),
            "_manual_entry_id": manual_entry_id,
        }
        items.append(item)

    return items


def mark_entries_ingested(entry_ids: list[str]) -> None:
    """Update status to 'ingested' and set ingested_at for consumed entries."""
    if not entry_ids:
        return
    sb = _get_supabase_client()
    now_iso = datetime.now(GST).isoformat()
    sb.table("manual_entries").update({
        "status": "ingested",
        "ingested_at": now_iso,
    }).in_("id", entry_ids).execute()
    logger.info("Marked %d manual entries as ingested", len(entry_ids))


def expire_old_entries() -> None:
    """
    Set status='expired' for pending entries whose target_date
    is before today (GST). Prevents stale items from leaking
    into future briefs.
    """
    today_str = datetime.now(GST).strftime("%Y-%m-%d")
    sb = _get_supabase_client()
    result = (
        sb.table("manual_entries")
        .update({"status": "expired"})
        .eq("status", "pending")
        .lt("target_date", today_str)
        .execute()
    )
    expired_count = len(result.data) if result.data else 0
    if expired_count:
        logger.info("Expired %d stale manual entries", expired_count)
