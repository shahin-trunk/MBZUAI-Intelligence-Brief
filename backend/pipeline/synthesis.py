"""Synthesis agent — event-level clustering + continuity annotation.

Runs AFTER the Content Filter and BEFORE the Gatekeeper. Its job is to
group related items into event-level clusters and annotate each cluster's
continuity status against the last 3 days of brief history. The Gatekeeper
uses the cluster metadata to make granular inclusion decisions (e.g., keep
multiple items from a head-of-state state visit cluster; drop a pure
restatement cluster).

This replaces the fuzzy-string `flag_previous_brief_overlaps` filter and
lifts cluster reasoning out of the Gatekeeper prompt — see Phase 2 of
`.claude/plans/robust-sleeping-raven.md` for context on why.

The module is intentionally a near-clone of `content_filter.py` so the
orchestrator integration pattern (retry loop, usage tracking, schema
validation) is identical.
"""

from __future__ import annotations

import json
import logging

import anthropic
from pydantic import ValidationError

from config import CONTENT_FILTER_MODEL, STAGE_TIMEOUTS
from models.schemas import SynthesisOutput
from pipeline.content_filter import _validate_with_pydantic, extract_json_object

logger = logging.getLogger(__name__)

# Budget for one Synthesis call. The agent must output N clusters +
# N item_annotations on up to ~250 post-content-filter items. Haiku 4.5
# supports 64K output tokens; we size near the top because annotation
# output scales linearly with item count.
SYNTHESIS_MAX_TOKENS = 64000


async def run_synthesis(
    client: anthropic.AsyncAnthropic,
    prompt_text: str,
) -> tuple[dict, dict]:
    """Run the Synthesis agent.

    Args:
        client: Async Anthropic client (Haiku 4.5 model).
        prompt_text: Fully templated Synthesis prompt with items_json +
            previous_brief_headlines already injected.

    Returns:
        Tuple of (result dict validated against SynthesisOutput, usage dict).

    Raises:
        ValueError: on JSON parse failure or schema validation failure.
            The orchestrator retries once on error and fails-open if the
            retry also fails.
    """
    # Use streaming — the response can be large (one annotation per item for
    # ~200 items) and non-streaming requests with large max_tokens can
    # exceed the HTTP timeout even though generation is still progressing.
    # See https://docs.anthropic.com/en/api/errors#long-requests.
    full_text_parts: list[str] = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    stop_reason = ""
    async with client.messages.stream(
        model=CONTENT_FILTER_MODEL,  # Haiku 4.5
        max_tokens=SYNTHESIS_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=STAGE_TIMEOUTS.get("synthesis", 600),
    ) as stream:
        async for chunk in stream.text_stream:
            full_text_parts.append(chunk)
        final_message = await stream.get_final_message()
        usage["input_tokens"] = final_message.usage.input_tokens
        usage["output_tokens"] = final_message.usage.output_tokens
        stop_reason = final_message.stop_reason or ""

    logger.info(
        f"Synthesis: stop_reason={stop_reason}, "
        f"tokens_in={usage['input_tokens']}, tokens_out={usage['output_tokens']}"
    )

    full_text = "".join(full_text_parts)
    if not full_text.strip():
        raise ValueError("Synthesis: No text in streamed response")

    try:
        result = extract_json_object(full_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Synthesis: Failed to parse JSON. Preview: {full_text[:500]}"
        ) from e

    try:
        result = _validate_with_pydantic(SynthesisOutput, result)
    except ValidationError as e:
        raise ValueError(
            f"Synthesis: Output schema validation failed: {e}"
        ) from e

    # Sanity check: every cluster's member_item_ids should be covered by
    # item_annotations. Partial coverage is not fatal — the caller falls
    # back to None annotations via apply_synthesis_annotations — but it is
    # worth logging loudly so a degraded Synthesis run is visible in stdout.
    # The usual cause is Haiku hitting max_tokens on output; tune
    # SYNTHESIS_MAX_TOKENS if this happens routinely.
    cluster_members: set[int] = set()
    for cluster in result.get("clusters", []):
        cluster_members.update(cluster.get("member_item_ids", []))
    annotated_ids = {
        ann.get("item_id") for ann in result.get("item_annotations", [])
    }
    missing = cluster_members - annotated_ids
    if missing:
        logger.warning(
            "Synthesis: %d item_id(s) appear in cluster member_item_ids but "
            "lack item_annotations (will be passed to Gatekeeper with cluster "
            "metadata but no facet tag): %s%s",
            len(missing),
            sorted(missing)[:10],
            "..." if len(missing) > 10 else "",
        )

    return result, usage


def apply_synthesis_annotations(
    items: list[dict],
    synthesis_result: dict,
) -> tuple[int, int]:
    """Merge Synthesis cluster + annotation metadata back onto pipeline items.

    Adds seven fields to each annotated item (matching the field names added
    to GATEKEEPER_KEEP_FIELDS so the Gatekeeper receives them):

    - cluster_id: str | None
    - cluster_event_key: str | None
    - cluster_composite_headline: str | None
    - cluster_continuity: "new_story" | "continuation" | "restatement" | None
    - cluster_continuity_reference: str | None
    - cluster_significance_tier: "head_of_state" | "major" | "standard" | None
    - facet: str | None

    Items without a matching annotation get None values (fail-open behavior).

    Args:
        items: Ordered list of pipeline items (index is the item_id the
            Synthesis agent saw).
        synthesis_result: The dict returned by run_synthesis.

    Returns:
        Tuple of (annotated_count, unannotated_count).
    """
    # Build lookup: item_id -> cluster + annotation.
    cluster_by_id: dict[str, dict] = {
        c["cluster_id"]: c for c in synthesis_result.get("clusters", [])
    }
    annotations_by_item: dict[int, dict] = {}
    for ann in synthesis_result.get("item_annotations", []):
        item_id = ann.get("item_id")
        if isinstance(item_id, int):
            annotations_by_item[item_id] = ann

    # Fallback map: if Haiku truncated `item_annotations` but still included
    # an item in a cluster's `member_item_ids`, we can still deliver cluster
    # metadata (cluster_id / event_key / significance_tier / continuity) to
    # the Gatekeeper — just without a per-item facet tag.
    cluster_by_member: dict[int, dict] = {}
    for cluster in synthesis_result.get("clusters", []):
        for mem_id in cluster.get("member_item_ids", []):
            if isinstance(mem_id, int):
                cluster_by_member.setdefault(mem_id, cluster)

    annotated = 0
    for idx, item in enumerate(items):
        ann = annotations_by_item.get(idx)
        fallback_cluster = cluster_by_member.get(idx)

        if ann:
            cluster = cluster_by_id.get(ann.get("cluster_id"), {})
            item["cluster_id"] = ann.get("cluster_id")
            item["cluster_event_key"] = cluster.get("event_key")
            item["cluster_composite_headline"] = cluster.get("composite_headline")
            item["cluster_continuity"] = ann.get("continuity_status") \
                or cluster.get("continuity_status")
            item["cluster_continuity_reference"] = (
                ann.get("continuity_reference")
                or cluster.get("continuity_reference")
            )
            item["cluster_significance_tier"] = cluster.get("significance_tier")
            item["facet"] = ann.get("facet")
            annotated += 1
        elif fallback_cluster:
            # Cluster metadata only — no individual annotation. Still better
            # than nothing; the Gatekeeper's cluster rules still apply.
            item["cluster_id"] = fallback_cluster.get("cluster_id")
            item["cluster_event_key"] = fallback_cluster.get("event_key")
            item["cluster_composite_headline"] = fallback_cluster.get(
                "composite_headline"
            )
            item["cluster_continuity"] = fallback_cluster.get("continuity_status")
            item["cluster_continuity_reference"] = fallback_cluster.get(
                "continuity_reference"
            )
            item["cluster_significance_tier"] = fallback_cluster.get(
                "significance_tier"
            )
            item["facet"] = None
            annotated += 1
        else:
            # Fail-open: leave with None fields so Gatekeeper sees a
            # consistent schema.
            item.setdefault("cluster_id", None)
            item.setdefault("cluster_event_key", None)
            item.setdefault("cluster_composite_headline", None)
            item.setdefault("cluster_continuity", None)
            item.setdefault("cluster_continuity_reference", None)
            item.setdefault("cluster_significance_tier", None)
            item.setdefault("facet", None)

    return annotated, len(items) - annotated


def clear_synthesis_annotations(items: list[dict]) -> None:
    """Set all synthesis fields to None on every item.

    Called when Synthesis fails and we're running in fail-open mode — this
    guarantees the Gatekeeper sees a consistent schema (None everywhere)
    rather than a mix of missing and set fields from partial retries.
    """
    for item in items:
        item["cluster_id"] = None
        item["cluster_event_key"] = None
        item["cluster_composite_headline"] = None
        item["cluster_continuity"] = None
        item["cluster_continuity_reference"] = None
        item["cluster_significance_tier"] = None
        item["facet"] = None
