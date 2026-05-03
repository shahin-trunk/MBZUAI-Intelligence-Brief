"""Content Filter agent — classifies scout items as NEWS or NOT_NEWS.

Runs as a hard gate between scouts and the gatekeeper. Items classified
as NOT_NEWS are removed from the pipeline before the gatekeeper sees them,
preventing the gatekeeper from rationalizing non-news items back in.
"""

import json
import logging
import re

import anthropic
from pydantic import ValidationError

from config import CONTENT_FILTER_MODEL, STAGE_TIMEOUTS
from models.schemas import ContentFilterOutput
from pipeline.json_utils import safe_parse_json

logger = logging.getLogger(__name__)

CONTENT_FILTER_MAX_TOKENS = 24000  # Supports ~200 items after newsletter splitting


def _validate_with_pydantic(model_cls, payload: dict) -> dict:
    """Validate payload with Pydantic across v1/v2."""
    if hasattr(model_cls, "model_validate"):
        model = model_cls.model_validate(payload)
        return model.model_dump()
    model = model_cls.parse_obj(payload)
    return model.dict()


def extract_json_object(text: str) -> dict:
    """Extract a JSON object from text that may be wrapped in markdown fences."""
    fence_match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
    if fence_match:
        return safe_parse_json(fence_match.group(1))

    obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if obj_match:
        return safe_parse_json(obj_match.group(1))

    raise ValueError("No JSON object found in Content Filter response")


async def run_content_filter(
    client: anthropic.AsyncAnthropic,
    prompt_text: str,
) -> tuple[dict, dict]:
    """Run the Content Filter agent.

    Args:
        client: Async Anthropic client.
        prompt_text: Fully templated Content Filter prompt with items injected.

    Returns:
        Tuple of (result dict with 'verdicts' list, usage dict).
    """
    response = await client.messages.create(
        model=CONTENT_FILTER_MODEL,
        max_tokens=CONTENT_FILTER_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=STAGE_TIMEOUTS["content_filter"],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    logger.info(
        f"Content Filter: stop_reason={response.stop_reason}, "
        f"tokens_in={usage['input_tokens']}, tokens_out={usage['output_tokens']}"
    )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ValueError("Content Filter: No text blocks in response")

    full_text = "\n".join(text_blocks)

    try:
        result = extract_json_object(full_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Content Filter: Failed to parse JSON. Preview: {full_text[:500]}"
        ) from e

    try:
        result = _validate_with_pydantic(ContentFilterOutput, result)
    except ValidationError as e:
        raise ValueError(
            f"Content Filter: Output schema validation failed: {e}"
        ) from e

    # Enforce per-item contract. The new prompt emits `decision` (KEEP/DROP);
    # the legacy prompt emitted `keep` (bool) or `verdict` (str). Accept any
    # one of the three — the orchestrator's verdict-consumption logic handles
    # the mapping.
    for i, verdict in enumerate(result.get("verdicts", [])):
        if verdict.get("id") is None and verdict.get("index") is None:
            raise ValueError(
                f"Content Filter: verdict[{i}] missing both 'id' and 'index'"
            )
        if (
            verdict.get("decision") is None
            and verdict.get("keep") is None
            and verdict.get("verdict") is None
        ):
            raise ValueError(
                f"Content Filter: verdict[{i}] missing 'decision' (and legacy 'keep'/'verdict')"
            )

    return result, usage
