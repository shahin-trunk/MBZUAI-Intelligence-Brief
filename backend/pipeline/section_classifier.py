"""Section classifier — Haiku agent that assigns each news item to a
canonical brief section.

Two entry points:

- `classify_sections` — post-Ghostwriter classifier that reads
  `headline + key_bullets` from authored cards and writes `section`.
  Used by `card_batch.py` as the final quality gate. Phase 2: becomes
  a no-op when items already carry a canonical section from the
  pre-Gatekeeper classifier.

- `classify_candidate_sections` — pre-Gatekeeper classifier (Phase 2)
  that runs on all content-filter-approved candidates (~150 items/day),
  reads `headline + summary/raw_content`, writes both `brief_section`
  (Gatekeeper schema) and `section` (downstream schema) so the
  assignment carries through every subsequent stage unchanged.

Replaces two unreliable upstream mechanisms:
1. The Ghostwriter's own section field (the shorter prompt doesn't
   preserve sections reliably — ~20% misplacement rate observed
   2026-04-16).
2. The source_scout → SCOUT_TO_SECTION lookup (based on newsletter
   sender, not content — dumps everything into the sender's primary
   section regardless of actual topic).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

import anthropic

logger = logging.getLogger(__name__)

CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
CLASSIFIER_MAX_TOKENS = 2000
CLASSIFIER_TIMEOUT = 60

# Phase 2: pre-Gatekeeper batching. 30 items per Haiku call keeps the
# prompt well under context limits; concurrency 5 fans out across
# ~150 candidates in ~1 round-trip.
CANDIDATE_BATCH_SIZE = 30
CANDIDATE_CONCURRENCY = 5
# Default section for items the classifier couldn't place (bad output,
# empty headline, etc.). Matches the plan: no 6th "Other" bucket.
DEFAULT_SECTION = "International Business & Technology"

SECTIONS = [
    "UAE",
    "Regional Research & Academic Events",
    "International Politics & Policy",
    "International Business & Technology",
    "Model Releases & Technical Developments",
]

CLASSIFIER_PROMPT = """Classify each news item into exactly one section.

Sections:
- UAE: news primarily about the UAE, its government, institutions, companies headquartered there (G42, ADNOC, Mubadala, MBZUAI, Presight, Khazna), or events directly impacting UAE interests.
- Regional Research & Academic Events: university research outputs, academic conferences, education partnerships in the Middle East / Gulf region. NOT company product launches.
- International Politics & Policy: geopolitics, government policy, regulation, sanctions, diplomacy, elections, military/defense — outside the UAE.
- International Business & Technology: company deals, funding rounds, earnings, market moves, enterprise tech adoption — outside the UAE.
- Model Releases & Technical Developments: AI model launches, benchmark results, new frameworks/tools/SDKs, technical research breakthroughs from labs.

Rules:
- If an item could fit multiple sections, choose the PRIMARY angle. A model release with policy implications is still "Model Releases." A UAE company's international deal is still "UAE."
- AI infrastructure deals (GPU leases, data center builds) go to "International Business & Technology" unless they are UAE-based.
- Items about Khalifa University, KAUST, or other Gulf academic institutions go to "Regional Research & Academic Events."

For each item, return its id and section. Return ONLY a JSON array:
[{"id": "item-id", "section": "Section Name"}, ...]

Items to classify:
"""


async def classify_sections(
    client: anthropic.AsyncAnthropic,
    items: list[dict],
) -> list[dict]:
    """Classify items into sections via a single batched Haiku call.

    Reads headline + key_bullets from each item, sends to Haiku,
    parses the response, and overrides each item's ``section`` field.
    Falls back to the original section on any error.

    Modifies items in place and returns the same list.

    Phase 2 (curation rewrite) — short-circuit when every item already
    carries a canonical section (set by the pre-Gatekeeper classifier).
    The Haiku call is redundant in that case and just adds cost.
    """
    if not items:
        return items

    if all(item.get("section") in SECTIONS for item in items):
        logger.info(
            "section_classifier: all %d items already in canonical sections; "
            "skipping Haiku re-classification",
            len(items),
        )
        return items

    # Build the classification input. Ghostwritten cards carry key_bullets;
    # pre-Ghostwriter items (e.g. drop candidates, used when the classifier
    # runs before the per-section cap) only have the collection-stage
    # ``summary`` string. Prefer bullets when present, else fall back.
    lines = []
    for item in items:
        item_id = item.get("id") or ""
        headline = item.get("headline") or ""
        bullets = item.get("key_bullets") or []
        summary = " ".join(b for b in bullets if isinstance(b, str))[:200]
        if not summary:
            raw_summary = item.get("summary")
            if isinstance(raw_summary, str):
                summary = raw_summary[:200]
        lines.append(f'- id: "{item_id}" | headline: "{headline}" | summary: "{summary}"')

    user_message = CLASSIFIER_PROMPT + "\n".join(lines)

    try:
        response = await client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=CLASSIFIER_MAX_TOKENS,
            messages=[{"role": "user", "content": user_message}],
            timeout=CLASSIFIER_TIMEOUT,
        )
    except Exception as e:
        logger.warning("section_classifier: Haiku call failed (%s); keeping original sections", e)
        return items

    text = "\n".join(b.text for b in response.content if b.type == "text").strip()

    # Parse JSON array from response — Haiku sometimes returns multiple
    # JSON objects on separate lines or wraps in markdown fences.
    # Extract the first valid JSON array.
    try:
        cleaned = re.sub(r"^```(?:json)?\s*", "", text)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        # Try direct parse first
        try:
            classifications = json.loads(cleaned)
        except json.JSONDecodeError:
            # Find the first [...] in the response
            arr_match = re.search(r"\[.*?\]", cleaned, re.DOTALL)
            if arr_match:
                classifications = json.loads(arr_match.group(0))
            else:
                raise ValueError("No JSON array found in response")
        if not isinstance(classifications, list):
            raise ValueError("Expected JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("section_classifier: failed to parse response (%s); keeping originals", e)
        return items

    # Build lookup
    section_by_id = {}
    for entry in classifications:
        if isinstance(entry, dict) and entry.get("id") and entry.get("section"):
            section = entry["section"]
            if section in SECTIONS:
                section_by_id[str(entry["id"])] = section

    # Apply classifications
    applied = 0
    for item in items:
        item_id = str(item.get("id") or "")
        new_section = section_by_id.get(item_id)
        if new_section and new_section != item.get("section"):
            old = item.get("section", "?")
            item["section"] = new_section
            applied += 1
            logger.info("section_classifier: %s → %s (was %s)", item_id, new_section, old)

    logger.info(
        "section_classifier: classified %d items, reassigned %d",
        len(items), applied,
    )
    if applied:
        print(f"  📂 Section classifier: reassigned {applied}/{len(items)} items")

    return items


# ---------------------------------------------------------------------------
# Phase 2 — pre-Gatekeeper candidate section classifier
# ---------------------------------------------------------------------------


def _candidate_signal(item: dict) -> str:
    """Best-available text to classify a pre-Gatekeeper candidate.

    Candidates don't have Ghostwriter prose yet; prefer the collector's
    `summary`, fall back to a truncated `raw_content` (stripped of
    nested JSON), last-resort the headline alone.
    """
    headline = (item.get("headline") or "").strip()
    raw = item.get("summary") or item.get("raw_content") or ""
    if isinstance(raw, (dict, list)):
        raw = json.dumps(raw, ensure_ascii=False)
    raw = str(raw).strip()
    if len(raw) > 400:
        raw = raw[:400]
    return f'{headline} | {raw}' if raw else headline


async def _classify_one_batch(
    client: anthropic.AsyncAnthropic,
    batch: list[dict],
) -> dict[str, str]:
    """Classify one batch of pre-Gatekeeper items. Returns {id: section}."""
    lines = []
    for item in batch:
        item_id = str(item.get("_idx", item.get("id", ""))) or ""
        signal = _candidate_signal(item)
        lines.append(f'- id: "{item_id}" | {signal[:500]}')
    user_message = CLASSIFIER_PROMPT + "\n".join(lines)

    try:
        response = await client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=CLASSIFIER_MAX_TOKENS,
            messages=[{"role": "user", "content": user_message}],
            timeout=CLASSIFIER_TIMEOUT,
        )
    except Exception as e:
        logger.warning(
            "candidate_section_classifier: Haiku call failed (%s); defaulting batch", e
        )
        return {}

    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", text)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        classifications = json.loads(cleaned)
    except json.JSONDecodeError:
        arr_match = re.search(r"\[.*?\]", cleaned, re.DOTALL)
        if not arr_match:
            logger.warning(
                "candidate_section_classifier: no JSON array in response; "
                "defaulting batch"
            )
            return {}
        try:
            classifications = json.loads(arr_match.group(0))
        except json.JSONDecodeError as e:
            logger.warning("candidate_section_classifier: JSON parse failed (%s)", e)
            return {}

    if not isinstance(classifications, list):
        return {}

    result: dict[str, str] = {}
    for entry in classifications:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        section = entry.get("section")
        if item_id and section in SECTIONS:
            result[str(item_id)] = section
    return result


async def classify_candidate_sections(
    client: anthropic.AsyncAnthropic,
    items: list[dict],
) -> None:
    """Assign a canonical section to every pre-Gatekeeper candidate.

    Writes BOTH `brief_section` (Gatekeeper schema) and `section`
    (downstream schema) on each item, so the assignment carries
    through Gatekeeper → Enricher → Ghostwriter → ingest without
    re-classification.

    Modifies items in place. Items the classifier couldn't place are
    defaulted to `DEFAULT_SECTION` ("International Business & Technology")
    — the broadest category, and the plan explicitly opts out of a
    6th "Other" bucket.

    Batched at `CANDIDATE_BATCH_SIZE` (30) items per Haiku call, with
    `CANDIDATE_CONCURRENCY` (5) concurrent calls via `asyncio.gather`.

    Idempotent: if every item already has a canonical `brief_section`,
    this is a no-op — safe to call on `--from-stage=gatekeeper` resume
    paths without double-billing.
    """
    if not items:
        return

    if all(item.get("brief_section") in SECTIONS for item in items):
        logger.info(
            "candidate_section_classifier: all %d items already classified; "
            "skipping",
            len(items),
        )
        return

    # Ensure every item carries a stable _idx. The orchestrator assigns it
    # on the normal daily path (orchestrator.py:2627-2628) but NOT on the
    # --from-stage=gatekeeper resume path. Without it, the key fallback
    # here (`str(i)`) diverges from _classify_one_batch's fallback
    # (`item.get("id", "")`), so Haiku-classified results never match on
    # lookup and every item silently defaults. Defensive assignment here
    # keeps the two code paths in sync regardless of caller.
    for i, item in enumerate(items):
        if "_idx" not in item:
            item["_idx"] = i

    # Key by _idx — matches the fallback used inside _classify_one_batch.
    keyed_items: list[tuple[str, dict]] = []
    for i, item in enumerate(items):
        key = str(item.get("_idx", i))
        keyed_items.append((key, item))

    batches = [
        [item for _, item in keyed_items[i : i + CANDIDATE_BATCH_SIZE]]
        for i in range(0, len(keyed_items), CANDIDATE_BATCH_SIZE)
    ]

    sem = asyncio.Semaphore(CANDIDATE_CONCURRENCY)

    async def _run_one(batch: list[dict]) -> dict[str, str]:
        async with sem:
            return await _classify_one_batch(client, batch)

    batch_results = await asyncio.gather(*[_run_one(b) for b in batches])

    section_by_key: dict[str, str] = {}
    for r in batch_results:
        section_by_key.update(r)

    classified = 0
    defaulted = 0
    for key, item in keyed_items:
        section = section_by_key.get(key)
        if section:
            classified += 1
        else:
            section = DEFAULT_SECTION
            defaulted += 1
        item["brief_section"] = section
        item["section"] = section

    logger.info(
        "candidate_section_classifier: %d classified, %d defaulted "
        "(to %r)",
        classified, defaulted, DEFAULT_SECTION,
    )
    print(
        f"  📂 Pre-Gatekeeper sections: {classified} classified, "
        f"{defaulted} defaulted"
    )
