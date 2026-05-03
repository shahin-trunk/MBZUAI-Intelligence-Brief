import asyncio
import json
import logging
import random
import re
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import anthropic
import httpx
from pydantic import ValidationError

from config import MODEL, STAGE_TIMEOUTS
from models.schemas import GatekeeperOutput
from pipeline.json_utils import safe_parse_json
from pipeline.section_classifier import SECTIONS as CANONICAL_SECTIONS
from prompts.loader import load_prompt

logger = logging.getLogger(__name__)

# 2026-04-20: bumped from 32000 after a busy-news-day run hit max_tokens
# at 32K, truncating mid-`dropped` and losing the trailing `brief_summary`
# field. 48K gives ~50% headroom over that day's output and stays well
# inside Sonnet 4.6's 64K output ceiling.
GATEKEEPER_MAX_TOKENS = 48000

# Retry budget for missing-_idx items inside a single chunk. Mirrors
# `card_batch.MAX_GHOSTWRITER_MISSING_ID_RETRIES`.
MAX_GATEKEEPER_MISSING_IDX_RETRIES = 2

# Below this total input size, skip section chunking and run a single
# Gatekeeper call. Preserves single-call behavior for low-volume days
# (e.g. 2026-04-12 had 53 post-content-filter items total — well below
# typical per-section budgets so chunking adds overhead with no benefit).
SINGLE_CALL_THRESHOLD = 60

# Sentinel section bucket for items missing or carrying a non-canonical
# `brief_section` value. Items still get scored — they just go through
# their own chunk.
UNSECTIONED_BUCKET = "?"

_GST = ZoneInfo("Asia/Dubai")


def _timestamp() -> str:
    return datetime.now(_GST).strftime("%H:%M:%S")


def _build_retry_correction(stage: str, error: Exception) -> str:
    """Compact retry note appended to the prompt on a failed attempt.

    Duplicated from `pipeline.orchestrator.build_retry_correction` to avoid
    a circular import (orchestrator imports from this module). Same pattern
    as `card_batch._build_retry_correction`. If the orchestrator copy
    changes, update this too.
    """
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


def _validate_with_pydantic(model_cls, payload: dict) -> dict:
    """Validate payload with Pydantic across v1/v2.

    by_alias=True on dump preserves JSON keys that can't be Python
    identifiers — notably "_idx" on Gatekeeper items, aliased to `idx`
    internally so the orchestrator's drop-rejoin fast path still works.
    """
    if hasattr(model_cls, "model_validate"):
        model = model_cls.model_validate(payload)
        return model.model_dump(by_alias=True)
    model = model_cls.parse_obj(payload)
    return model.dict(by_alias=True)


def extract_json_object(text: str) -> dict:
    """Extract a JSON object from text that may be wrapped in markdown fences."""
    # Try code fences first
    fence_match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
    if fence_match:
        return safe_parse_json(fence_match.group(1))

    # Try raw JSON object
    obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if obj_match:
        return safe_parse_json(obj_match.group(1))

    raise ValueError("No JSON object found in response text")


async def run_gatekeeper(
    client: anthropic.AsyncAnthropic,
    prompt_text: str,
) -> tuple:
    """Run the Gatekeeper agent.

    Args:
        client: Async Anthropic client.
        prompt_text: Fully templated Gatekeeper prompt with scout output injected.

    Returns:
        Tuple of (result dict, usage dict).
    """
    response = await client.messages.create(
        model=MODEL,
        max_tokens=GATEKEEPER_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=STAGE_TIMEOUTS["gatekeeper"],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    logger.info(f"Gatekeeper: stop_reason={response.stop_reason}, "
                f"tokens_in={usage['input_tokens']}, tokens_out={usage['output_tokens']}")

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ValueError("Gatekeeper: No text blocks in response")

    full_text = "\n".join(text_blocks)

    try:
        result = extract_json_object(full_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Gatekeeper: Failed to parse JSON. Preview: {full_text[:500]}"
        ) from e

    # Defensive reconstruction: brief_summary is the last field the model
    # writes, so it's the first casualty when output hits max_tokens. If
    # the rest of the JSON parsed (we have selected + dropped), synthesize
    # brief_summary from what we have rather than hard-failing validation.
    # Orchestrator recomputes most of these values post-hoc anyway.
    if "brief_summary" not in result and isinstance(result, dict):
        selected = result.get("selected") or []
        dropped = result.get("dropped") or []
        section_distribution: dict[str, int] = {}
        for item in selected:
            if not isinstance(item, dict):
                continue
            section = item.get("brief_section") or item.get("section") or "Unknown"
            section_distribution[section] = section_distribution.get(section, 0) + 1
        result["brief_summary"] = {
            "total_input_items": len(selected) + len(dropped),
            "after_deduplication": 0,
            "selected": len(selected),
            "dropped": len(dropped),
            "section_distribution": section_distribution,
            "notable_decisions": (
                f"Reconstructed after model output hit max_tokens "
                f"(stop_reason={response.stop_reason})."
            ),
        }
        logger.warning(
            "Gatekeeper: brief_summary missing from model output; "
            "reconstructed from selected/dropped (stop_reason=%s, tokens_out=%d)",
            response.stop_reason,
            usage["output_tokens"],
        )

    try:
        result = _validate_with_pydantic(GatekeeperOutput, result)
    except ValidationError as e:
        raise ValueError(f"Gatekeeper: Output schema validation failed: {e}") from e

    return result, usage


# ---------------------------------------------------------------------------
# Chunked + missing-_idx-retry wrappers
# ---------------------------------------------------------------------------
#
# Background: the single-shot Gatekeeper call silently omitted ~38 items/day
# in production (recorded as `gatekeeper_implicit` in `dropped_items`). The
# fix is structurally identical to the Ghostwriter's existing
# `pipeline.card_batch.run_card_batch` + `run_chunked_card_batches` pattern:
#
#   - Chunk by `brief_section` so each call sees ~30-80 items instead of
#     100-600 (recall on tail items degrades with input size).
#   - Inside each chunk, retry up to MAX_GATEKEEPER_MISSING_IDX_RETRIES with
#     a missing-only payload when the model's response doesn't echo every
#     input `_idx`.
#   - Reconcile cross-section clusters post-merge so the cluster-aware
#     preservation rule (`prompts/gatekeeper_prompt.md` cluster section)
#     still applies globally even though Gatekeeper saw only fragments.
#
# See `.claude/plans/let-s-start-with-1-hidden-prism.md` for design rationale.


def _collect_input_ids(batch_items: list[dict]) -> tuple[list[int], dict[int, dict]]:
    """Return (`expected_ids`, `item_by_id`) keyed on integer `_idx`.

    Items lacking a usable `_idx` are silently skipped — they were already
    out-of-contract before reaching this function. The caller can detect
    "items dropped here" by comparing input length vs len(expected_ids).
    """
    expected_ids: list[int] = []
    item_by_id: dict[int, dict] = {}
    for item in batch_items:
        idx = item.get("_idx")
        if idx is None:
            continue
        try:
            idx_int = int(idx)
        except (TypeError, ValueError):
            continue
        # Defensive: skip duplicate `_idx` values — keep first.
        if idx_int in item_by_id:
            continue
        expected_ids.append(idx_int)
        item_by_id[idx_int] = item
    return expected_ids, item_by_id


async def run_gatekeeper_with_retry(
    *,
    client: anthropic.AsyncAnthropic,
    batch_items: list[dict],
    label: str = "main",
    max_retries: int = MAX_GATEKEEPER_MISSING_IDX_RETRIES,
    completeness_threshold: float = 0.85,
) -> tuple[Optional[dict], dict, dict]:
    """Run a single Gatekeeper call with a missing-items retry loop.

    Mirrors `pipeline.card_batch.run_card_batch` in spirit but uses a
    count-based completeness check instead of strict per-id matching.
    Reason: production data shows Sonnet drops `_idx` echoing at scale
    (`gk_rekeyer.py` notes 0% echo rate at 180+ items), so strict `_idx`
    enforcement would trigger massive false-positive retries. Instead we:

      1. Accept every item the LLM returned (whether or not it echoed `_idx`).
      2. Dedupe items by `_idx` when present, otherwise by normalized headline.
      3. Compare output_count to input_count; if below
         `completeness_threshold`, retry with a count-discrepancy note.
         Specific missing `_idx` values, when known, are listed in the
         retry message.
      4. The orchestrator's existing rekeyer + implicit-drop detector
         continues to handle the residual `_idx` rejoining downstream
         (we don't try to replace its job).

    Parameters
    ----------
    client
        Async Anthropic client.
    batch_items
        Lightweight Gatekeeper-input items (each carries `_idx` plus the
        fields whitelisted by `orchestrator.GATEKEEPER_KEEP_FIELDS`).
    label
        Log label for this batch (e.g. "single", "sec-UAE").
    max_retries
        Number of additional attempts after the first call. Default 2,
        matching the Ghostwriter's MAX_GHOSTWRITER_MISSING_ID_RETRIES.
    completeness_threshold
        Trigger retry when `output_count < input_count * threshold`.
        0.85 leaves slack for legitimate model judgment to merge a
        couple of items, while still catching wholesale omissions.

    Returns
    -------
    `(merged_result, usage, telemetry)` where:
      - merged_result has the same shape as `run_gatekeeper`'s output.
      - usage aggregates `input_tokens`/`output_tokens` across all attempts.
      - telemetry: `{"input_count", "output_count", "retries_used",
                     "still_missing_count", "addressed_idx_count"}`.
    """
    expected_ids, item_by_id = _collect_input_ids(batch_items)
    input_count = len(expected_ids)
    expected_id_set = set(expected_ids)

    # Items collected across all attempts. Keyed by `_idx` when present
    # and by normalized headline when not (to dedupe across retries).
    collected_selected: dict = {}
    collected_dropped: dict = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    correction_suffix = ""
    retries_used = 0

    if input_count == 0:
        return (
            {"selected": [], "dropped": [], "brief_summary": {}},
            usage_total,
            {
                "input_count": 0,
                "output_count": 0,
                "retries_used": 0,
                "still_missing_count": 0,
                "addressed_idx_count": 0,
            },
        )

    def _normalized_headline_key(headline: str) -> str:
        return re.sub(r"\s+", " ", (headline or "")).strip().lower()[:120]

    def _record_item(item: dict, bucket: dict) -> bool:
        """Insert `item` into `bucket` keyed by _idx (preferred) or headline.

        Returns True if newly added, False if duplicate of an existing entry.
        """
        idx = item.get("_idx")
        try:
            idx_int = int(idx) if idx is not None else None
        except (TypeError, ValueError):
            idx_int = None
        # Reject items whose _idx is not in our input set (model hallucination).
        if idx_int is not None and idx_int not in expected_id_set:
            return False
        if idx_int is not None:
            key = ("idx", idx_int)
        else:
            hl = _normalized_headline_key(item.get("headline", ""))
            if not hl:
                return False
            key = ("hl", hl)
        if key in bucket:
            return False
        bucket[key] = item
        return True

    for attempt in range(1 + max_retries):
        # Build payload: full set on first attempt; on retry send the
        # full set again BUT with a correction note about the count
        # discrepancy. (We can't reliably know which specific items the
        # model missed when it doesn't echo _idx, so re-sending the full
        # set is the safest recovery.)
        chunk_scout_json = json.dumps(batch_items, indent=2, ensure_ascii=False)
        prompt = load_prompt(
            "gatekeeper_prompt.md",
            scout_output=chunk_scout_json,
        ) + correction_suffix

        if attempt > 0:
            retries_used += 1
            wait = 2 + random.uniform(0, 1)
            print(
                f"{_timestamp()}   Gatekeeper [{label}] backing off "
                f"{wait:.1f}s before completeness retry "
                f"(attempt {attempt + 1}/{1 + max_retries})..."
            )
            await asyncio.sleep(wait)

        try:
            result, usage = await run_gatekeeper(client, prompt)
            usage_total["input_tokens"] += usage["input_tokens"]
            usage_total["output_tokens"] += usage["output_tokens"]
        except (
            anthropic.APIError,
            anthropic.APITimeoutError,
            httpx.TimeoutException,
            json.JSONDecodeError,
            ValueError,
            ValidationError,
        ) as e:
            logger.warning(
                "Gatekeeper [%s] attempt %d failed: %s",
                label,
                attempt + 1,
                e,
            )
            print(
                f"{_timestamp()}   ⚠️  Gatekeeper [{label}] attempt "
                f"{attempt + 1} failed: {type(e).__name__}; "
                f"will retry if budget remains."
            )
            correction_suffix = _build_retry_correction("gatekeeper", e)
            continue

        # Drain selected and dropped into our collection buckets.
        for item in (result.get("selected") or []):
            _record_item(item, collected_selected)
        for item in (result.get("dropped") or []):
            _record_item(item, collected_dropped)

        # Completeness check: did we address most of the input?
        addressed_count = len(collected_selected) + len(collected_dropped)
        if addressed_count >= input_count * completeness_threshold:
            break  # good enough — stop retrying

        # Identify specific _idx misses (when echoed) for the correction msg.
        addressed_idx = {
            k[1] for k in (list(collected_selected.keys()) + list(collected_dropped.keys()))
            if k[0] == "idx"
        }
        missing_idx_specific = [i for i in expected_ids if i not in addressed_idx]

        # Build the retry note. If we have specific _idx misses, list them;
        # otherwise communicate the count gap and ask for completeness.
        if missing_idx_specific:
            sample = missing_idx_specific[:30]
            ellipsis = "…" if len(missing_idx_specific) > 30 else ""
            msg = (
                f"You addressed {addressed_count} of {input_count} input "
                f"items. Specific `_idx` values still missing from your "
                f"`selected` and `dropped` arrays: {sample}{ellipsis}. "
                f"Re-emit JSON containing every missing item placed in "
                f"either `selected` or `dropped` — you can keep your "
                f"prior decisions for the items you already addressed, "
                f"OR emit only the missing ones (we will merge)."
            )
        else:
            msg = (
                f"You returned {addressed_count} items but I sent "
                f"{input_count}. The contract requires every input item "
                f"to appear in either `selected` or `dropped`. Re-emit "
                f"with the full set scored — pay particular attention to "
                f"items toward the end of the input pool, which is where "
                f"completeness regressions typically occur."
            )
        correction_suffix = _build_retry_correction(
            "gatekeeper", ValueError(msg)
        )
        print(
            f"{_timestamp()}   ⚠️  Gatekeeper [{label}] addressed "
            f"{addressed_count}/{input_count} items "
            f"(threshold {completeness_threshold:.0%}), retrying..."
        )

    final_selected = list(collected_selected.values())
    final_dropped = list(collected_dropped.values())
    addressed_count = len(final_selected) + len(final_dropped)
    addressed_idx = {
        k[1] for k in (list(collected_selected.keys()) + list(collected_dropped.keys()))
        if k[0] == "idx"
    }
    still_missing_count = max(0, input_count - addressed_count)

    if still_missing_count > 0:
        logger.warning(
            "Gatekeeper [%s] addressed %d/%d items after %d attempts "
            "(retries=%d). %d truly silent.",
            label,
            addressed_count,
            input_count,
            1 + retries_used,
            retries_used,
            still_missing_count,
        )

    if not final_selected and not final_dropped:
        return (
            None,
            usage_total,
            {
                "input_count": input_count,
                "output_count": 0,
                "retries_used": retries_used,
                "still_missing_count": still_missing_count,
                "addressed_idx_count": len(addressed_idx),
            },
        )

    # Reconstruct brief_summary defensively — same pattern as run_gatekeeper's
    # truncation guard. Sections are pre-assigned by the upstream classifier
    # so we read brief_section straight off the items.
    section_distribution: dict[str, int] = {}
    for item in final_selected:
        section = item.get("brief_section") or item.get("section") or "Unknown"
        section_distribution[section] = section_distribution.get(section, 0) + 1
    merged = {
        "selected": final_selected,
        "dropped": final_dropped,
        "brief_summary": {
            "total_input_items": input_count,
            "after_deduplication": 0,
            "selected": len(final_selected),
            "dropped": len(final_dropped),
            "section_distribution": section_distribution,
            "notable_decisions": (
                f"Chunk [{label}] processed {input_count} input items "
                f"with {retries_used} completeness retries; "
                f"{still_missing_count} item(s) still silent after retries."
            ),
        },
    }

    telemetry = {
        "input_count": input_count,
        "output_count": addressed_count,
        "retries_used": retries_used,
        "still_missing_count": still_missing_count,
        "addressed_idx_count": len(addressed_idx),
    }

    return merged, usage_total, telemetry


def reconcile_cross_section_clusters(
    selected: list[dict],
    dropped: list[dict],
) -> tuple[list[dict], list[dict], int]:
    """Re-apply the cluster-aware preservation rule globally post-chunking.

    After per-section chunking, each chunk's Gatekeeper applied the
    cluster-aware rule (`prompts/gatekeeper_prompt.md` cluster section)
    only on its local fragment. For clusters whose items were split across
    sections, this can over-include `standard` and `major` tier clusters.
    This pass restores the intended global behavior:

      - head_of_state: keep all (no-op).
      - major: keep top-3 by composite_score; demote rest.
      - standard: keep top-1 by composite_score; demote rest.

    Items lacking `cluster_id` pass through untouched. Demoted items get
    `_stage = 'cross_section_cluster_demote'` and a drop_reason for
    `/admin/drops` audit visibility.

    Returns `(new_selected, new_dropped, demoted_count)` so the caller
    can emit the count in telemetry.
    """
    if not selected:
        return list(selected), list(dropped), 0

    # Group selected items by cluster_id (skip items with no cluster).
    by_cluster: dict[str, list[dict]] = {}
    no_cluster: list[dict] = []
    for item in selected:
        cluster_id = item.get("cluster_id")
        if not cluster_id:
            no_cluster.append(item)
            continue
        by_cluster.setdefault(cluster_id, []).append(item)

    new_selected: list[dict] = list(no_cluster)
    new_dropped: list[dict] = list(dropped)
    demoted_count = 0

    # Tier caps. head_of_state is uncapped (intentionally preserve all
    # facets per the prompt's granular-inclusion rule for top-tier visits).
    tier_cap = {
        "head_of_state": None,
        "major": 3,
        "standard": 1,
    }

    for cluster_id, items in by_cluster.items():
        # Single-section clusters need no reconciliation — the chunk
        # already enforced the rule. Detect by checking that all items
        # share the same `brief_section`.
        sections = {it.get("brief_section") for it in items}
        if len(sections) <= 1:
            new_selected.extend(items)
            continue

        # Cross-section cluster — re-apply tier rule globally.
        tier = items[0].get("cluster_significance_tier") or "standard"
        cap = tier_cap.get(tier, 1)
        # Sort by composite_score descending; ties broken by _idx (stable).
        items_sorted = sorted(
            items,
            key=lambda x: (
                -float(x.get("composite_score") or 0.0),
                int(x.get("_idx") or 0),
            ),
        )
        if cap is None or len(items_sorted) <= cap:
            new_selected.extend(items_sorted)
            continue

        keep = items_sorted[:cap]
        demote = items_sorted[cap:]
        new_selected.extend(keep)
        for d in demote:
            d_copy = dict(d)
            d_copy["_stage"] = "cross_section_cluster_demote"
            d_copy["drop_reason"] = (
                f"Cross-section cluster cap ({tier} tier): "
                f"{len(items_sorted)} items in cluster {cluster_id} across "
                f"{len(sections)} sections, kept top {cap} by composite_score"
            )
            new_dropped.append(d_copy)
            demoted_count += 1

    return new_selected, new_dropped, demoted_count


async def run_chunked_gatekeeper(
    *,
    client: anthropic.AsyncAnthropic,
    lightweight_items: list[dict],
    max_retries: int = MAX_GATEKEEPER_MISSING_IDX_RETRIES,
    single_call_threshold: int = SINGLE_CALL_THRESHOLD,
) -> tuple[Optional[dict], dict, dict]:
    """Run the Gatekeeper in parallel per `brief_section` and merge results.

    Partitions `lightweight_items` by their pre-assigned `brief_section`
    (the upstream Haiku section classifier already populated this field).
    Each section's items run through `run_gatekeeper_with_retry`
    concurrently via `asyncio.gather`. Outputs are merged, then a
    `reconcile_cross_section_clusters` pass restores the global
    cluster-aware preservation rule.

    Fast-path: when `len(lightweight_items) <= single_call_threshold` the
    whole pool runs in a single call, preserving low-volume-day behavior.

    Returns
    -------
    `(merged_result, usage, telemetry)`:
      - merged_result has shape `{"selected": [...], "dropped": [...],
        "brief_summary": {...}}`.
      - usage aggregates input/output tokens across all chunks (including
        the retry attempts).
      - telemetry: per-section counts, retries, missing-idx counts, and
        `cross_section_clusters_demoted` for `pipeline_runs.gatekeeper_log`.
    """
    if not lightweight_items:
        return (
            {"selected": [], "dropped": [], "brief_summary": {}},
            {"input_tokens": 0, "output_tokens": 0},
            {"chunked": False, "total_input": 0, "total_output": 0},
        )

    # Fast-path: single call for low-volume days.
    if len(lightweight_items) <= single_call_threshold:
        print(
            f"{_timestamp()} Gatekeeper (single-call fast path): "
            f"{len(lightweight_items)} items <= threshold "
            f"{single_call_threshold}"
        )
        result, usage, sub_telemetry = await run_gatekeeper_with_retry(
            client=client,
            batch_items=lightweight_items,
            label="single",
            max_retries=max_retries,
        )
        if result is None:
            return None, usage, {
                "chunked": False,
                "total_input": len(lightweight_items),
                "total_output": 0,
                "single_call": sub_telemetry,
                "cross_section_clusters_demoted": 0,
            }
        # Reconciliation is a no-op on single-call (no chunking happened),
        # but run it for output-shape consistency and to catch any
        # cross-section cluster oddities the single Sonnet call might emit.
        reconciled_selected, reconciled_dropped, demoted = (
            reconcile_cross_section_clusters(
                result.get("selected") or [],
                result.get("dropped") or [],
            )
        )
        result["selected"] = reconciled_selected
        result["dropped"] = reconciled_dropped
        return (
            result,
            usage,
            {
                "chunked": False,
                "total_input": len(lightweight_items),
                "total_output": (
                    len(reconciled_selected) + len(reconciled_dropped)
                ),
                "single_call": sub_telemetry,
                "cross_section_clusters_demoted": demoted,
            },
        )

    # Chunk path: partition by brief_section.
    buckets: dict[str, list[dict]] = {s: [] for s in CANONICAL_SECTIONS}
    buckets[UNSECTIONED_BUCKET] = []
    for item in lightweight_items:
        sec = item.get("brief_section")
        if sec in CANONICAL_SECTIONS:
            buckets[sec].append(item)
        else:
            buckets[UNSECTIONED_BUCKET].append(item)

    print(
        f"{_timestamp()} Gatekeeper (chunked): "
        f"{len(lightweight_items)} items across "
        f"{sum(1 for v in buckets.values() if v)} non-empty section(s)"
    )
    for sec, items in buckets.items():
        if items:
            print(f"{_timestamp()}   {sec}: {len(items)} item(s)")

    async def _run_chunk(section: str, items: list[dict]):
        if not items:
            return section, None, {"input_tokens": 0, "output_tokens": 0}, {
                "input_count": 0,
                "output_count": 0,
                "retries_used": 0,
                "still_missing_count": 0,
                "addressed_idx_count": 0,
            }
        # Sanitize the label for log readability — section names contain
        # spaces and ampersands.
        safe_label = re.sub(r"\W+", "_", section)[:24] or "chunk"
        result, usage, telemetry = await run_gatekeeper_with_retry(
            client=client,
            batch_items=items,
            label=f"sec-{safe_label}",
            max_retries=max_retries,
        )
        return section, result, usage, telemetry

    chunk_outputs = await asyncio.gather(
        *[_run_chunk(s, items) for s, items in buckets.items()]
    )

    # Merge selected/dropped/usage across chunks; collect per-section telemetry.
    merged_selected: list[dict] = []
    merged_dropped: list[dict] = []
    merged_usage = {"input_tokens": 0, "output_tokens": 0}
    per_section_input: dict[str, int] = {}
    per_section_output: dict[str, int] = {}
    retries_per_section: dict[str, int] = {}
    still_missing_per_section: dict[str, int] = {}

    for section, result, usage, telemetry in chunk_outputs:
        merged_usage["input_tokens"] += usage.get("input_tokens", 0)
        merged_usage["output_tokens"] += usage.get("output_tokens", 0)
        per_section_input[section] = telemetry["input_count"]
        per_section_output[section] = telemetry["output_count"]
        retries_per_section[section] = telemetry["retries_used"]
        still_missing_per_section[section] = telemetry["still_missing_count"]
        if not result:
            continue
        merged_selected.extend(result.get("selected") or [])
        merged_dropped.extend(result.get("dropped") or [])

    # Cluster reconciliation runs on the merged pool.
    reconciled_selected, reconciled_dropped, demoted = (
        reconcile_cross_section_clusters(merged_selected, merged_dropped)
    )

    if not reconciled_selected and not reconciled_dropped:
        return (
            None,
            merged_usage,
            {
                "chunked": True,
                "total_input": len(lightweight_items),
                "total_output": 0,
                "per_section_input_count": per_section_input,
                "per_section_output_count": per_section_output,
                "retries_per_section": retries_per_section,
                "still_missing_per_section": still_missing_per_section,
                "cross_section_clusters_demoted": demoted,
            },
        )

    # Reconstruct brief_summary across all chunks.
    section_distribution: dict[str, int] = {}
    for item in reconciled_selected:
        section = item.get("brief_section") or item.get("section") or "Unknown"
        section_distribution[section] = section_distribution.get(section, 0) + 1

    total_retries = sum(retries_per_section.values())
    total_missing = sum(still_missing_per_section.values())
    print(
        f"{_timestamp()} Gatekeeper (chunked) merged: "
        f"{len(reconciled_selected)} selected, {len(reconciled_dropped)} dropped "
        f"({total_retries} retry attempts, {total_missing} truly silent, "
        f"{demoted} cross-section-cluster demoted)"
    )

    merged_result = {
        "selected": reconciled_selected,
        "dropped": reconciled_dropped,
        "brief_summary": {
            "total_input_items": len(lightweight_items),
            "after_deduplication": 0,
            "selected": len(reconciled_selected),
            "dropped": len(reconciled_dropped),
            "section_distribution": section_distribution,
            "notable_decisions": (
                f"Chunked across {sum(1 for v in buckets.values() if v)} "
                f"section(s); {total_retries} missing-_idx retry attempts; "
                f"{total_missing} silent omissions remaining; "
                f"{demoted} cross-section cluster items demoted."
            ),
        },
    }

    telemetry = {
        "chunked": True,
        "total_input": len(lightweight_items),
        "total_output": len(reconciled_selected) + len(reconciled_dropped),
        "per_section_input_count": per_section_input,
        "per_section_output_count": per_section_output,
        "retries_per_section": retries_per_section,
        "still_missing_per_section": still_missing_per_section,
        "cross_section_clusters_demoted": demoted,
    }

    return merged_result, merged_usage, telemetry
