"""Gatekeeper output re-keyer — specialist Haiku agent that attaches the
correct `_idx` to every Gatekeeper-output item via semantic matching against
the input pool.

Background: the Gatekeeper (Sonnet 4.6) is instructed to echo `_idx` on its
output, but in practice does so variably — 100% of dropped items in
controlled tests at 30-136 item scale, 0% on both selected and dropped in
production runs of 180+ items. Asking the same model to bookkeep index
values while making editorial judgments fights its attention.

This module mirrors the existing specialist-Haiku pattern used by the
pre-Gatekeeper section classifier (`pipeline/section_classifier.py`) and the
entity classifier. Haiku reads the (tagged) Gatekeeper output plus the
original input pool and returns a mapping from tagged output IDs
(`SEL_0`/`DROP_0`) to input `_idx`. The result is attached in-place to both
`selected` and `dropped` lists.

Failure modes:
- Haiku call errors → fail open (log, return no mapping for that batch).
  The orchestrator's fuzzy fallback still runs, so worst case we're no worse
  than the pre-re-keyer state.
- Haiku returns `null` for an output item → the item is left without `_idx`.
  The downstream fuzzy fallback attempts to assign one; if it also fails the
  item is flagged as a genuine silent drop (likely model hallucination).
- Haiku returns an `_idx` not present in input → ignored.
- Two output items claim the same input `_idx` → 1:1 greedy pairing keeps
  the first match, leaves the second unmatched (logged at WARNING).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

REKEYER_MODEL = "claude-haiku-4-5-20251001"
REKEYER_MAX_TOKENS = 4000
REKEYER_TIMEOUT = 60

# Batching: Gatekeeper can emit up to ~250 items in selected+dropped at
# production scale. 50 output items per call keeps the response small; the
# reference pool (~250 items) is re-sent on each call. At 5-way concurrency
# this is ~5 Haiku calls at ~32k input tokens each = ~160k input tokens/day
# at ~$0.13 — same order as the pre-Gatekeeper section classifier.
OUTPUT_BATCH_SIZE = 50
OUTPUT_CONCURRENCY = 5

# Keep reference summaries short so the prompt doesn't balloon. Headline is
# the primary signal; summary only disambiguates near-duplicates.
REF_SUMMARY_MAX = 220


REKEYER_PROMPT = """Your task is to match each Gatekeeper output item back to its source in the reference pool.

The Gatekeeper is an editorial agent that reads a pool of candidate news items and returns `selected` and `dropped` arrays. Each output item corresponds to ONE item in the pool, but the Gatekeeper may have lightly refined the headline (word tweaks, punctuation, occasionally heavier paraphrase, sometimes an appended cluster-facet tag like "[market_reaction facet]"). Your job is to match each output item back to its source by semantic similarity.

REFERENCE POOL (original input candidates — each has a stable `idx`):
{reference_pool}

OUTPUT ITEMS TO MATCH (headlines may be lightly rewritten):
{output_items}

Guidance:
- Prefer strong semantic overlap over literal string similarity. "Stellantis, Microsoft sign partnership" and "Stellantis and Microsoft sign five-year partnership for AI push" are the same event.
- When two reference items are plausible, pick the one whose summary most strongly supports the output headline.
- Do not assign the same reference `idx` to two different output items. If forced to, pick the better match and set the loser's `idx=null`.
- If no reference item plausibly corresponds to an output (e.g. the Gatekeeper merged two items, or hallucinated), return `idx=null` for that output.

Return ONLY a JSON array, one entry per output item:
[{{"out_id": "SEL_0", "idx": 5}}, {{"out_id": "DROP_0", "idx": null}}, ...]
"""


def _ref_line(item: dict) -> str:
    """Build one line for the reference pool section of the prompt."""
    idx = item.get("_idx")
    headline = (item.get("headline") or "").strip().replace("\n", " ")[:200]
    summary = (item.get("summary") or "").strip().replace("\n", " ")
    if len(summary) > REF_SUMMARY_MAX:
        summary = summary[:REF_SUMMARY_MAX] + "…"
    if summary:
        return f'- idx={idx} | "{headline}" | {summary}'
    return f'- idx={idx} | "{headline}"'


def _out_line(out_id: str, item: dict) -> str:
    """Build one line for the output items section of the prompt."""
    headline = (item.get("headline") or "").strip().replace("\n", " ")[:220]
    return f'- out_id={out_id} | "{headline}"'


async def _rekey_one_batch(
    client: anthropic.AsyncAnthropic,
    reference_pool: list[dict],
    batch: list[tuple[str, dict]],
) -> dict[str, Optional[int]]:
    """Run one Haiku call; returns `{out_id: idx_or_None}`.

    On any parse/API failure, returns `{}` (fail open — orchestrator's fuzzy
    fallback will attempt to recover these items).
    """
    ref_lines = "\n".join(_ref_line(it) for it in reference_pool)
    out_lines = "\n".join(_out_line(oid, it) for oid, it in batch)
    prompt = REKEYER_PROMPT.format(
        reference_pool=ref_lines,
        output_items=out_lines,
    )

    try:
        response = await client.messages.create(
            model=REKEYER_MODEL,
            max_tokens=REKEYER_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            timeout=REKEYER_TIMEOUT,
        )
    except Exception as e:
        logger.warning("gk_rekeyer: Haiku call failed (%s); batch fails open", e)
        return {}

    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", text)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        matches = json.loads(cleaned)
    except json.JSONDecodeError:
        arr_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not arr_match:
            logger.warning(
                "gk_rekeyer: no JSON array in response; batch fails open"
            )
            return {}
        try:
            matches = json.loads(arr_match.group(0))
        except json.JSONDecodeError as e:
            logger.warning("gk_rekeyer: JSON parse failed (%s)", e)
            return {}

    if not isinstance(matches, list):
        return {}

    result: dict[str, Optional[int]] = {}
    for entry in matches:
        if not isinstance(entry, dict):
            continue
        out_id = entry.get("out_id")
        if not out_id:
            continue
        idx = entry.get("idx")
        if idx is None:
            result[str(out_id)] = None
            continue
        try:
            result[str(out_id)] = int(idx)
        except (TypeError, ValueError):
            result[str(out_id)] = None
    return result


async def rekey_gatekeeper_output(
    client: anthropic.AsyncAnthropic,
    input_pool: list[dict],
    selected: list[dict],
    dropped: list[dict],
) -> dict:
    """Attach `_idx` to every Gatekeeper output item via Haiku similarity matching.

    Args:
        client: Async Anthropic client.
        input_pool: pre-Gatekeeper lightweight_items list. Each entry MUST
            already carry `_idx` (the orchestrator assigns these before
            calling the Gatekeeper).
        selected: Gatekeeper's `selected` array. Mutated in place: each item
            gains (or retains) an `_idx` field.
        dropped: Gatekeeper's model-drops array. Mutated in place.

    Behavior:
        - Items where the Gatekeeper already echoed a valid `_idx` are trusted
          and skipped (saves Haiku tokens and respects model compliance when
          present).
        - Remaining items are tagged `SEL_n` / `DROP_n` and fanned out to
          Haiku in batches.
        - 1:1 greedy pairing: once an input `_idx` has been claimed by an
          output item, subsequent claims on the same `_idx` are rejected
          (logged at WARNING). Losers stay unmatched — orchestrator's fuzzy
          fallback gets another try.

    Returns a report dict for pipeline stats. Keys:
        total, matched, unmatched, trusted_existing, matched_by_haiku,
        match_rate, duplicate_claim_count.
    """
    all_out: list[tuple[str, dict]] = []
    for i, item in enumerate(selected):
        all_out.append((f"SEL_{i}", item))
    for i, item in enumerate(dropped):
        all_out.append((f"DROP_{i}", item))

    total = len(all_out)
    if total == 0:
        return {
            "total": 0, "matched": 0, "unmatched": 0,
            "trusted_existing": 0, "matched_by_haiku": 0,
            "duplicate_claim_count": 0, "match_rate": 1.0,
        }

    valid_input_idx = {
        int(i["_idx"]) for i in input_pool if i.get("_idx") is not None
    }
    used_idx: set[int] = set()  # tracks 1:1 pairing across trusted + Haiku

    # Trust existing `_idx` echoes first. Respect the model's compliance
    # when it happens — and lock those idx values out of later Haiku claims.
    needs_rekey: list[tuple[str, dict]] = []
    trusted = 0
    for out_id, item in all_out:
        echoed = item.get("_idx")
        echoed_int: Optional[int] = None
        if echoed is not None:
            try:
                echoed_int = int(echoed)
            except (TypeError, ValueError):
                echoed_int = None
        if (
            echoed_int is not None
            and echoed_int in valid_input_idx
            and echoed_int not in used_idx
        ):
            item["_idx"] = echoed_int
            used_idx.add(echoed_int)
            trusted += 1
        else:
            # Drop any stale/invalid _idx so downstream treats the item as
            # needing re-keying rather than silently trusting a bad value.
            if "_idx" in item and echoed_int not in valid_input_idx:
                item.pop("_idx", None)
            needs_rekey.append((out_id, item))

    # Fan out Haiku calls.
    batches = [
        needs_rekey[i : i + OUTPUT_BATCH_SIZE]
        for i in range(0, len(needs_rekey), OUTPUT_BATCH_SIZE)
    ]
    sem = asyncio.Semaphore(OUTPUT_CONCURRENCY)

    async def _run(batch: list[tuple[str, dict]]) -> dict[str, Optional[int]]:
        async with sem:
            return await _rekey_one_batch(client, input_pool, batch)

    batch_results = (
        await asyncio.gather(*[_run(b) for b in batches]) if batches else []
    )

    mapping: dict[str, Optional[int]] = {}
    for r in batch_results:
        mapping.update(r)

    # Apply matches + greedy 1:1 dedup. Iterate out_ids deterministically.
    by_out_id = {oid: item for oid, item in needs_rekey}
    matched_by_haiku = 0
    duplicate_claims = 0

    for out_id in sorted(by_out_id):
        item = by_out_id[out_id]
        idx = mapping.get(out_id)
        if idx is None or idx not in valid_input_idx:
            continue
        if idx in used_idx:
            duplicate_claims += 1
            logger.warning(
                "gk_rekeyer: idx=%d already claimed; leaving %s unmatched",
                idx, out_id,
            )
            continue
        item["_idx"] = idx
        used_idx.add(idx)
        matched_by_haiku += 1

    matched = trusted + matched_by_haiku
    unmatched = total - matched

    report = {
        "total": total,
        "matched": matched,
        "unmatched": unmatched,
        "trusted_existing": trusted,
        "matched_by_haiku": matched_by_haiku,
        "duplicate_claim_count": duplicate_claims,
        "match_rate": matched / total if total else 1.0,
    }
    logger.info(
        "gk_rekeyer: %d/%d matched (%.1f%%) — trusted=%d, haiku=%d, "
        "unmatched=%d, duplicate_claims=%d",
        matched, total, 100 * report["match_rate"],
        trusted, matched_by_haiku, unmatched, duplicate_claims,
    )
    return report
