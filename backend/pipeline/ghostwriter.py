from __future__ import annotations

import json
import logging
import re
from typing import Optional

import anthropic
from pydantic import ValidationError

from config import MODEL, STAGE_TIMEOUTS
from models.schemas import GhostwriterOutput
from pipeline.json_utils import safe_parse_json

logger = logging.getLogger(__name__)

GHOSTWRITER_MAX_TOKENS = 32000


def _validate_with_pydantic(model_cls, payload: dict) -> dict:
    """Validate payload with Pydantic across v1/v2."""
    if hasattr(model_cls, "model_validate"):
        model = model_cls.model_validate(payload)
        return model.model_dump()
    model = model_cls.parse_obj(payload)
    return model.dict()


def _coerce_exhibit_data(payload: dict) -> dict:
    """Wrap bare-list ``exhibit.data`` values as ``{"items": [...]}``.

    ``ExhibitData.data`` is typed ``dict``. The model-release agent
    occasionally emits the list of entries directly (``data: [...]``)
    instead of wrapping them under a key (``data: {"items": [...]}``).
    This mutates the payload in place so Pydantic validation can proceed.
    """
    for item in payload.get("items") or []:
        for exhibit in item.get("exhibits") or []:
            if isinstance(exhibit.get("data"), list):
                exhibit["data"] = {"items": exhibit["data"]}
    return payload


def extract_json_object(text: str) -> dict:
    """Extract a JSON object from text that may be wrapped in markdown fences."""
    fence_match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
    if fence_match:
        return safe_parse_json(fence_match.group(1))

    obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if obj_match:
        return safe_parse_json(obj_match.group(1))

    raise ValueError("No JSON object found in response text")


async def run_ghostwriter(
    client: anthropic.AsyncAnthropic,
    prompt_text: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> tuple:
    """Run the Ghostwriter agent.

    Args:
        client: Async Anthropic client.
        prompt_text: Fully templated Ghostwriter prompt with gatekeeper output injected.
        model: Model override (defaults to config.MODEL).
        max_tokens: Max output tokens override (defaults to GHOSTWRITER_MAX_TOKENS).

    Returns:
        Tuple of (result dict, usage dict).

    Refusal fallback
    ----------------
    When ``model`` overrides ``MODEL`` (e.g. a just-released Opus trial)
    and that model returns ``stop_reason="refusal"`` — as Opus 4.7 did on
    2026-04-17 across two runs with identical token counts on the same
    17-item batch — this function retries the prompt once against the
    canonical ``MODEL`` instead of raising. If the override is already
    ``MODEL`` (or the fallback also refuses), the caller gets the
    ValueError and can decide how to handle it. Usage tokens from both
    calls are summed in the returned usage dict.
    """
    requested_model = model or MODEL
    resolved_max_tokens = max_tokens or GHOSTWRITER_MAX_TOKENS

    response = await client.messages.create(
        model=requested_model,
        max_tokens=resolved_max_tokens,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=STAGE_TIMEOUTS["ghostwriter"],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    logger.info(f"Ghostwriter: model={requested_model}, "
                f"stop_reason={response.stop_reason}, "
                f"tokens_in={usage['input_tokens']}, tokens_out={usage['output_tokens']}")

    text_blocks = [block.text for block in response.content if block.type == "text"]

    # Refusal fallback. If the override model refused, retry once against
    # the canonical MODEL. Check refusal first (regardless of whether
    # text_blocks is empty) because Anthropic emits refusals as a
    # non-text content block, so a refusal reliably produces 0 text
    # blocks — but we want to be explicit that we're handling refusal,
    # not just "empty response."
    if response.stop_reason == "refusal" and requested_model != MODEL:
        logger.warning(
            "Ghostwriter: %s refused (stop_reason=refusal, tokens_in=%d, "
            "tokens_out=%d). Falling back to %s and retrying once.",
            requested_model,
            usage["input_tokens"],
            usage["output_tokens"],
            MODEL,
        )
        fallback = await client.messages.create(
            model=MODEL,
            max_tokens=resolved_max_tokens,
            messages=[{"role": "user", "content": prompt_text}],
            timeout=STAGE_TIMEOUTS["ghostwriter"],
        )
        usage["input_tokens"] += fallback.usage.input_tokens
        usage["output_tokens"] += fallback.usage.output_tokens
        logger.info(
            "Ghostwriter fallback: model=%s, stop_reason=%s, "
            "tokens_in=%d, tokens_out=%d",
            MODEL,
            fallback.stop_reason,
            fallback.usage.input_tokens,
            fallback.usage.output_tokens,
        )
        text_blocks = [b.text for b in fallback.content if b.type == "text"]
        if not text_blocks:
            raise ValueError(
                f"Ghostwriter: {requested_model} refused and fallback to "
                f"{MODEL} also returned no text blocks "
                f"(stop_reason={fallback.stop_reason})"
            )
    elif not text_blocks:
        raise ValueError(
            f"Ghostwriter: No text blocks in response "
            f"(stop_reason={response.stop_reason}, model={requested_model})"
        )

    full_text = "\n".join(text_blocks)

    try:
        result = extract_json_object(full_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Ghostwriter: Failed to parse JSON. Preview: {full_text[:500]}"
        ) from e

    result = _coerce_exhibit_data(result)

    try:
        result = _validate_with_pydantic(GhostwriterOutput, result)
    except ValidationError as e:
        raise ValueError(f"Ghostwriter: Output schema validation failed: {e}") from e

    return result, usage
