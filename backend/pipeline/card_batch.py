"""Card-batch runner and agent router for the Ghostwriter stage.

This module carries two responsibilities that used to live as nested
closures inside ``pipeline.orchestrator.run_pipeline``:

1. ``run_card_batch`` — run a single Ghostwriter batch with retries,
   enforce the ID contract, and run model-release completeness
   validation. Callable directly by orchestrator paths that don't need
   routing (e.g., the draft-mode Haiku chunks).

2. ``route_and_run_card_agents`` — the main-Ghostwriter entry point.
   Currently a thin pass-through to ``run_card_batch`` with the
   standard Ghostwriter prompt. In a later refactor step this function
   will partition items by ``is_model_release`` and route release
   items to a specialized Haiku agent.

Extracting these out of the orchestrator closure:

* makes both the scaffolding and the retry/merge logic reusable from
  ``backend/evals/eval_ghostwriter_ab.py``;
* surfaces the ``today`` and ``client`` captures as explicit arguments;
* is a pure structural refactor — behavior is identical to the
  pre-refactor nested version.

See ``.claude/plans/pure-honking-shore.md`` for rationale.
"""
from __future__ import annotations

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

from config import MODEL, CONTENT_FILTER_MODEL
from pipeline.ghostwriter import run_ghostwriter
from pipeline.exhibit_formatter import format_exhibits
from pipeline.exhibit_formatter import format_model_release_data  # noqa: F811 — explicit for clarity
from pipeline.section_classifier import classify_sections
from pipeline.ghostwriter_validate import (
    log_soft_violations,
    scan_item_for_banned_phrases,
    validate_batch,
)
from pipeline.model_release import validate_model_release_output
from prompts.loader import load_prompt

# Mirror the model choice the orchestrator uses elsewhere for Haiku-
# level work. CONTENT_FILTER_MODEL is the canonical "use Haiku" constant.
HAIKU_MODEL = CONTENT_FILTER_MODEL
# Temporary rollback to Sonnet 4.6 (2026-04-17): Opus 4.7 produced a
# deterministic refusal (stop_reason=refusal, 0 text blocks) on today's
# 17-item gatekeeper batch — reproduced across two runs with identical
# token counts. Sonnet 4.6 was the last known stable model for this
# stage; Opus 4.6/4.7 never successfully ran the morning brief. Revisit
# once we add refusal fallback handling in ghostwriter.py or bisect the
# offending item.
GHOSTWRITER_MODEL = MODEL
STANDARD_GHOSTWRITER_PROMPT = "ghostwriter_prompt.md"
MODEL_RELEASE_CARD_PROMPT = "model_release_card_prompt.md"

logger = logging.getLogger(__name__)

# Kept in sync with orchestrator.MAX_GHOSTWRITER_MISSING_ID_RETRIES.
# Duplicated here to keep this module self-contained (orchestrator imports
# from us, not the other way around).
MAX_GHOSTWRITER_MISSING_ID_RETRIES = 2

_GST = ZoneInfo("Asia/Dubai")


def _timestamp() -> str:
    return datetime.now(_GST).strftime("%H:%M:%S")


def _build_retry_correction(stage: str, error: Exception) -> str:
    """Compact retry note appended to the prompt on a failed attempt.

    Kept in sync with ``pipeline.orchestrator.build_retry_correction``.
    Duplicated here to avoid a circular import — if orchestrator changes
    this text, update it here too.
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


async def run_card_batch(
    *,
    client: anthropic.AsyncAnthropic,
    batch_items: list[dict],
    gatekeeper_payload: dict,
    today: str,
    batch_label: str = "main",
    batch_model: str = MODEL,
    batch_max_tokens: int = 32000,
    include_dropped: bool = True,
    prompt_filename: str = "ghostwriter_prompt.md",
) -> tuple[Optional[dict], dict]:
    """Run one Ghostwriter batch and enforce the exact ID contract.

    Parameters mirror the pre-refactor nested ``_run_gw_batch``.  Returns
    ``(result_dict_or_None, usage_dict)`` where ``result_dict`` has
    shape ``{"date": today, "items": [...]}``.  The ID contract is
    enforced by up to ``MAX_GHOSTWRITER_MISSING_ID_RETRIES`` retries;
    any items still missing after retries are dropped with a warning.
    """
    expected_ids = [str(i.get("id", "")).strip() for i in batch_items if i.get("id")]
    item_by_id = {str(i["id"]): i for i in batch_items if i.get("id")}
    remaining_ids = expected_ids[:]
    collected_by_id: dict[str, dict] = {}
    batch_usage = {"input_tokens": 0, "output_tokens": 0}
    correction_suffix = ""
    validation_failures: dict[str, list[str]] = {}

    for _ in range(1 + MAX_GHOSTWRITER_MISSING_ID_RETRIES):
        if not remaining_ids:
            break

        remaining_items = [item_by_id[item_id] for item_id in remaining_ids if item_id in item_by_id]
        batch_gk = {
            "selected": remaining_items,
            "allowed_ids": remaining_ids,
            "brief_summary": gatekeeper_payload.get("brief_summary", {}),
            "id_contract": "Return exactly one item for each allowed id and do not invent ids.",
        }
        if include_dropped:
            batch_gk["dropped"] = gatekeeper_payload.get("dropped", [])
        batch_gk_json = json.dumps(batch_gk, indent=2, ensure_ascii=False)
        batch_prompt = load_prompt(
            prompt_filename,
            gatekeeper_output=batch_gk_json,
        ) + correction_suffix

        result = None
        for attempt in range(2):
            if attempt > 0:
                wait = 2 + random.uniform(0, 1)
                print(f"{_timestamp()}   Backing off {wait:.1f}s before {batch_label} retry...")
                await asyncio.sleep(wait)
            try:
                result, usage = await run_ghostwriter(
                    client, batch_prompt,
                    model=batch_model,
                    max_tokens=batch_max_tokens,
                )
                batch_usage["input_tokens"] += usage["input_tokens"]
                batch_usage["output_tokens"] += usage["output_tokens"]
                break
            except (anthropic.APIError, anthropic.APITimeoutError, httpx.TimeoutException, json.JSONDecodeError) as e:
                if attempt == 0:
                    logger.warning(
                        f"Ghostwriter {batch_label} attempt 1 failed: {e}. Retrying..."
                    )
                    print(f"{_timestamp()} ⚠️  Ghostwriter {batch_label} failed, retrying...")
                    correction_suffix = _build_retry_correction("ghostwriter", e)
                else:
                    logger.error(f"Ghostwriter {batch_label} failed after 2 attempts: {e}")
                    print(f"{_timestamp()} ❌ Ghostwriter {batch_label} failed after 2 attempts: {e}")

        if not result:
            continue

        allowed_set = set(remaining_ids)
        seen_this_round: set[str] = set()
        invalid_ids: list[str] = []
        for item in result.get("items", []):
            item_id = str(item.get("id", "")).strip()
            if not item_id or item_id not in allowed_set or item_id in seen_this_round:
                invalid_ids.append(item_id or "<missing>")
                continue
            source_item = item_by_id.get(item_id, {})
            if source_item.get("is_model_release"):
                issues = validate_model_release_output(source_item, item)
                if issues:
                    validation_failures[item_id] = issues
                    logger.warning(
                        "Model release %s accepted with incomplete data: %s",
                        item_id, "; ".join(issues),
                    )
                    # Accept the item — prose is more valuable than perfect tables.
            seen_this_round.add(item_id)
            collected_by_id[item_id] = item

        remaining_ids = [i for i in remaining_ids if i not in seen_this_round]
        if remaining_ids:
            validation_lines = [
                f"{item_id}: {'; '.join(validation_failures[item_id])}"
                for item_id in remaining_ids
                if item_id in validation_failures
            ]
            msg = (
                f"Missing required IDs: {remaining_ids}. "
                f"Invalid/extra IDs seen: {invalid_ids}. "
                f"Model-release completeness failures: {validation_lines}. "
                "Return ONLY the missing IDs in valid JSON."
            )
            correction_suffix = _build_retry_correction("ghostwriter", ValueError(msg))
            print(
                f"{_timestamp()}   ⚠️  Ghostwriter {batch_label} missing "
                f"{len(remaining_ids)} ID(s), retrying missing only..."
            )

    final_items = [collected_by_id[i] for i in expected_ids if i in collected_by_id]
    missing_final = [i for i in expected_ids if i not in collected_by_id]
    if missing_final:
        print(
            f"{_timestamp()}   ❌ Ghostwriter {batch_label} missing IDs after retries: "
            f"{missing_final}"
        )
        for missing_id in missing_final:
            issues = validation_failures.get(missing_id)
            if issues:
                logger.warning(
                    "Ghostwriter %s completeness warning for %s: %s",
                    batch_label,
                    missing_id,
                    "; ".join(issues),
                )
                print(
                    f"{_timestamp()}   ⚠️  Model-release completeness warning for "
                    f"{missing_id}: {'; '.join(issues)}"
                )
    if not final_items:
        return None, batch_usage

    # --- Section classification (Haiku) -----------------------------
    # Dedicated classifier assigns each card to the correct section
    # based on headline + summary. Overrides the Ghostwriter's section
    # assignment, which is unreliable in the shorter prompt (~20%
    # misplacement rate observed 2026-04-16).
    final_items = await classify_sections(client, final_items)

    # --- Model-release exhibit formatting (deterministic) ------------
    # Clean up auto-generated model_release_data for card display:
    # abbreviate benchmark names, cap columns, clean cells. Only runs
    # on items with model_release_data (auto-generated by the Haiku
    # agent). Standalone exhibits (attached by the analyst during
    # curation) are formatted at attachment time via the curation API,
    # not here.
    for item in final_items:
        mrd = item.get("model_release_data")
        if mrd and isinstance(mrd, dict):
            format_model_release_data(mrd)

    # --- Domain-specific validation (log-only) ----------------------
    # Scan for domain-specific tics (MBZUAI flattery, intelligence-brief
    # jargon, editorial thesis-sentence framings). Log only — no retry.
    collected_items_by_id = {str(i.get("id", "")): i for i in final_items}
    report = validate_batch(collected_items_by_id)
    log_soft_violations(report, batch_label=batch_label)
    if report.banned_hits_by_id:
        for item_id, hits in report.banned_hits_by_id.items():
            logger.warning(
                "Domain-specific tic in %s: %s",
                item_id, hits,
            )

    return {"date": today, "items": final_items}, batch_usage


async def route_and_run_card_agents(
    *,
    client: anthropic.AsyncAnthropic,
    gatekeeper_payload: dict,
    today: str,
    selected: Optional[list[dict]] = None,
    standard_prompt_filename: str = STANDARD_GHOSTWRITER_PROMPT,
    model_release_prompt_filename: str = MODEL_RELEASE_CARD_PROMPT,
    include_dropped: bool = False,
    standard_model: Optional[str] = None,
    standard_max_tokens: int = 32000,
    standard_batch_label: str = "main",
    release_batch_label: str = "releases",
) -> tuple[Optional[dict], dict]:
    """Route selected items to the right card-writing agent and merge.

    Items with ``is_model_release=True`` are routed to a specialized
    Sonnet agent with the model-release prompt (Haiku produced
    incomplete benchmarks and missing ``developer`` fields). Everything
    else goes through the main Ghostwriter. Both batches run
    concurrently via ``asyncio.gather``. Outputs are merged in
    ``allowed_ids`` order so Gatekeeper rank is preserved.

    Parameters
    ----------
    client
        An ``anthropic.AsyncAnthropic`` client.
    gatekeeper_payload
        The full Gatekeeper output dict. Used to carry context the
        prompts reference.
    today
        Today's date as ``YYYY-MM-DD``; becomes ``result["date"]``.
    selected
        Override for the list of items to write. Defaults to
        ``gatekeeper_payload["selected"]``.
    standard_prompt_filename
        Prompt file for non-release cards. Bare filenames resolve
        against ``PROMPTS_DIR``; absolute paths are read directly
        (enables the eval harness to test alternate versions).
    model_release_prompt_filename
        Prompt file for model-release cards.
    include_dropped
        Pass the Gatekeeper's dropped items through to the prompt. The
        main production path sets this ``False``; a few legacy paths
        pass ``True``.
    standard_model
        Override for the model used on non-release items. ``None``
        (the default) means use ``GHOSTWRITER_MODEL``. The draft-mode
        drop-chunk loop passes ``HAIKU_MODEL`` here to keep drop costs
        bounded while still getting correct Sonnet routing on any
        model-release drops.
    standard_max_tokens
        Max output tokens for the standard branch. Defaults to 32000
        (the selected-items budget); drop chunks pass 16000.
    standard_batch_label / release_batch_label
        Labels used for logs and telemetry. Override when this router
        is reused for non-main batches (e.g. ``"draft-3/5-std"``) so
        log lines identify the chunk.

    Returns
    -------
    ``(result_dict_or_None, usage_dict)`` — same shape as
    ``run_card_batch``. ``result["items"]`` is merged in
    ``gatekeeper_payload["allowed_ids"]`` order (or the input
    ``selected`` order if allowed_ids isn't set).
    """
    if selected is None:
        selected = gatekeeper_payload.get("selected", [])

    # Partition by is_model_release. A small item (e.g. a single
    # release day) short-circuits the parallel gather.
    release_items = [i for i in selected if i.get("is_model_release")]
    standard_items = [i for i in selected if not i.get("is_model_release")]
    expected_order = [str(i.get("id", "")).strip() for i in selected if i.get("id")]

    resolved_standard_model = standard_model or GHOSTWRITER_MODEL

    async def _run_standard() -> tuple[Optional[dict], dict]:
        if not standard_items:
            return None, {"input_tokens": 0, "output_tokens": 0}
        return await run_card_batch(
            client=client,
            batch_items=standard_items,
            gatekeeper_payload=gatekeeper_payload,
            today=today,
            batch_label=standard_batch_label,
            batch_model=resolved_standard_model,
            batch_max_tokens=standard_max_tokens,
            include_dropped=include_dropped,
            prompt_filename=standard_prompt_filename,
        )

    async def _run_release() -> tuple[Optional[dict], dict]:
        if not release_items:
            return None, {"input_tokens": 0, "output_tokens": 0}
        # Sonnet handles the structured extraction (benchmarks, key_numbers,
        # developer). Haiku consistently dropped required fields, so this
        # stage is always Sonnet regardless of the standard_model override.
        # Uses the same run_card_batch scaffolding: ID contract, retry
        # loop, voice validation. Different prompt, different model.
        return await run_card_batch(
            client=client,
            batch_items=release_items,
            gatekeeper_payload=gatekeeper_payload,
            today=today,
            batch_label=release_batch_label,
            batch_model=MODEL,  # Sonnet — Haiku produced incomplete benchmarks
            batch_max_tokens=16000,
            include_dropped=False,
            prompt_filename=model_release_prompt_filename,
        )

    standard_result, release_result = await asyncio.gather(
        _run_standard(),
        _run_release(),
    )
    std_dict, std_usage = standard_result
    rel_dict, rel_usage = release_result

    # Merge: aggregate usage, then union items in expected_order.
    merged_usage = {
        "input_tokens": std_usage.get("input_tokens", 0) + rel_usage.get("input_tokens", 0),
        "output_tokens": std_usage.get("output_tokens", 0) + rel_usage.get("output_tokens", 0),
    }
    items_by_id: dict[str, dict] = {}
    for result_dict in (std_dict, rel_dict):
        if not result_dict:
            continue
        for item in result_dict.get("items", []):
            item_id = str(item.get("id", "")).strip()
            if item_id:
                items_by_id[item_id] = item

    if not items_by_id:
        return None, merged_usage

    # Preserve allowed_ids order so downstream rank/section sorting is intact.
    ordered_items = [items_by_id[i] for i in expected_order if i in items_by_id]
    # Anything that arrived with a non-expected ID (shouldn't happen given
    # the ID contract) tags on the end deterministically.
    extras = [v for k, v in items_by_id.items() if k not in expected_order]
    ordered_items.extend(extras)

    return {"date": today, "items": ordered_items}, merged_usage


async def run_chunked_card_batches(
    *,
    client: anthropic.AsyncAnthropic,
    gatekeeper_payload: dict,
    today: str,
    standard_prompt_filename: str = STANDARD_GHOSTWRITER_PROMPT,
    model_release_prompt_filename: str = MODEL_RELEASE_CARD_PROMPT,
    include_dropped: bool = False,
    standard_model: Optional[str] = None,
    chunk_size: int = 15,
) -> tuple[Optional[dict], dict]:
    """Ghostwriter wrapper that fans out by-section for parallel authoring.

    Phase 2 of the curation redesign: Gatekeeper now emits up to 15 items
    per section (5 sections = up to 75 items total). A single Ghostwriter
    call can't fit 75 items in a 32k-token output budget; chunk by section
    and fire each chunk concurrently via ``asyncio.gather``.

    Each chunk is its own ``route_and_run_card_agents`` call — ID contracts
    are per-batch (see [card_batch.py:121]) so parallel chunks with disjoint
    item sets don't race. Section labels are unique per chunk for log
    clarity.

    Fast path: if total selected ≤ ``chunk_size``, run a single unchunked
    call (no scheduling overhead for small days).

    Returns the merged (result_dict, usage_dict) in Gatekeeper's
    ``allowed_ids`` order, same shape as ``route_and_run_card_agents``.
    """
    selected = gatekeeper_payload.get("selected", [])
    if not selected:
        return None, {"input_tokens": 0, "output_tokens": 0}

    # Fast path — no chunking overhead if the slate is small.
    if len(selected) <= chunk_size:
        return await route_and_run_card_agents(
            client=client,
            gatekeeper_payload=gatekeeper_payload,
            today=today,
            selected=selected,
            standard_prompt_filename=standard_prompt_filename,
            model_release_prompt_filename=model_release_prompt_filename,
            include_dropped=include_dropped,
            standard_model=standard_model,
        )

    # Group by brief_section. Items without a section are grouped under
    # a sentinel key so they still get authored (should be rare post-
    # Phase 2 since the pre-Gatekeeper classifier assigns every item).
    buckets: dict[str, list[dict]] = {}
    for item in selected:
        sec = item.get("brief_section") or "__unsectioned__"
        buckets.setdefault(sec, []).append(item)

    # Preserve overall Gatekeeper order so post-merge ordering is stable.
    expected_order = [
        str(i.get("id", "")).strip() for i in selected if i.get("id")
    ]

    async def _run_chunk(section: str, items: list[dict]) -> tuple[Optional[dict], dict]:
        safe_label = re.sub(r"\W+", "_", section)[:20] or "chunk"
        return await route_and_run_card_agents(
            client=client,
            gatekeeper_payload=gatekeeper_payload,
            today=today,
            selected=items,
            standard_prompt_filename=standard_prompt_filename,
            model_release_prompt_filename=model_release_prompt_filename,
            include_dropped=include_dropped,
            standard_model=standard_model,
            standard_batch_label=f"sec-{safe_label}",
            release_batch_label=f"sec-{safe_label}-rel",
        )

    logger.info(
        "run_chunked_card_batches: fanning out %d item(s) across %d section(s)",
        len(selected), len(buckets),
    )
    print(
        f"{_timestamp()} Ghostwriter (chunked): {len(selected)} items "
        f"across {len(buckets)} section(s)"
    )

    chunk_results = await asyncio.gather(*[
        _run_chunk(section, items) for section, items in buckets.items()
    ])

    # Merge: aggregate usage, then union items in Gatekeeper's expected_order.
    merged_usage = {"input_tokens": 0, "output_tokens": 0}
    items_by_id: dict[str, dict] = {}
    for result_dict, usage in chunk_results:
        merged_usage["input_tokens"] += usage.get("input_tokens", 0)
        merged_usage["output_tokens"] += usage.get("output_tokens", 0)
        if not result_dict:
            continue
        for item in result_dict.get("items", []):
            item_id = str(item.get("id", "")).strip()
            if item_id:
                items_by_id[item_id] = item

    if not items_by_id:
        return None, merged_usage

    ordered_items = [items_by_id[i] for i in expected_order if i in items_by_id]
    extras = [v for k, v in items_by_id.items() if k not in expected_order]
    ordered_items.extend(extras)

    return {"date": today, "items": ordered_items}, merged_usage
