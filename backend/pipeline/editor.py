from __future__ import annotations

import json
import logging
import re
from typing import Optional

import anthropic
from pydantic import ValidationError

from config import MODEL, STAGE_TIMEOUTS
from models.schemas import EditorOutput
from pipeline.json_utils import safe_parse_json

logger = logging.getLogger(__name__)

# Editor needs high max_tokens because it outputs its audit steps as text
# before the final JSON. With 9-11 items, the JSON alone can be 20K+ tokens.
EDITOR_MAX_TOKENS = 32000


def _validate_with_pydantic(model_cls, payload: dict) -> dict:
    """Validate payload with Pydantic across v1/v2."""
    if hasattr(model_cls, "model_validate"):
        model = model_cls.model_validate(payload)
        return model.model_dump()
    model = model_cls.parse_obj(payload)
    return model.dict()


def extract_json_object(text: str) -> dict:
    """Extract a JSON object from text that may be wrapped in markdown fences.

    Tries multiple strategies:
    1. Look for complete JSON in code fences
    2. Look for complete JSON object in raw text
    3. Find the last top-level JSON object (the editor outputs audit text
       before the JSON, so the JSON is at the end)
    """
    # Strategy 1: code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(\{.*\})\s*\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return safe_parse_json(fence_match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 2: find the outermost JSON object starting from the last
    # occurrence of {"final_brief" or {"brief_metadata" (editor's expected output)
    for marker in ['"final_brief"', '"brief_metadata"']:
        idx = text.rfind(marker)
        if idx == -1:
            continue
        # Walk backwards to find the opening brace
        brace_idx = text.rfind("{", 0, idx)
        if brace_idx == -1:
            continue
        candidate = text[brace_idx:]
        try:
            result = safe_parse_json(candidate)
            return result
        except (json.JSONDecodeError, ValueError):
            # Try to find the matching closing brace
            repaired = repair_truncated_json_object(candidate)
            if repaired:
                return repaired

    # Strategy 3: generic — find any JSON object
    obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if obj_match:
        try:
            return safe_parse_json(obj_match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 4: truncated JSON repair
    repaired = repair_truncated_json_object(text)
    if repaired:
        return repaired

    raise ValueError("No JSON object found in response text")


def repair_truncated_json_object(text: str) -> dict | None:
    """Attempt to repair a truncated JSON object.

    The editor output has structure:
    { "final_brief": { "brief_metadata": {...}, "items": [...] },
      "email_brief": null,
      "edit_log": [...] }

    If truncated, we try to close the open structures.
    """
    # Find the start of the JSON object
    obj_start = text.find("{")
    if obj_start == -1:
        return None

    json_text = text[obj_start:]

    # Track nesting to find where we need to close
    depth_brace = 0
    depth_bracket = 0
    in_string = False
    escape_next = False
    last_valid_pos = -1

    for i, ch in enumerate(json_text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1

        # Track positions where we're at a reasonable closing point
        if depth_brace >= 0 and depth_bracket >= 0:
            last_valid_pos = i

    if last_valid_pos == -1:
        return None

    # Take the text up to the last valid position and close all open structures
    truncated = json_text[: last_valid_pos + 1].rstrip().rstrip(",")
    closing = "]" * depth_bracket + "}" * depth_brace
    repaired = truncated + closing

    try:
        result = safe_parse_json(repaired)
        logger.warning(f"Repaired truncated editor JSON (closed {depth_brace} braces, {depth_bracket} brackets)")
        return result
    except (json.JSONDecodeError, ValueError):
        return None


async def run_editor(
    client: anthropic.AsyncAnthropic,
    prompt_text: str,
) -> tuple:
    """Run the Editor agent.

    Args:
        client: Async Anthropic client.
        prompt_text: Fully templated Editor prompt with ghostwriter and gatekeeper output.

    Returns:
        Tuple of (result dict, usage dict).
    """
    response = await client.messages.create(
        model=MODEL,
        max_tokens=EDITOR_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=STAGE_TIMEOUTS["editor"],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    logger.info(f"Editor: stop_reason={response.stop_reason}, "
                f"tokens_in={usage['input_tokens']}, tokens_out={usage['output_tokens']}")

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ValueError("Editor: No text blocks in response")

    full_text = "\n".join(text_blocks)

    try:
        result = extract_json_object(full_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Editor: Failed to parse JSON. Preview: {full_text[:500]}"
        ) from e

    if "final_brief" not in result and "brief_metadata" in result and "items" in result:
        # The editor sometimes returns only final_brief; wrap it before validation.
        result = {"final_brief": result, "email_brief": None, "edit_log": []}

    try:
        result = _validate_with_pydantic(EditorOutput, result)
    except ValidationError as e:
        raise ValueError(f"Editor: Output schema validation failed: {e}") from e

    return result, usage
