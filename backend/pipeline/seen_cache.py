"""Seen-URL cache for infrequent-publishing collectors.

Stores the set of URLs each cached collector returned on its last run.
On the next run, if a collector returns the exact same URLs, all its
items are skipped (nothing new).  If any new URLs appear, only the new
items are passed into the pipeline.

Primary storage: Supabase ``public.scout_seen_urls`` (survives Cloud Run
container restarts).  Fallback storage: ``<output_dir>/seen_urls_cache.json``
on disk — used only when Supabase credentials are not configured (local
dev / tests).

Before 2026-04-15 this module stored the cache exclusively in
``backend/output/seen_urls_cache.json``, which is ephemeral on Cloud Run.
The cache reset every run, which let infrequent sources (tii/g42/khazna/
presight) re-yield the same stale press releases every day, where they
were then culled at date_filter.  Persisting the cache in Supabase fixes
that root cause.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

CACHE_FILENAME = "seen_urls_cache.json"
SUPABASE_TABLE = "scout_seen_urls"

# Collectors whose output is cached between runs.  High-volume sources
# (wam, newsletters) and special sources (admo, mbzuai_events, x_tahnoon)
# are intentionally excluded.
CACHED_COLLECTORS: set[str] = {"tii", "g42", "khazna", "presight"}

DUBAI_TZ = ZoneInfo("Asia/Dubai")


# ------------------------------------------------------------------
# Supabase client (lazy)
# ------------------------------------------------------------------

def _get_supabase_client():
    """Return a Supabase client using service-role credentials, or None.

    Returns None if the env vars aren't set (local dev / tests without
    Supabase configured) so callers can fall back to disk-based caching.
    """
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client  # local import: optional dep
    except ImportError:
        log.warning("seen_cache: supabase-py not installed, using disk fallback")
        return None
    try:
        return create_client(url, key)
    except Exception as exc:  # pragma: no cover — defensive
        log.warning("seen_cache: failed to create Supabase client (%s)", exc)
        return None


# ------------------------------------------------------------------
# Load / save
# ------------------------------------------------------------------

def load_cache(output_dir: Path) -> dict[str, Any]:
    """Read the seen-URL cache.

    Prefers Supabase (``public.scout_seen_urls``); falls back to the
    legacy JSON file in ``output_dir`` when Supabase isn't configured.
    Returns ``{}`` on any error so callers treat the cache as empty.
    """
    sb = _get_supabase_client()
    if sb is not None:
        try:
            rows = (
                sb.table(SUPABASE_TABLE)
                .select("collector_name,url,last_seen_at")
                .in_("collector_name", sorted(CACHED_COLLECTORS))
                .execute()
                .data
                or []
            )
        except Exception as exc:
            log.warning(
                "seen_cache: Supabase load failed (%s); falling back to disk", exc
            )
        else:
            cache: dict[str, Any] = {}
            for row in rows:
                name = row.get("collector_name")
                url = row.get("url")
                if not name or not url:
                    continue
                entry = cache.setdefault(name, {"urls": [], "count": 0})
                entry["urls"].append(url)
            for name, entry in cache.items():
                entry["urls"].sort()
                entry["count"] = len(entry["urls"])
            log.info(
                "seen_cache: loaded %d collector(s) from Supabase (%d URLs total)",
                len(cache), sum(e["count"] for e in cache.values()),
            )
            return cache

    # Disk fallback
    path = output_dir / CACHE_FILENAME
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            log.warning("seen_cache: unexpected format, resetting")
            return {}
        return data
    except Exception as exc:
        log.warning("seen_cache: failed to load from disk (%s), treating as empty", exc)
        return {}


def save_cache(output_dir: Path, cache: dict[str, Any]) -> None:
    """Persist the cache.

    Writes to Supabase (``public.scout_seen_urls``) when configured;
    otherwise writes atomically to the legacy JSON file in ``output_dir``.

    On Supabase, each (collector_name, url) row is upserted so
    ``last_seen_at`` advances on every run while ``first_seen_at`` is
    preserved for any row that already existed.
    """
    sb = _get_supabase_client()
    if sb is not None:
        now_iso = datetime.now(DUBAI_TZ).isoformat()
        upserts: list[dict[str, Any]] = []
        for collector_name, entry in cache.items():
            if collector_name not in CACHED_COLLECTORS:
                continue
            if not isinstance(entry, dict):
                continue
            for url in entry.get("urls", []) or []:
                if not url:
                    continue
                upserts.append(
                    {
                        "collector_name": collector_name,
                        "url": url,
                        "last_seen_at": now_iso,
                    }
                )

        if upserts:
            try:
                # Upsert in chunks to avoid hitting row-size/request limits.
                CHUNK = 500
                for i in range(0, len(upserts), CHUNK):
                    sb.table(SUPABASE_TABLE).upsert(
                        upserts[i : i + CHUNK],
                        on_conflict="collector_name,url",
                        # DO NOT overwrite first_seen_at — it's default-now on
                        # insert; upsert ignores default columns already set.
                    ).execute()
                log.info(
                    "seen_cache: upserted %d rows to Supabase across %d collector(s)",
                    len(upserts), len({u["collector_name"] for u in upserts}),
                )
                return
            except Exception as exc:
                log.warning(
                    "seen_cache: Supabase upsert failed (%s); writing disk fallback",
                    exc,
                )

    # Disk fallback (also used when Supabase write succeeded but the caller
    # still wants a local snapshot — harmless on Cloud Run where the file
    # disappears at container exit).
    path = output_dir / CACHE_FILENAME
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
    except Exception as exc:
        log.warning("seen_cache: failed to save to disk (%s)", exc)
        tmp.unlink(missing_ok=True)


# ------------------------------------------------------------------
# Filter & update
# ------------------------------------------------------------------

def filter_new_items(
    collector_name: str,
    articles: list,
    cache: dict[str, Any],
) -> tuple[list, int]:
    """Return only articles whose URL is not in the cache.

    Returns ``(new_articles, num_skipped)``.  If there is no cache
    entry for this collector, all articles pass through.
    """
    entry = cache.get(collector_name)
    if not entry or not isinstance(entry, dict):
        return articles, 0

    cached_urls: set[str] = set(entry.get("urls", []))
    if not cached_urls:
        return articles, 0

    new = [a for a in articles if getattr(a, "url", None) not in cached_urls]
    skipped = len(articles) - len(new)
    return new, skipped


def update_cache_entry(
    collector_name: str,
    articles: list,
    cache: dict[str, Any],
) -> None:
    """Record the current URL set for *collector_name*."""
    urls = sorted({getattr(a, "url", "") for a in articles} - {""})
    cache[collector_name] = {
        "urls": urls,
        "count": len(urls),
        "updated_at": datetime.now(DUBAI_TZ).isoformat(),
    }
