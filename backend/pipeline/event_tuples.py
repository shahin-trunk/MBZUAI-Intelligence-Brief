"""Event-tuple extraction stage — structural fingerprint per item.

Phase 2 of the post-2026-04-27 structural fix. Replaces the prompt-clause
arms race in within-day dedup (`_semantic_dedup`) and cross-day history
dedup (`run_history_dedup`) with mechanical tuple comparison.

Each item gets an `_event_tuple` dict capturing
`{event_type, primary_actor, counterpart, action, location, date_or_period,
key_numbers}`. Phase 3 (within-day dedup) and Phase 4 (history dedup) then
compare items by event fingerprint instead of asking another Haiku judge.

Pattern mirrors `pipeline.section_classifier.classify_candidate_sections`:
single async entry point with chunking + parallel batches + fail-open
semantics. Uses Anthropic Structured Outputs (Nov 2025 GA) via
`client.messages.parse()` for guaranteed schema compliance, with a manual
JSON-parsing fallback for the (rare) case where the SDK or model rejects
the structured-outputs request.

The stage is idempotent: re-running on items that already carry tuples is
a no-op. Fails open: extraction errors leave items without tuples, and
downstream stages fall back to their pre-Phase-2 logic.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import anthropic
from pydantic import ValidationError

from models.schemas import EventTupleBatchOutput
from prompts.loader import extract_prompt_from_md
from config import PROMPTS_DIR

logger = logging.getLogger(__name__)


EXTRACT_MODEL = "claude-haiku-4-5-20251001"
EXTRACT_MAX_TOKENS = 4000  # ~30 items × ~120 output tokens per tuple
EXTRACT_TIMEOUT = 90       # seconds, mirrors section_classifier timeout

# Mirrors section_classifier batching (30 items per call, 5 concurrent
# batches). 325 items on a typical 4/27-shape day -> 11 chunks -> ~3 round
# trips at concurrency 5. Cost: ~$0.18/run.
EXTRACT_BATCH_SIZE = 30
EXTRACT_CONCURRENCY = 5

# Fail-open status sentinels in the telemetry dict.
_STATUS_OK = "ok"
_STATUS_IDEMPOTENT_SKIP = "idempotent_skip"
_STATUS_PARTIAL = "partial"
_STATUS_FAILED_OPEN = "failed_open"


def _candidate_signal(item: dict) -> str:
    """Build the per-item input string sent to the extractor.

    Headline first, then a short summary slice (300 chars) so the judge can
    disambiguate things like which entity is the primary actor in a
    headline whose subject is unclear from the headline alone. Mirrors the
    snippet length used by triage's `_build_triage_line` for consistency.
    """
    headline = (item.get("headline") or "").strip()
    raw = item.get("summary") or item.get("raw_content") or ""
    if isinstance(raw, (dict, list)):
        raw = json.dumps(raw, ensure_ascii=False)
    raw = str(raw).strip()
    if len(raw) > 300:
        raw = raw[:300]
    return f"{headline} | {raw}" if raw else headline


def _build_user_message(items: list[dict]) -> str:
    """Numbered list of items for the extractor. 0-based ids match the
    input batch order so the response can be merged back by index.
    """
    lines = [
        f"{i}. {_candidate_signal(item)}"
        for i, item in enumerate(items)
    ]
    return "\n".join(lines)


def _load_extraction_prompt() -> str:
    """Read the extraction system prompt from disk.

    Bypasses `prompts.loader.load_prompt` because that helper auto-fills
    `{recent_history}`, `{date}`, and other dynamic placeholders that
    aren't relevant to extraction (and would make tests non-deterministic).
    """
    raw_md = (PROMPTS_DIR / "event_extraction_prompt.md").read_text(
        encoding="utf-8"
    )
    return extract_prompt_from_md(raw_md)


async def _extract_one_batch_structured(
    client: anthropic.AsyncAnthropic,
    chunk: list[dict],
    system_prompt: str,
) -> tuple[EventTupleBatchOutput | None, dict]:
    """Preferred path: use Anthropic Structured Outputs via `messages.parse()`.

    Returns `(parsed_output, attempt_log)`. `parsed_output` is None on any
    failure (network, validation, schema rejection); the caller falls back
    to the manual-JSON path.
    """
    user_msg = _build_user_message(chunk)
    attempt_log: dict = {
        "path": "structured_outputs",
        "input_chars": len(user_msg),
    }
    try:
        response = await client.messages.parse(
            model=EXTRACT_MODEL,
            max_tokens=EXTRACT_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
            output_format=EventTupleBatchOutput,
            timeout=EXTRACT_TIMEOUT,
        )
    except (TypeError, AttributeError) as e:
        # SDK doesn't support `parse()` / `output_format` — fall back.
        attempt_log["status"] = "sdk_unsupported"
        attempt_log["error"] = str(e)[:200]
        return None, attempt_log
    except Exception as e:
        attempt_log["status"] = "request_failed"
        attempt_log["error"] = str(e)[:200]
        return None, attempt_log

    parsed = getattr(response, "parsed_output", None)
    if parsed is None:
        # Some SDK versions place parsed objects under `parsed` instead.
        parsed = getattr(response, "parsed", None)
    if not isinstance(parsed, EventTupleBatchOutput):
        attempt_log["status"] = "no_parsed_output"
        return None, attempt_log

    usage = getattr(response, "usage", None)
    attempt_log.update({
        "status": "ok",
        "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
    })
    return parsed, attempt_log


async def _extract_one_batch_manual(
    client: anthropic.AsyncAnthropic,
    chunk: list[dict],
    system_prompt: str,
) -> tuple[EventTupleBatchOutput | None, dict]:
    """Fallback path: prompt-only JSON, manual extract + Pydantic validation.

    Used when `messages.parse()` is unavailable or the structured-outputs
    request is rejected (e.g. SDK older than 0.42.0). The prompt itself
    instructs the model to return strict JSON; we then parse + validate.
    """
    user_msg = _build_user_message(chunk)
    attempt_log: dict = {
        "path": "manual_json",
        "input_chars": len(user_msg),
    }
    try:
        response = await client.messages.create(
            model=EXTRACT_MODEL,
            max_tokens=EXTRACT_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
            timeout=EXTRACT_TIMEOUT,
        )
    except Exception as e:
        attempt_log["status"] = "request_failed"
        attempt_log["error"] = str(e)[:200]
        return None, attempt_log

    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    # Strip ```json ... ``` fences if present.
    raw_clean = re.sub(r"^```(?:json)?\s*", "", raw)
    raw_clean = re.sub(r"\s*```$", "", raw_clean).strip()

    try:
        payload = json.loads(raw_clean)
    except json.JSONDecodeError as e:
        attempt_log["status"] = "json_parse_failed"
        attempt_log["error"] = str(e)[:200]
        attempt_log["raw_preview"] = raw[:300]
        return None, attempt_log

    try:
        validated = EventTupleBatchOutput.model_validate(payload)
    except ValidationError as e:
        attempt_log["status"] = "schema_validation_failed"
        attempt_log["error"] = str(e)[:300]
        return None, attempt_log

    usage = getattr(response, "usage", None)
    attempt_log.update({
        "status": "ok",
        "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
    })
    return validated, attempt_log


async def _extract_one_batch(
    client: anthropic.AsyncAnthropic,
    chunk: list[dict],
    system_prompt: str,
) -> tuple[EventTupleBatchOutput | None, list[dict]]:
    """Try structured outputs first; fall back to manual JSON on failure.

    Returns `(parsed_or_none, [attempt_log, ...])`. The attempt_log list
    captures both attempts when the fallback was needed, so telemetry
    can show which path produced the verdict.
    """
    parsed, log_struct = await _extract_one_batch_structured(
        client, chunk, system_prompt
    )
    attempts = [log_struct]
    if parsed is not None:
        return parsed, attempts

    parsed, log_manual = await _extract_one_batch_manual(
        client, chunk, system_prompt
    )
    attempts.append(log_manual)
    return parsed, attempts


def _apply_tuples(
    items: list[dict],
    chunk_offset: int,
    parsed: EventTupleBatchOutput | None,
) -> int:
    """Mutate items in place, adding `_event_tuple`. Returns count applied.

    `chunk_offset` is the global index of `parsed.verdicts[0]` — verdicts
    use chunk-local 0-based ids, so we add the offset to find the global
    item.
    """
    if parsed is None:
        return 0
    applied = 0
    for verdict in parsed.verdicts:
        global_idx = chunk_offset + verdict.id
        if 0 <= global_idx < len(items):
            items[global_idx]["_event_tuple"] = verdict.tuple_.model_dump(
                mode="json"
            )
            applied += 1
    return applied


async def extract_event_tuples(
    client: anthropic.AsyncAnthropic,
    items: list[dict],
) -> tuple[list[dict], dict]:
    """Extract structured event tuples for each item.

    Mutates `items` in place: adds `_event_tuple` field with shape:
      {
        "event_type": <one of EventType>,
        "primary_actor": str | None,
        "counterpart": str | None,
        "action": str,
        "location": str | None,
        "date_or_period": str | None,
        "key_numbers": list[str],
      }

    Returns `(items, telemetry)`. Telemetry has shape:
      {
        "status": "ok" | "partial" | "failed_open" | "idempotent_skip",
        "total_items": int,
        "tuples_extracted": int,
        "tuples_failed": int,
        "input_tokens": int,
        "output_tokens": int,
        "chunks": [<per-chunk attempt log>, ...],
      }

    Idempotent: if every item already has `_event_tuple`, returns
    immediately with status="idempotent_skip" — safe to call on
    `--from-stage` resume paths without double-billing.

    Fails open: per-chunk extraction failures leave those items WITHOUT
    `_event_tuple`. Downstream Phase 3 / Phase 4 stages must handle
    missing tuples by falling back to legacy LLM-judged dedup.
    """
    if not items:
        return items, {
            "status": _STATUS_OK,
            "total_items": 0,
            "tuples_extracted": 0,
            "tuples_failed": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "chunks": [],
        }

    # Idempotent skip: if every item already has a tuple, this is a resume
    # path. Mirrors the section_classifier idempotency check.
    if all(item.get("_event_tuple") for item in items):
        logger.info(
            "event_tuples: all %d items already have tuples; idempotent skip",
            len(items),
        )
        return items, {
            "status": _STATUS_IDEMPOTENT_SKIP,
            "total_items": len(items),
            "tuples_extracted": len(items),
            "tuples_failed": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "chunks": [],
        }

    system_prompt = _load_extraction_prompt()

    # Chunk into batches of EXTRACT_BATCH_SIZE.
    chunks: list[tuple[int, list[dict]]] = []
    for start in range(0, len(items), EXTRACT_BATCH_SIZE):
        chunks.append((start, items[start:start + EXTRACT_BATCH_SIZE]))

    sem = asyncio.Semaphore(EXTRACT_CONCURRENCY)

    async def _run_one(chunk_offset: int, chunk: list[dict]):
        async with sem:
            return chunk_offset, await _extract_one_batch(
                client, chunk, system_prompt
            )

    results = await asyncio.gather(
        *[_run_one(off, ch) for off, ch in chunks]
    )

    total_extracted = 0
    total_input_tokens = 0
    total_output_tokens = 0
    chunk_telemetry: list[dict] = []
    chunks_succeeded = 0

    for chunk_offset, (parsed, attempts) in results:
        applied = _apply_tuples(items, chunk_offset, parsed)
        total_extracted += applied
        ok = parsed is not None
        if ok:
            chunks_succeeded += 1
        chunk_log = {
            "chunk_offset": chunk_offset,
            "size": len(chunks[chunk_offset // EXTRACT_BATCH_SIZE][1]),
            "tuples_applied": applied,
            "status": "ok" if ok else "fallback_failed",
            "attempts": attempts,
        }
        for a in attempts:
            total_input_tokens += a.get("input_tokens", 0)
            total_output_tokens += a.get("output_tokens", 0)
        chunk_telemetry.append(chunk_log)

    if chunks_succeeded == len(chunks):
        status = _STATUS_OK
    elif chunks_succeeded == 0:
        status = _STATUS_FAILED_OPEN
        logger.warning(
            "event_tuples: all %d chunks failed extraction; downstream "
            "stages will fall back to legacy LLM-judged dedup",
            len(chunks),
        )
    else:
        status = _STATUS_PARTIAL
        logger.warning(
            "event_tuples: %d/%d chunks extracted; %d items lack tuples",
            chunks_succeeded, len(chunks),
            len(items) - total_extracted,
        )

    return items, {
        "status": status,
        "total_items": len(items),
        "tuples_extracted": total_extracted,
        "tuples_failed": len(items) - total_extracted,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "chunks": chunk_telemetry,
    }
