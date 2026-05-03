"""Entity Classifier agent.

Runs AFTER Ghostwriter, BEFORE Editor. For each item in the Ghostwriter
output, classifies the `primary_entity` into one of 10 categories aligned
with `entity_logos.category`. The orchestrator merges the result back onto
the Ghostwriter items so downstream stages (Editor, ingest_brief,
ingest_draft, frontend) see `primary_entity_category` alongside
`primary_entity`.

Keeping classification in a dedicated Haiku 4.5 stage (rather than widening
the Ghostwriter prompt) preserves Ghostwriter's focus on writing. See
`.claude/plans/robust-sleeping-raven.md` for the design rationale.

Mirrors the `backend/pipeline/synthesis.py` streaming + validation pattern
so the orchestrator integration looks identical.
"""

from __future__ import annotations

import json
import logging

import anthropic
from pydantic import ValidationError

from config import CONTENT_FILTER_MODEL, STAGE_TIMEOUTS
from models.schemas import EntityClassificationOutput
from pipeline.content_filter import _validate_with_pydantic, extract_json_object
from pipeline.entity_category import infer_entity_category
from pipeline.entity_identity import resolve_story_identity

logger = logging.getLogger(__name__)

# Classification is a narrow task — ~15 items with one short string +
# optional rationale each. 8K output is comfortable headroom.
ENTITY_CLASSIFIER_MAX_TOKENS = 8000


async def run_entity_classifier(
    client: anthropic.AsyncAnthropic,
    prompt_text: str,
) -> tuple[dict, dict]:
    """Run the Entity Classifier agent.

    Args:
        client: Async Anthropic client (Haiku 4.5 model).
        prompt_text: Fully templated prompt with items_json substituted.

    Returns:
        Tuple of (result dict validated against EntityClassificationOutput,
        usage dict with input_tokens/output_tokens).

    Raises:
        ValueError: on JSON parse failure or schema validation failure.
            The orchestrator retries once on error and fails-open if the
            retry also fails (items go through with
            primary_entity_category=None).
    """
    full_text_parts: list[str] = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    stop_reason = ""
    async with client.messages.stream(
        model=CONTENT_FILTER_MODEL,  # Haiku 4.5
        max_tokens=ENTITY_CLASSIFIER_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=STAGE_TIMEOUTS.get("entity_classifier", 120),
    ) as stream:
        async for chunk in stream.text_stream:
            full_text_parts.append(chunk)
        final_message = await stream.get_final_message()
        usage["input_tokens"] = final_message.usage.input_tokens
        usage["output_tokens"] = final_message.usage.output_tokens
        stop_reason = final_message.stop_reason or ""

    logger.info(
        f"Entity Classifier: stop_reason={stop_reason}, "
        f"tokens_in={usage['input_tokens']}, tokens_out={usage['output_tokens']}"
    )

    full_text = "".join(full_text_parts)
    if not full_text.strip():
        raise ValueError("Entity Classifier: No text in streamed response")

    try:
        result = extract_json_object(full_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Entity Classifier: Failed to parse JSON. Preview: {full_text[:500]}"
        ) from e

    try:
        result = _validate_with_pydantic(EntityClassificationOutput, result)
    except ValidationError as e:
        raise ValueError(
            f"Entity Classifier: Output schema validation failed: {e}"
        ) from e

    return result, usage


def apply_entity_classifications(
    items: list[dict],
    classifier_result: dict | None,
) -> tuple[int, int]:
    """Merge classifier output back onto Ghostwriter items by id.

    Every input item is guaranteed to have `primary_entity_category` set
    after this call — either to a valid category from the classifier, a
    deterministic heuristic fallback, or None when neither has enough
    signal.

    Returns (annotated_count, unannotated_count).
    """
    lookup: dict[str, str] = {}
    if classifier_result:
        classifications = classifier_result.get("classifications", [])
        for c in classifications:
            item_id = c.get("id")
            cat = c.get("primary_entity_category")
            if isinstance(item_id, str) and isinstance(cat, str):
                lookup[item_id] = cat
        skipped = len(classifications) - len(lookup)
        if skipped > 0:
            logger.warning(
                "Entity Classifier: %d/%d classifications skipped (malformed id or category)",
                skipped, len(classifications),
            )

    annotated = 0
    for item in items:
        item_id = item.get("id")
        cat = lookup.get(item_id) if isinstance(item_id, str) else None
        if cat is None:
            cat = infer_entity_category(item)
        item["primary_entity_category"] = cat
        identity = resolve_story_identity(item, cat)
        item["primary_subject"] = identity["primary_subject"]
        item["primary_subject_type"] = identity["primary_subject_type"]
        item["badge_subject"] = identity["badge_subject"]
        item["badge_subject_type"] = identity["badge_subject_type"]
        item["badge_subject_category"] = identity["badge_subject_category"]
        if cat is not None:
            annotated += 1

    return annotated, len(items) - annotated


def build_classifier_input_items(items: list[dict]) -> list[dict]:
    """Extract the fields the classifier needs from a Ghostwriter item list.

    The agent only sees headline + section + primary_entity so it has enough
    context to disambiguate (e.g. "Khalifa" the person vs "Khalifa University"
    the institution) without reading the whole item.
    """
    return [
        {
            "id": item.get("id"),
            "primary_entity": item.get("primary_entity"),
            "headline": item.get("headline", ""),
            "section": item.get("section", ""),
        }
        for item in items
        if item.get("primary_entity")  # skip items with no entity to classify
    ]
