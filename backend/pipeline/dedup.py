"""Three-stage deduplication for collected items.

Stage 0: URL match — items with the same canonicalized source_url are the
         same article, regardless of how their headlines differ.
Stage 1: Fuzzy headline match (SequenceMatcher > threshold) — free, instant.
Stage 2: Semantic dedup via Haiku — one API call for all headlines.

Runs in the orchestrator between date filtering and the content filter, and
again on the post-Gatekeeper selected pool to catch items that survived Stage
1+2 but later get rewritten into near-identical headlines by Ghostwriter.
"""

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import parse_qsl, urlparse, urlunparse

from pipeline.json_utils import safe_parse_json

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = float(os.environ.get("DEDUP_FUZZY_THRESHOLD", "0.6"))

# Minimum distinctive-token overlap between keeper and loser headlines
# required to accept a Haiku semantic-dedup cluster. Mirrors the
# distinctive-token guard the fuzzy stage already uses at L309 — without
# this, Haiku occasionally collapses topically-similar-but-event-different
# items into one cluster (see 2026-04-23 BlackRock↔Kenya incident).
SEMANTIC_DEDUP_MIN_SHARED_TOKENS = int(
    os.environ.get("DEDUP_SEMANTIC_MIN_SHARED_TOKENS", "2")
)

# Query params that don't affect article identity. Stripped during URL
# canonicalization so the same article shared with different tracking
# parameters gets correctly deduped.
_TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "ref", "referrer", "source", "fbclid", "gclid",
    "mc_cid", "mc_eid", "_hsenc", "_hsmi",
}

# Boilerplate tokens that appear across unrelated stories sharing the same
# headline template (e.g. "$X B at $Y B valuation"). Without stripping these,
# the fuzzy matcher collapses every fundraising / deal story into one
# super-cluster because SequenceMatcher scores template overlap at ~0.60–0.65
# even when the actual entities are disjoint (see 2026-04-20 incident where
# Cursor + DeepSeek + Canva + Slash all merged into the San Diego Padres sale).
_BOILERPLATE_TOKENS = {
    # Structural / function words
    "the", "and", "for", "with", "from", "this", "that", "its", "their",
    "after", "amid", "over", "into", "onto", "about", "between", "before",
    # Money / size descriptors
    "billion", "million", "thousand", "valuation", "worth", "record", "first",
    "second", "third", "new", "latest", "top", "major",
    # Deal / transaction verbs
    "raises", "raising", "raised", "seeks", "seeking", "funds", "funding",
    "round", "sells", "sell", "sold", "sale", "deal", "deals", "acquires",
    "acquired", "buys", "buying", "bought", "announces", "announced",
    "launches", "launched", "releases", "released", "opens", "opening",
    "plans", "planning", "considers", "considering", "near", "eyes", "nears",
    # News framing verbs
    "says", "said", "reports", "reported", "reveals", "revealed",
    "confirms", "confirmed", "meets", "meeting", "calls", "called",
}


def _canonicalize_url(url: str) -> str:
    """Return a comparable form of a URL, or '' if it's not usable for dedup.

    Lowercases scheme+host, strips fragment, strips trailing slash from path,
    and removes common tracking query params. Empty/invalid URLs return ''
    so the caller can skip them — we never want to merge two items just
    because both have no URL.
    """
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return ""
    if not parsed.netloc:
        return ""
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    kept_query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_QUERY_PARAMS
    ]
    query = "&".join(f"{k}={v}" for k, v in kept_query)
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _safe_date_lt(a: str, b: str) -> bool:
    """Compare two date strings, preferring ISO format.

    Falls back to lexicographic comparison with a warning if either
    value doesn't look like YYYY-MM-DD.
    """
    if a and b and _ISO_DATE_RE.match(a) and _ISO_DATE_RE.match(b):
        return a < b
    if a and b and (not _ISO_DATE_RE.match(a) or not _ISO_DATE_RE.match(b)):
        logger.debug("dedup: non-ISO date comparison: %r vs %r", a, b)
    return a < b


def _normalize_headline(headline: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    h = headline.lower()
    h = re.sub(r"[^\w\s]", "", h)
    h = re.sub(r"\s+", " ", h).strip()
    return h


def _distinctive_tokens(headline: str) -> set[str]:
    """Content-bearing tokens from a headline, used as a fuzzy-merge guard.

    Returns tokens (length ≥ 3) from the normalized headline, excluding the
    template/boilerplate set. Pairs of headlines with zero overlap here are
    never merged by fuzzy dedup, regardless of SequenceMatcher similarity —
    this prevents unrelated stories sharing a template (e.g. "X raises $Y at
    $Z valuation") from being transitively unioned.
    """
    normalized = _normalize_headline(headline)
    return {
        tok for tok in normalized.split()
        if len(tok) >= 3 and tok not in _BOILERPLATE_TOKENS
    }


def _richness_score(item: dict) -> int:
    """Score an item by content richness. Higher = richer."""
    score = len(item.get("raw_content") or "")
    score += len(item.get("additional_context") or "") * 2
    score += len(item.get("also_covered_by") or []) * 100
    # Prefer items with a source URL — the enricher and ghostwriter need it,
    # and losing the URL during dedup merging is hard to recover from.
    if item.get("source_url"):
        score += 200
    return score


def _merge_group(group: list[dict]) -> dict:
    """Merge a group of duplicate items, keeping the richest as base."""
    group.sort(key=_richness_score, reverse=True)
    base = dict(group[0])

    # Collect all sources with earliest publication date
    all_sources: dict[str, str] = {}
    for item in group:
        src_name = item.get("source", "")
        src_date = item.get("date", "")
        if src_name:
            if src_name not in all_sources or _safe_date_lt(src_date, all_sources.get(src_name, "9")):
                all_sources[src_name] = src_date
        for s in item.get("also_covered_by", []):
            if isinstance(s, dict):
                name = s.get("source", "")
                d = s.get("date", "")
            else:
                name = str(s)
                d = item.get("date", "")
            if name:
                if name not in all_sources or _safe_date_lt(d, all_sources.get(name, "9")):
                    all_sources[name] = d
    all_sources.pop(base.get("source", ""), None)
    base["also_covered_by"] = [
        {"source": name, "date": d}
        for name, d in sorted(all_sources.items())
    ]

    # Merge entities (unique, preserve order from base first)
    seen = set()
    merged_entities = []
    for item in group:
        for e in item.get("entities", []):
            key = e.lower()
            if key not in seen:
                seen.add(key)
                merged_entities.append(e)
    base["entities"] = merged_entities

    # Merge additional_context
    contexts = []
    for item in group:
        ctx = (item.get("additional_context") or "").strip()
        if ctx and ctx not in contexts:
            contexts.append(ctx)
    if contexts:
        base["additional_context"] = " | ".join(contexts)

    # Preserve uae_exposure if any duplicate has it
    for item in group:
        if item.get("uae_exposure") and not base.get("uae_exposure"):
            base["uae_exposure"] = item["uae_exposure"]

    # Track which scouts contributed
    scouts = {s for item in group if (s := item.get("source_scout"))}
    if len(scouts) > 1:
        base["_merged_from_scouts"] = sorted(scouts)

    return base


# ── Stage 0: URL match ───────────────────────────────────────────────────────


def _url_dedup(items: list[dict]) -> tuple[list[dict], int, list[dict], list[dict]]:
    """Group items by canonicalized source_url and merge each group.

    Items without a usable URL (empty, malformed, or no host) are passed
    through untouched — Stage 1/2 will handle them. Same return shape as
    ``_fuzzy_dedup``.
    """
    if not items:
        return [], 0, [], []

    by_url: dict[str, list[int]] = {}
    no_url: list[int] = []
    for idx, item in enumerate(items):
        canon = _canonicalize_url(item.get("source_url", ""))
        if canon:
            by_url.setdefault(canon, []).append(idx)
        else:
            no_url.append(idx)

    deduplicated: list[dict] = [items[i] for i in no_url]
    merge_log: list[dict] = []
    dropped_rows: list[dict] = []
    total_merged = 0

    for canon_url, idxs in by_url.items():
        group = [items[i] for i in idxs]
        if len(group) == 1:
            deduplicated.append(group[0])
            continue
        sorted_group = sorted(group, key=_richness_score, reverse=True)
        merged = _merge_group(group)
        deduplicated.append(merged)
        total_merged += len(group) - 1
        kept_headline = merged.get("headline", "")
        for loser in sorted_group[1:]:
            dropped_rows.append(_dedup_drop_row(loser, kept_headline, "url"))
        merge_log.append({
            "kept_headline": kept_headline,
            "merged_count": len(group),
            "merged_headlines": [g.get("headline", "") for g in group],
            "canonical_url": canon_url,
        })
        logger.info(
            "Dedup (url): merged %d items sharing %s -> '%s'",
            len(group), canon_url, kept_headline[:60],
        )

    return deduplicated, total_merged, merge_log, dropped_rows


# ── Stage 1: Fuzzy headline match ────────────────────────────────────────────


def _dedup_drop_row(item: dict, kept_headline: str, stage: str) -> dict:
    """Build a dropped_items-compatible row for a merged-away item.

    Populates ``source``/``source_url`` from the original item dict so the
    ingest pipeline lands them in ``dropped_items.source_name`` instead of
    NULL. Previously dedup merges were silent, which hid per-source
    attrition on audit (e.g. the 2026-04-15 UAE audit couldn't see which
    WAM/Presight items were collapsed into newsletter duplicates).
    """
    return {
        "headline": item.get("headline", ""),
        "source": item.get("source") or item.get("source_name"),
        "source_url": item.get("source_url"),
        "drop_reason": f"Dedup ({stage}): merged into '{kept_headline[:60]}'",
        "composite_score": None,
    }


def _fuzzy_dedup(items: list[dict]) -> tuple[list[dict], int, list[dict], list[dict]]:
    """Pairwise SequenceMatcher dedup. Threshold > 0.6 → merge.

    Returns ``(deduplicated_items, num_merged, merge_log, dropped_rows)``.
    ``dropped_rows`` are the items that were merged away (one per loser,
    not per cluster) so they can be surfaced in ``dropped_items``.
    """
    if not items:
        return [], 0, [], []

    normalized = [_normalize_headline(item.get("headline", "")) for item in items]
    distinctive = [_distinctive_tokens(item.get("headline", "")) for item in items]

    # Union-Find
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            # Require at least one shared distinctive (non-boilerplate) token
            # before running the expensive SequenceMatcher. Skipping zero-
            # overlap pairs is both a correctness fix (blocks template-only
            # false-positive merges) and a speedup.
            if not (distinctive[i] & distinctive[j]):
                continue
            sim = SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if sim > FUZZY_THRESHOLD:
                union(i, j)

    # Build groups
    groups: dict[int, list[dict]] = {}
    for i in range(len(items)):
        root = find(i)
        groups.setdefault(root, []).append(items[i])

    # Merge each group
    deduplicated = []
    merge_log = []
    dropped_rows: list[dict] = []
    total_merged = 0

    for group in groups.values():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            # Identify the "base" the same way _merge_group does (richest
            # item wins), so dropped_rows excludes only that one.
            sorted_group = sorted(group, key=_richness_score, reverse=True)
            base = sorted_group[0]
            merged = _merge_group(group)
            deduplicated.append(merged)
            total_merged += len(group) - 1
            kept_headline = merged.get("headline", "")
            for loser in sorted_group[1:]:
                dropped_rows.append(_dedup_drop_row(loser, kept_headline, "fuzzy"))
            merge_log.append({
                "kept_headline": kept_headline,
                "merged_count": len(group),
                "merged_headlines": [g.get("headline", "") for g in group],
            })
            logger.info(
                f"Dedup (fuzzy): merged {len(group)} items -> "
                f"'{merged.get('headline', '')[:60]}'"
            )

    return deduplicated, total_merged, merge_log, dropped_rows


# ── Stage 2: Semantic dedup via Haiku ─────────────────────────────────────────

_SEMANTIC_DEDUP_SYSTEM = """\
You are a deduplication engine for a daily news intelligence brief. Given a numbered list of news headlines, identify clusters where multiple headlines cover the same underlying STORY (not merely the same TOPIC).

<critical_rule>
BILATERAL ITEMS WITH DIFFERENT COUNTERPARTS ARE DIFFERENT EVENTS.

Diplomatic meetings name two parties: a principal and a counterpart. Deals name two parties: a buyer and a seller. If two headlines share an entity but name DIFFERENT counterparts (different countries, different organizations, different people), they are DIFFERENT events. Do NOT cluster them.
</critical_rule>

<examples>
<example label="DIFFERENT_COUNTERPARTS_KEEP_SEPARATE">
- "G42 signs $1B chip deal with NVIDIA"
- "G42 partners with Microsoft on UAE data centers"
DECISION: DIFFERENT events (NVIDIA != Microsoft). Do NOT cluster.
</example>

<example label="DIFFERENT_COUNTERPARTS_KEEP_SEPARATE">
- "Joint Statement following meeting between Abdullah bin Zayed, UK Foreign Secretary"
- "Abdullah bin Zayed, US Secretary of State discuss regional developments"
DECISION: DIFFERENT events (UK != US counterpart). Do NOT cluster.
</example>

<example label="DIFFERENT_COUNTERPARTS_KEEP_SEPARATE">
- "Tencent invests in DeepSeek AI"
- "Alibaba invests in DeepSeek AI"
DECISION: DIFFERENT events (Tencent != Alibaba). Do NOT cluster.
</example>

<example label="SAME_STORY_CLUSTER">
- "OpenAI releases GPT-5.5"
- "GPT-5.5 launched by OpenAI in Pro and Thinking modes"
DECISION: SAME event, paraphrased. Cluster with keep=more-informative-headline.
</example>
</examples>

OUTPUT FORMAT
Return ONLY a JSON array of clusters. Each cluster: {"keep": <index>, "drop": [<indices>]}. "keep" is the index with the most informative headline. Return [] if no duplicates found. Return valid JSON only, no markdown."""


async def _semantic_dedup(
    items: list[dict], client
) -> tuple[list[dict], int, list[dict], list[dict]]:
    """Send all headlines to Haiku, get back clusters to merge.

    Returns ``(deduplicated_items, num_merged, merge_log, dropped_rows)``.
    """
    if not items or client is None:
        return items, 0, [], []

    # Build numbered headline list
    lines = [f"{i}. {item.get('headline', '')}" for i, item in enumerate(items)]
    user_msg = "\n".join(lines)

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            system=_SEMANTIC_DEDUP_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        clusters = safe_parse_json(raw)
        if not isinstance(clusters, list):
            return items, 0, [], []
    except Exception as e:
        logger.warning(f"Semantic dedup Haiku call failed: {e}")
        return items, 0, [], []

    # Build set of indices to drop
    drop_indices: set[int] = set()
    merge_log = []
    dropped_rows: list[dict] = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        keep_idx = cluster.get("keep")
        drop_idxs = cluster.get("drop", [])
        if not isinstance(drop_idxs, list) or keep_idx is None:
            continue
        # Validate indices
        valid_drops = [d for d in drop_idxs if isinstance(d, int) and 0 <= d < len(items)]
        if not valid_drops or not (isinstance(keep_idx, int) and 0 <= keep_idx < len(items)):
            continue

        # Distinctive-token veto: reject losers that share fewer than
        # SEMANTIC_DEDUP_MIN_SHARED_TOKENS non-boilerplate headline tokens
        # with the keeper. Deterministic catch-net for Haiku false positives
        # like 'UAE President meets BlackRock' ↔ 'UAE and Kenyan Presidents
        # discuss cooperation under CEPA' (shared = {"uae"}, size 1).
        keep_tokens = _distinctive_tokens(items[keep_idx].get("headline", ""))
        filtered_drops = [
            d for d in valid_drops
            if len(keep_tokens & _distinctive_tokens(items[d].get("headline", "")))
               >= SEMANTIC_DEDUP_MIN_SHARED_TOKENS
        ]
        vetoed = [d for d in valid_drops if d not in filtered_drops]
        for v in vetoed:
            logger.info(
                "Dedup (semantic) VETO: '%s' ↔ '%s' — shared %d < %d distinctive tokens",
                items[keep_idx].get("headline", "")[:60],
                items[v].get("headline", "")[:60],
                len(keep_tokens & _distinctive_tokens(items[v].get("headline", ""))),
                SEMANTIC_DEDUP_MIN_SHARED_TOKENS,
            )
        valid_drops = filtered_drops
        if not valid_drops:
            continue

        # Override Haiku's keep choice: keep the item with most raw_content
        all_in_cluster = [keep_idx] + valid_drops
        best = max(all_in_cluster, key=lambda idx: _richness_score(items[idx]))
        to_drop = [idx for idx in all_in_cluster if idx != best]

        # Snapshot loser items BEFORE we replace items[best] with the merged
        # dict, so dropped_rows carries the original source/url of each loser.
        loser_originals = [dict(items[idx]) for idx in to_drop]

        drop_indices.update(to_drop)

        group = [items[idx] for idx in all_in_cluster]
        merged = _merge_group(group)
        # Replace the kept item with the merged version
        items[best] = merged

        kept_headline = merged.get("headline", "")
        for loser in loser_originals:
            dropped_rows.append(_dedup_drop_row(loser, kept_headline, "semantic"))

        merge_log.append({
            "kept_headline": kept_headline,
            "merged_count": len(all_in_cluster),
            "merged_headlines": [items[idx].get("headline", "") if idx not in drop_indices
                                 else group[all_in_cluster.index(idx)].get("headline", "")
                                 for idx in all_in_cluster],
        })
        logger.info(
            f"Dedup (semantic): merged {len(all_in_cluster)} items -> "
            f"'{merged.get('headline', '')[:60]}'"
        )

    deduplicated = [item for i, item in enumerate(items) if i not in drop_indices]
    return deduplicated, len(drop_indices), merge_log, dropped_rows


# ── Stage 2-tuple: Mechanical event-tuple comparison (Phase 3) ────────────────


# Minimum action-token overlap for a tuple match. Two items with the same
# event_type, primary_actor, and counterpart but disjoint action verbs
# (e.g. "Tencent invests" vs "Tencent licenses") are NOT the same event.
# Threshold of 1 is generous — any single shared lemma counts. Tightening
# to 2 would over-veto on legitimate paraphrases that share only one
# action token (e.g. "releases" vs "launches" share neither token).
_TUPLE_MATCH_MIN_ACTION_OVERLAP = 1


def _normalize_actor(value):
    """Lowercase + strip a free-text actor/counterpart for comparison.

    Returns "" for None / empty so two items with both fields null
    compare equal (single-actor events without a counterpart match each
    other on that field rather than being forced apart).
    """
    if not value:
        return ""
    return str(value).strip().lower()


def _action_tokens(action: str) -> set[str]:
    """Tokenize an action verb phrase for overlap comparison.

    Reuses `_distinctive_tokens` so the lemma stripping (boilerplate +
    < 3 chars) matches the rest of the dedup pipeline. "cancels trip"
    and "cancel meetings" both produce tokens including "cancel" forms,
    catching paraphrases with a single shared content lemma.
    """
    if not action:
        return set()
    return {
        tok for tok in _normalize_headline(action).split()
        if len(tok) >= 3 and tok not in _BOILERPLATE_TOKENS
    }


def _tuple_match(a: Optional[dict], b: Optional[dict]) -> tuple[bool, str]:
    """Mechanical same-event decision based on event tuples.

    Same event requires ALL of:
      - event_type matches
      - primary_actor matches (case-insensitive, stripped) — null counts as
        equal to null so single-actor events (product releases, internal
        decisions) can still merge with their paraphrases.
      - counterpart matches (or both null)
      - action lemma overlap >= `_TUPLE_MATCH_MIN_ACTION_OVERLAP`

    Returns ``(is_same_event, reason)``. The reason is a short string
    suitable for telemetry / audit, e.g. "counterpart differs:
    'UK Foreign Secretary' vs 'US Secretary of State'".

    Defensive: if either tuple is None / empty, returns (False, ...).
    Callers should fall back to the legacy LLM-judged path when tuples
    are unavailable rather than treating "missing tuple" as match.
    """
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False, "tuple unavailable"
    if not a or not b:
        return False, "tuple empty"

    a_type = a.get("event_type") or ""
    b_type = b.get("event_type") or ""
    if a_type != b_type:
        return False, f"event_type differs: {a_type!r} vs {b_type!r}"

    a_actor = _normalize_actor(a.get("primary_actor"))
    b_actor = _normalize_actor(b.get("primary_actor"))
    if a_actor != b_actor:
        return False, (
            f"primary_actor differs: "
            f"{a.get('primary_actor')!r} vs {b.get('primary_actor')!r}"
        )

    a_cp = _normalize_actor(a.get("counterpart"))
    b_cp = _normalize_actor(b.get("counterpart"))
    if a_cp != b_cp:
        return False, (
            f"counterpart differs: "
            f"{a.get('counterpart')!r} vs {b.get('counterpart')!r}"
        )

    a_act = _action_tokens(a.get("action") or "")
    b_act = _action_tokens(b.get("action") or "")
    overlap = a_act & b_act
    if len(overlap) < _TUPLE_MATCH_MIN_ACTION_OVERLAP:
        # No content-bearing shared lemma. Same actor + counterpart but
        # different actions = different events (Tencent invests vs
        # Tencent licenses).
        return False, (
            f"no action overlap: {sorted(a_act)} vs {sorted(b_act)}"
        )

    return True, (
        f"matched on event_type+actor+counterpart+action overlap={sorted(overlap)}"
    )


def _all_items_have_tuples(items: list[dict]) -> bool:
    """True iff every item has a non-empty `_event_tuple` dict.

    Used to decide whether the tuple-aware dedup path is safe to take.
    Phase 2 extraction fails open, so partial coverage is possible —
    fall back to the LLM-judged path in that case rather than treating
    "missing tuple" items as not-merge-eligible (which would silently
    leak duplicates downstream).
    """
    return all(
        isinstance(item.get("_event_tuple"), dict)
        and bool(item["_event_tuple"])
        for item in items
    )


def _tuple_dedup(items: list[dict]) -> tuple[list[dict], int, list[dict], list[dict]]:
    """Cluster items by mechanical tuple comparison. No LLM call.

    Pairwise: any two items with `_tuple_match` -> True go into the same
    cluster. Each cluster's richest item (by `_richness_score`) becomes
    the merge winner; the rest become drops.

    Returns the same shape as `_semantic_dedup`:
    ``(deduplicated, num_merged, merge_log, dropped_rows)``.

    Design note: O(n^2) pairwise check is fine at our volumes (~150-300
    items post-fuzzy). An indexed approach via primary_actor would
    speed this up if needed, but the constant factor is small (no
    network calls, no Haiku) so the wall-clock cost is negligible.
    """
    if len(items) < 2:
        return list(items), 0, [], []

    # Union-find over indices. parent[i] = root of i's cluster.
    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Pairwise tuple match. Symmetric, transitive via union-find.
    for i in range(len(items)):
        a_tup = items[i].get("_event_tuple")
        if not isinstance(a_tup, dict) or not a_tup:
            continue
        for j in range(i + 1, len(items)):
            b_tup = items[j].get("_event_tuple")
            if not isinstance(b_tup, dict) or not b_tup:
                continue
            same, _ = _tuple_match(a_tup, b_tup)
            if same:
                union(i, j)

    # Group items by cluster root.
    clusters: dict[int, list[int]] = {}
    for i in range(len(items)):
        clusters.setdefault(find(i), []).append(i)

    drop_indices: set[int] = set()
    merge_log: list[dict] = []
    dropped_rows: list[dict] = []

    for root, idxs in clusters.items():
        if len(idxs) < 2:
            continue
        # Pick the richest as merge winner.
        best = max(idxs, key=lambda k: _richness_score(items[k]))
        to_drop = [idx for idx in idxs if idx != best]
        loser_originals = [dict(items[idx]) for idx in to_drop]
        drop_indices.update(to_drop)

        group = [items[idx] for idx in idxs]
        merged = _merge_group(group)
        items[best] = merged

        kept_headline = merged.get("headline", "")
        for loser in loser_originals:
            dropped_rows.append(_dedup_drop_row(loser, kept_headline, "tuple"))

        merge_log.append({
            "kept_headline": kept_headline,
            "merged_count": len(idxs),
            "merged_headlines": [g.get("headline", "") for g in group],
        })
        logger.info(
            "Dedup (tuple): merged %d items -> '%s'",
            len(idxs), kept_headline[:60],
        )

    deduplicated = [item for i, item in enumerate(items) if i not in drop_indices]
    return deduplicated, len(drop_indices), merge_log, dropped_rows


# ── Public API ────────────────────────────────────────────────────────────────


async def deduplicate_items(
    items: list[dict],
    client=None,
) -> tuple[list[dict], int, list[dict], list[dict]]:
    """Three-stage dedup pipeline:

      0. URL — exact source_url match (always runs).
      1. Fuzzy — `SequenceMatcher` headline near-duplicates (always runs).
      2a. Tuple — Phase 3 mechanical event-tuple comparison. Used when
          all surviving items carry `_event_tuple` (the normal Phase 2+
          flow). NO LLM call — purely pairwise field equality.
      2b. Semantic — legacy Haiku-judged path. Falls back here when
          tuples are unavailable (extraction failure, resume from a
          pre-Phase-2 artifact, or `client` is None).

    Args:
        items: List of ScoutItem-like dicts with at least 'headline' and
            'raw_content'. Items SHOULD have `_event_tuple` from the
            Phase 2 extraction stage; missing tuples route to Stage 2b.
        client: anthropic.AsyncAnthropic instance. Required for Stage 2b
            fallback; Stage 2a (tuple) doesn't use it.

    Returns:
        ``(deduplicated_items, total_num_merged, merge_log, dropped_rows)``.
    """
    if not items:
        return [], 0, [], []

    # Stage 0: URL — same source_url is unambiguously the same article.
    items, n0, log0, drops0 = _url_dedup(items)
    logger.info(f"Stage 0 (url): {n0} items merged, {len(items)} remain")

    # Stage 1: Fuzzy
    items, n1, log1, drops1 = _fuzzy_dedup(items)
    logger.info(f"Stage 1 (fuzzy): {n1} items merged, {len(items)} remain")

    # Stage 2: tuple-aware (Phase 3) when tuples are available, fall
    # back to the legacy Haiku-judged path otherwise.
    if _all_items_have_tuples(items):
        items, n2, log2, drops2 = _tuple_dedup(items)
        logger.info(
            f"Stage 2 (tuple): {n2} items merged, {len(items)} remain"
        )
    else:
        items, n2, log2, drops2 = await _semantic_dedup(items, client)
        logger.info(
            f"Stage 2 (semantic): {n2} items merged, {len(items)} remain "
            f"(fallback — tuples unavailable)"
        )

    return (
        items,
        n0 + n1 + n2,
        log0 + log1 + log2,
        drops0 + drops1 + drops2,
    )
