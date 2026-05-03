import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from env_loader import load_project_env

# Load environment variables
load_project_env()

# API settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"
CONTENT_FILTER_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 16000

# Stage-specific timeouts (seconds)
STAGE_TIMEOUTS = {
    "triage": 120,             # 2 min
    "content_filter": 120,     # 2 min
    "history_dedup": 300,      # 5 min (Haiku, ~100 items vs ~180 history entries)
    "synthesis": 600,          # 10 min (Haiku, ~200 items + prior-brief context, large output)
    "entity_classifier": 120,  # 2 min (Haiku, ~15 items, tiny output)
    "gatekeeper": 600,         # 10 min (100+ items after newsletter splitting)
    "ghostwriter": 600,        # 10 min (large input + output)
    "editor": 600,             # 10 min (large output, 32K max_tokens)
}

# Phase 2 rollback flag. When False, the Synthesis stage is skipped and the
# legacy fuzzy-string previous-brief overlap filter (flag_previous_brief_overlaps
# + apply_continuity_penalty) is used instead. Flip to "false" via env if
# Synthesis misbehaves in production — no redeploy required.
SYNTHESIS_ENABLED = os.getenv("SYNTHESIS_ENABLED", "true").lower() == "true"

# When true, the Entity Classifier stage runs after Ghostwriter and tags each
# item with a `primary_entity_category` (one of 10 values matching
# entity_logos.category). Used by the frontend to pick an industry-appropriate
# icon when the entity doesn't have a logo in the entity_logos table. Flip
# to "false" via env to disable without a redeploy.
ENTITY_CLASSIFIER_ENABLED = os.getenv(
    "ENTITY_CLASSIFIER_ENABLED", "true"
).lower() == "true"

# When true, a Haiku-powered history-dedup stage runs after Content Filter
# and before Synthesis. It semantically drops items that repeat recent
# published briefs OR recent analyst pending-items slates — catching
# paraphrases the deterministic `flag_previous_brief_overlaps` misses.
# Flip to "false" via env to disable without a redeploy.
HISTORY_DEDUP_ENABLED = os.getenv(
    "HISTORY_DEDUP_ENABLED", "true"
).lower() == "true"

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Timezone
GST = ZoneInfo("Asia/Dubai")  # GST = UTC+4
LOOKBACK_CUTOFF_HOUR = 6
SCRAPER_GRACE_HOURS = 24  # Extra lookback for scraped (non-newsletter) sources

# User profile (hardcoded for Phase 1)
USER_PROFILE = """Name: Prof. Eric Xing
Role: President, Mohamed bin Zayed University of Artificial Intelligence (MBZUAI)
Location: Abu Dhabi, UAE
Priorities: UAE AI ecosystem, regional competition (especially KAUST),
global AI landscape, model releases, policy affecting UAE tech access,
higher education competitive positioning
Tracked entities: G42, TII, Presight, ADNOC, Mubadala, KAUST, Khalifa University,
NYUAD, HBKU, QCRI, OpenAI, Anthropic, Google DeepMind, Meta AI, NVIDIA"""

# Delivery format
DELIVERY_FORMAT = "portal"


# Required collection categories — pipeline aborts if these have 0 items
REQUIRED_SCOUTS = {"uae"}


def get_today_date() -> str:
    """Return today's date in YYYY-MM-DD format (GST)."""
    return datetime.now(GST).strftime("%Y-%m-%d")


def get_date_variable() -> str:
    """Calculate the lookback cutoff based on day of week.

    The brief runs at 6:00am GST on weekdays:
    - Tue-Fri: lookback to 6:00am GST previous day (24h)
    - Monday: lookback to Friday 6:00am GST (72h, covering weekend)
    - Sat/Sun: no runs (return None-like marker)
    """
    return f"{get_lookback_cutoff_date():%Y-%m-%d} 6:00am GST"



def _days_back_for_lookback(now: datetime) -> int:
    """Return how many days the lookback window should step back."""
    return 3 if now.weekday() == 0 else 1


def get_lookback_cutoff_date() -> datetime:
    """Return the lookback cutoff as a GST-aware datetime.

    Mon: cutoff = Friday 6:00am GST (covers Fri/Sat/Sun/Mon).
    Tue-Sun: cutoff = yesterday 6:00am GST.
    """
    now = datetime.now(GST)
    return now.replace(
        hour=LOOKBACK_CUTOFF_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    ) - timedelta(days=_days_back_for_lookback(now))


def get_previous_brief() -> str:
    """Find the most recent brief JSON in the output folder.

    Returns the contents of the most recent brief file, or a
    default message if no previous brief exists.
    """
    output_dir = OUTPUT_DIR
    brief_files = sorted(output_dir.glob("brief_*.json"), reverse=True)

    for bf in brief_files:
        # Don't load today's brief as "previous"
        today = get_today_date()
        if today not in bf.name:
            try:
                return bf.read_text(encoding="utf-8")
            except Exception:
                continue

    return "No previous brief available. This is the first run."


def get_previous_brief_headlines(max_days: int = 3) -> str:
    """Extract recent PUBLISHED brief headlines + context for LLM prompts.

    Used by `{previous_brief_headlines}` substitution in
    `prompts/loader.py`. Scope is limited to published items so prompts
    stay lean — do not include unpublished `pending_items` here, or every
    Gatekeeper/Synthesis call balloons by 5×.

    For the richer "has the analyst ever seen this?" check used by the
    history-dedup stage and `flag_previous_brief_overlaps`, use
    `get_recent_history_headlines()` instead.

    Returns JSON with:
      - brief_date: which day the item appeared in
      - headline, section, entities: for matching
      - main_bullet: included for contextual repeat detection
    """
    today = get_today_date()
    all_headlines = _load_recent_brief_entries_from_supabase(today, max_days=max_days)
    if not all_headlines:
        all_headlines = _load_recent_brief_entries_from_files(today, max_days=max_days)

    if not all_headlines:
        return "No previous brief available. This is the first run."
    return json.dumps(all_headlines, indent=2, ensure_ascii=False)


# Sentence boundary used by `_trim_history_entry_for_dedup`. Splits on a
# terminator (.!?) followed by whitespace, so the first sentence ends at
# the first such boundary. Conservative: doesn't try to handle "Inc." /
# "U.S." abbreviations, since those rarely appear at the END of sentence 1
# in Ghostwriter prose, and a slightly long first-sentence carries less
# risk than over-aggressive splitting.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def _trim_history_entry_for_dedup(entry: dict) -> dict:
    """Return a slimmed copy of a recent-history entry for the dedup judge.

    Reduces the surface area Haiku sees so buried side-mentions in prior
    items can't masquerade as full coverage of a future event. Specifically:

    - Truncates `main_bullet` to its FIRST SENTENCE only.
    - Drops any `context` field if present (defensive — current loaders
      don't emit it, but if a future loader does, we don't want it
      leaking into the dedup baseline).
    - Keeps `headline`, `brief_date`, `section`, and `entities` intact —
      those are what the judge actually needs to recognize a paraphrase.

    Background: on 2026-04-24, the prior day's pending item
    "Meta installs keystroke and screen-capture software..." had a
    main_bullet whose THIRD sentence was a forward-looking aside —
    "Meta is planning 10% global layoffs starting May 20...". The
    history_dedup judge read that aside as coverage of the May 20 layoff
    event itself and dropped today's actual layoff announcement as a
    repeat. The first sentence of that main_bullet describes the MCI
    surveillance tool only and is a true semantic fingerprint of the
    prior story.
    """
    if not isinstance(entry, dict):
        return entry
    main_bullet = (entry.get("main_bullet") or "").strip()
    if main_bullet:
        first_sentence = _SENTENCE_BOUNDARY_RE.split(main_bullet, maxsplit=1)[0]
    else:
        first_sentence = ""
    out = {
        "brief_date": entry.get("brief_date", ""),
        "headline": entry.get("headline", ""),
        "section": entry.get("section", ""),
        "entities": entry.get("entities", []),
        "main_bullet": first_sentence,
    }
    # Phase 4: preserve event_tuple through the trim — tuple-aware
    # history_dedup needs it on the recent_history entries to do
    # mechanical comparison. The dedup judge prompt itself never sees
    # this field; only the Python history_dedup logic reads it.
    event_tuple = entry.get("event_tuple")
    if isinstance(event_tuple, dict) and event_tuple:
        out["event_tuple"] = event_tuple
    return out


def get_recent_history_headlines(max_days: int = 3) -> str:
    """Extract recent history covering BOTH published briefs and draft slates.

    This is the "full memory" view: every story that's either been
    published OR shown to the analyst in a pending curation in the last
    `max_days` days. Used by history-dedup stages that need to prevent
    the same story from being re-surfaced day after day regardless of
    whether the analyst selected, rejected, or left it idle.

    Published entries use a plain ISO date (`"2026-04-16"`) as
    `brief_date`. Pending-slate entries use `"pending 2026-04-16"` so log
    messages can distinguish the source of a match.

    Each entry is trimmed via `_trim_history_entry_for_dedup` before being
    serialized, so the dedup judge sees only headline + first sentence of
    main_bullet (plus brief_date / section / entities). See that helper
    for the 2026-04-24 incident that motivated the trim.

    Returns JSON in the same shape as `get_previous_brief_headlines`.
    """
    today = get_today_date()
    published = _load_recent_brief_entries_from_supabase(today, max_days=max_days)
    pending = _load_recent_pending_entries_from_supabase(today, max_days=max_days)

    merged = _merge_history_entries(published, pending)
    if not merged:
        merged = _load_recent_brief_entries_from_files(today, max_days=max_days)

    if not merged:
        return "No previous brief available. This is the first run."
    trimmed = [_trim_history_entry_for_dedup(entry) for entry in merged]
    return json.dumps(trimmed, indent=2, ensure_ascii=False)


def _merge_history_entries(
    published: list[dict],
    pending: list[dict],
) -> list[dict]:
    """Merge published-brief and pending-slate entries, dropping duplicates.

    A published item was a pending item first, so the same (brief_date,
    headline) tuple appears in both lists when an item was selected and
    published. Keep the published row (richer entities) and drop the
    duplicate pending row. The pending list uses a "pending " brief_date
    prefix for log readability, so we strip that for the dedup key.
    """
    def _key(entry: dict) -> tuple[str, str]:
        brief_date = entry.get("brief_date", "")
        if brief_date.startswith("pending "):
            brief_date = brief_date[len("pending "):]
        return (brief_date, entry.get("headline", "").strip().lower())

    seen: set[tuple[str, str]] = set()
    merged: list[dict] = []

    for entry in published:
        key = _key(entry)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)

    for entry in pending:
        key = _key(entry)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)

    return merged


def _load_recent_brief_entries_from_files(today: str, max_days: int = 3) -> list[dict]:
    """Load recent brief history from local brief_*.json artifacts."""
    brief_files = sorted(OUTPUT_DIR.glob("brief_*.json"), reverse=True)
    all_headlines: list[dict] = []
    days_found = 0

    for bf in brief_files:
        if today in bf.name:
            continue
        if days_found >= max_days:
            break
        try:
            data = json.loads(bf.read_text(encoding="utf-8"))
            brief_date = bf.stem.replace("brief_", "")
            for item in data.get("items", []):
                if item.get("is_placeholder"):
                    continue
                event_tuple = item.get("_event_tuple") or item.get("event_tuple")
                all_headlines.append({
                    "brief_date": brief_date,
                    "headline": item.get("headline", ""),
                    "section": item.get("section", ""),
                    "entities": item.get("entities", []),
                    "main_bullet": item.get("main_bullet", ""),
                    "event_tuple": event_tuple if isinstance(event_tuple, dict) else None,
                })
            days_found += 1
        except Exception:
            continue

    return all_headlines


def _load_recent_brief_entries_from_supabase(today: str, max_days: int = 3) -> list[dict]:
    """Load recent brief history from Supabase when service-role creds exist."""
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return []

    try:
        from supabase import create_client
    except Exception:
        return []

    try:
        sb = create_client(url, key)
        resp = (
            sb.table("briefs")
            .select("brief_date")
            .lt("brief_date", today)
            .order("brief_date", desc=True)
            .limit(max_days + 4)
            .execute()
        )
        rows = resp.data or []
        brief_dates: list[str] = []
        for row in rows:
            brief_date = row.get("brief_date")
            if brief_date and brief_date not in brief_dates:
                brief_dates.append(brief_date)
            if len(brief_dates) >= max_days:
                break

        if not brief_dates:
            return []

        # Read from briefs.raw_json (source of truth). Previously this
        # queried brief_items.raw_content; migration 018 narrowed
        # brief_items to a cross-date index. raw_content is retained on
        # brief_items for historical audit but is no longer read by live
        # code.
        briefs_resp = (
            sb.table("briefs")
            .select("brief_date,raw_json")
            .in_("brief_date", brief_dates)
            .execute()
        )
        brief_rows = briefs_resp.data or []
        date_rank = {brief_date: idx for idx, brief_date in enumerate(brief_dates)}

        flattened: list[dict] = []
        for brief_row in brief_rows:
            brief_date = brief_row.get("brief_date", "")
            raw_json = brief_row.get("raw_json") or {}
            items = raw_json.get("items", []) if isinstance(raw_json, dict) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("is_placeholder") or item.get("depth") == "placeholder":
                    continue
                entities = item.get("entities", [])
                # Phase 4: pull `_event_tuple` from the published item if
                # present so tuple-aware history_dedup can compare today's
                # tuples against historical ones from briefs.raw_json.
                # Falls back to None for pre-Phase-2 items.
                event_tuple = item.get("_event_tuple") or item.get("event_tuple")
                flattened.append({
                    "brief_date": brief_date,
                    "headline": item.get("headline", ""),
                    "section": item.get("section", ""),
                    "entities": entities if isinstance(entities, list) else [],
                    "main_bullet": item.get("main_bullet", ""),
                    "event_tuple": event_tuple if isinstance(event_tuple, dict) else None,
                })

        flattened.sort(
            key=lambda row: (
                date_rank.get(row.get("brief_date", ""), 999),
                row.get("headline", ""),
            )
        )
        return flattened
    except Exception:
        return []


def _load_recent_pending_entries_from_supabase(
    today: str,
    max_days: int = 3,
) -> list[dict]:
    """Load recent draft-slate entries from `pending_briefs` + `pending_items`.

    Mirrors `_load_recent_brief_entries_from_supabase` but reads the
    curation queue instead of published briefs. This catches items the
    analyst was shown yesterday but did not publish — without this, the
    pipeline has no memory of those rejections and re-surfaces the same
    URLs every day.

    Returns the same shape as `_load_recent_brief_entries_from_supabase`
    so the two lists can be merged. The `brief_date` field is prefixed
    with "pending " so log output (`flag_previous_brief_overlaps`)
    distinguishes the source of the match.
    """
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return []

    try:
        from supabase import create_client
    except Exception:
        return []

    try:
        sb = create_client(url, key)
        resp = (
            sb.table("pending_briefs")
            .select("id,brief_date")
            .lt("brief_date", today)
            .order("brief_date", desc=True)
            .limit(max_days + 4)
            .execute()
        )
        rows = resp.data or []
        # Deduplicate by date (in theory unique, but defensive) and cap.
        brief_id_to_date: dict[str, str] = {}
        date_seen: set[str] = set()
        for row in rows:
            brief_date = row.get("brief_date")
            brief_id = row.get("id")
            if not brief_date or not brief_id or brief_date in date_seen:
                continue
            date_seen.add(brief_date)
            brief_id_to_date[brief_id] = brief_date
            if len(brief_id_to_date) >= max_days:
                break

        if not brief_id_to_date:
            return []

        items_resp = (
            sb.table("pending_items")
            .select("pending_brief_id,headline,section,main_bullet,raw_item")
            .in_("pending_brief_id", list(brief_id_to_date.keys()))
            .execute()
        )
        items = items_resp.data or []

        date_rank = {
            brief_date: idx
            for idx, brief_date in enumerate(
                sorted(brief_id_to_date.values(), reverse=True)
            )
        }

        normalized: list[dict] = []
        for item in sorted(
            items,
            key=lambda row: (
                date_rank.get(
                    brief_id_to_date.get(row.get("pending_brief_id", ""), ""),
                    999,
                ),
                row.get("headline", ""),
            ),
        ):
            brief_date = brief_id_to_date.get(
                item.get("pending_brief_id", ""), ""
            )
            raw_item = item.get("raw_item") or {}
            entities = (
                raw_item.get("entities", []) if isinstance(raw_item, dict) else []
            )
            # Phase 4: surface `_event_tuple` from raw_item if present so
            # tuple-aware history_dedup can compare today's tuples against
            # historical ones. Falls back to None for pre-Phase-2 items.
            event_tuple = (
                raw_item.get("_event_tuple")
                if isinstance(raw_item, dict)
                else None
            )
            normalized.append({
                "brief_date": f"pending {brief_date}",
                "headline": item.get("headline", ""),
                "section": item.get("section", ""),
                "entities": entities if isinstance(entities, list) else [],
                "main_bullet": item.get("main_bullet", ""),
                "event_tuple": event_tuple if isinstance(event_tuple, dict) else None,
            })

        return normalized
    except Exception:
        return []
