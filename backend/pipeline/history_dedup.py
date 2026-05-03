"""History Dedup agent — cross-day repeat detection via Haiku.

The deterministic `flag_previous_brief_overlaps` in the orchestrator
catches obvious headline matches against the last 3 days of published
briefs + pending drafts. This stage runs semantically on top of that to
catch paraphrased repeats the fuzzy match misses (e.g. a headline
rewrite that doesn't share enough tokens to trigger a fuzzy threshold).

Runs AFTER within-run dedup + date filtering and BEFORE Synthesis (on
the default production path) and BEFORE Gatekeeper (on legacy / resume
paths). Semantic dedup at this point keeps later stages focused on
fresh items only — Synthesis doesn't waste cluster slots on yesterday's
restatements, and Gatekeeper doesn't burn scoring budget on dupes.

The module is structured to mirror `content_filter.py` / `synthesis.py`
so the orchestrator integration pattern (streaming call, retry, schema
validation, drop-row emission) is consistent across stages.
"""

from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher

import anthropic
from pydantic import ValidationError

from config import CONTENT_FILTER_MODEL, STAGE_TIMEOUTS
from models.schemas import HistoryDedupOutput
from pipeline.content_filter import _validate_with_pydantic, extract_json_object
from pipeline.dedup import _distinctive_tokens, _normalize_headline

logger = logging.getLogger(__name__)

# When a verdict claims a candidate matches a history entry, we fuzzy-match
# the judge's cited `matched_headline` against the headlines that were
# actually in `recent_history`. 0.85 tolerates minor rephrasing/truncation
# while rejecting outright hallucinations where the judge names an unrelated
# historical headline. See 2026-04-20 "Olly Robbins exit → White House
# Mythos AI Model" false positive.
_MATCHED_HEADLINE_FUZZY_THRESHOLD = 0.85

# Budget for one history-dedup call. Input is modest (~100 candidates
# plus ~180 history entries); output is one small verdict per candidate
# so we don't need the full 64K Haiku ceiling that Synthesis uses.
HISTORY_DEDUP_MAX_TOKENS = 16000

# Drop-reason prefix used when emitting rows for the `dropped_items`
# table. Kept distinct from the deterministic tier's "Previous brief
# repeat — ..." prefix so /admin/drops can distinguish which stage
# caught a given item (see session notes on "Option B").
DROP_REASON_PREFIX = "History dedup (semantic)"

# Stage timeout. Falls back to a sensible default if not configured
# explicitly in STAGE_TIMEOUTS.
_STAGE_TIMEOUT_SECONDS = STAGE_TIMEOUTS.get("history_dedup", 300)

# Drop-reason prefix for the Phase 4 tuple-aware path. Distinct from
# the semantic prefix so /admin/drops can audit tuple-driven drops
# separately from Haiku-driven ones.
TUPLE_DROP_REASON_PREFIX = "History dedup (tuple)"


def run_tuple_aware_history_dedup(
    items: list[dict],
    recent_history: list[dict],
) -> tuple[dict, dict]:
    """Phase 4: mechanical tuple comparison vs cross-day history. No LLM call.

    For each candidate item with `_event_tuple`, compare against every
    `recent_history` entry that also carries an `event_tuple`. If
    `_tuple_match` returns True for any pair, the candidate is a repeat
    of that history entry — emit a drop verdict in the same shape as the
    Haiku `run_history_dedup` result so `apply_history_dedup_verdicts`
    can consume it unchanged.

    Returns ``(result_dict, telemetry)``:
      - result_dict has the same shape as Haiku output:
        ``{"verdicts": [{id, headline, is_repeat, matched_headline,
                          matched_brief_date, reason}, ...]}``
      - telemetry: ``{"items_with_tuples", "history_with_tuples",
        "drops", "skipped_no_tuple"}``

    Items lacking tuples produce no verdicts here — the caller routes
    them through the existing Haiku path. This is fail-open: Phase 2
    extraction failures don't poison the cross-day check.
    """
    # Local import to avoid circulars (dedup imports content_filter
    # which imports schemas, etc.).
    from pipeline.dedup import _tuple_match

    verdicts: list[dict] = []
    items_with_tuples = 0
    history_with_tuples = sum(
        1 for h in (recent_history or [])
        if isinstance(h, dict) and isinstance(h.get("event_tuple"), dict)
        and h.get("event_tuple")
    )
    drops = 0
    skipped_no_tuple = 0

    for idx, item in enumerate(items):
        item_tuple = item.get("_event_tuple")
        if not isinstance(item_tuple, dict) or not item_tuple:
            skipped_no_tuple += 1
            continue
        items_with_tuples += 1

        matched_history_entry = None
        match_reason = ""
        for hist in (recent_history or []):
            if not isinstance(hist, dict):
                continue
            hist_tuple = hist.get("event_tuple")
            if not isinstance(hist_tuple, dict) or not hist_tuple:
                continue
            same, reason = _tuple_match(item_tuple, hist_tuple)
            if same:
                matched_history_entry = hist
                match_reason = reason
                break

        if matched_history_entry is None:
            # Tuple comparison says NEW EVENT. Emit a non-repeat verdict
            # so the caller can short-circuit the Haiku call for this
            # item. (The Haiku call wouldn't override KEEP into DROP, but
            # being explicit lets us merge results cleanly.)
            verdicts.append({
                "id": idx,
                "headline": item.get("headline", ""),
                "is_repeat": False,
                "matched_headline": None,
                "matched_brief_date": None,
                "reason": "tuple comparison: no historical match",
            })
            continue

        # Tuple match found — emit a DROP verdict. Use the historical
        # entry's headline + brief_date so apply_history_dedup_verdicts'
        # coherence check passes (the matched_headline is verbatim
        # present in recent_history).
        drops += 1
        verdicts.append({
            "id": idx,
            "headline": item.get("headline", ""),
            "is_repeat": True,
            "matched_headline": matched_history_entry.get("headline", ""),
            "matched_brief_date": matched_history_entry.get("brief_date", ""),
            "reason": f"tuple match: {match_reason}",
        })

    return (
        {"verdicts": verdicts},
        {
            "items_with_tuples": items_with_tuples,
            "history_with_tuples": history_with_tuples,
            "drops": drops,
            "skipped_no_tuple": skipped_no_tuple,
            "items_total": len(items),
        },
    )


def merge_history_dedup_verdicts(
    primary: list[dict],
    fallback: list[dict],
) -> list[dict]:
    """Merge two verdict lists keyed by `id`, preferring `primary`.

    Used by the orchestrator when the tuple path covers SOME items and
    the Haiku fallback covers the rest. Primary verdicts always win;
    fallback verdicts fill in for items the primary didn't classify.
    """
    by_id: dict[int, dict] = {}
    for v in primary or []:
        if isinstance(v, dict) and isinstance(v.get("id"), int):
            by_id[v["id"]] = v
    for v in fallback or []:
        if isinstance(v, dict) and isinstance(v.get("id"), int):
            by_id.setdefault(v["id"], v)
    return [by_id[k] for k in sorted(by_id)]


async def run_history_dedup(
    client: anthropic.AsyncAnthropic,
    prompt_text: str,
) -> tuple[dict, dict]:
    """Run the History Dedup agent.

    Args:
        client: Async Anthropic client (Haiku 4.5 model).
        prompt_text: Fully templated history_dedup_prompt with items_json
            and recent_history already injected by `load_prompt`.

    Returns:
        Tuple of (result dict validated against HistoryDedupOutput,
        usage dict).

    Raises:
        ValueError: on JSON parse failure or schema validation failure.
            Callers should retry once and fail-open (pass items through
            untouched) on repeated failure.
    """
    full_text_parts: list[str] = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    stop_reason = ""

    # Streaming because the response may contain ~100 verdicts and
    # non-streaming calls with large max_tokens can hit HTTP timeouts
    # even while generation is still progressing.
    async with client.messages.stream(
        model=CONTENT_FILTER_MODEL,  # Haiku 4.5
        max_tokens=HISTORY_DEDUP_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=_STAGE_TIMEOUT_SECONDS,
    ) as stream:
        async for chunk in stream.text_stream:
            full_text_parts.append(chunk)
        final_message = await stream.get_final_message()
        usage["input_tokens"] = final_message.usage.input_tokens
        usage["output_tokens"] = final_message.usage.output_tokens
        stop_reason = final_message.stop_reason or ""

    logger.info(
        "History dedup: stop_reason=%s, tokens_in=%s, tokens_out=%s",
        stop_reason,
        usage["input_tokens"],
        usage["output_tokens"],
    )

    full_text = "".join(full_text_parts)
    if not full_text.strip():
        raise ValueError("History dedup: No text in streamed response")

    try:
        result = extract_json_object(full_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"History dedup: Failed to parse JSON. Preview: {full_text[:500]}"
        ) from e

    try:
        result = _validate_with_pydantic(HistoryDedupOutput, result)
    except ValidationError as e:
        raise ValueError(
            f"History dedup: Output schema validation failed: {e}"
        ) from e

    return result, usage


def _coherence_check_passes(
    candidate_headline: str,
    matched_headline: str,
    recent_history: list[dict] | None,
) -> tuple[bool, str]:
    """Verify a drop verdict is coherent before honoring it.

    Fails open: when `recent_history` is None we skip the check entirely
    (old callers get backward-compatible behavior). Two guards:

    1. The judge's `matched_headline` must actually appear in the list
       shown to the judge. Fuzzy threshold 0.85 tolerates minor
       rephrasing/truncation while catching the "judge hallucinated a
       cite" failure mode.
    2. Candidate and matched headline must share at least one
       distinctive (non-boilerplate) token. If they share nothing beyond
       structural words like "launches" / "raises", the "same story"
       claim is almost always wrong.

    Returns ``(passed, reason_if_failed)``. When `passed=False`, the
    reason is a short string for audit logging.
    """
    if not matched_headline:
        # Verdict claimed a drop but provided no cite — nothing to verify.
        # Be lenient: let it through. This is rare.
        return True, ""

    if recent_history is None:
        return True, ""

    # Guard 1: matched_headline must exist in the inputs the judge saw.
    mh_norm = _normalize_headline(matched_headline)
    best_ratio = 0.0
    for entry in recent_history:
        if not isinstance(entry, dict):
            continue
        hist_headline = entry.get("headline") or ""
        if not hist_headline:
            continue
        ratio = SequenceMatcher(
            None, mh_norm, _normalize_headline(hist_headline)
        ).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            if best_ratio >= 1.0:
                break

    if best_ratio < _MATCHED_HEADLINE_FUZZY_THRESHOLD:
        return False, (
            f"matched_headline not found in recent_history "
            f"(best fuzzy match={best_ratio:.2f})"
        )

    # Guard 2: candidate and match must share at least one distinctive token.
    candidate_tokens = _distinctive_tokens(candidate_headline)
    matched_tokens = _distinctive_tokens(matched_headline)
    if not (candidate_tokens & matched_tokens):
        return False, (
            "candidate and matched_headline share no distinctive tokens"
        )

    return True, ""


def apply_history_dedup_verdicts(
    items: list[dict],
    verdicts: list[dict],
    recent_history: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Split items into kept vs. dropped based on the agent's verdicts.

    Args:
        items: Today's candidate items (same list that was sent to the
            agent as items_json).
        verdicts: The `verdicts` list from `run_history_dedup`'s result
            dict. Each verdict carries `id` (index into items),
            `is_repeat`, and audit fields.
        recent_history: The list that was shown to the judge as
            `recent_history`, each entry with `headline` + `brief_date`.
            When provided, enables a coherence check that rejects drops
            where the judge's `matched_headline` does not actually exist
            in the inputs or shares no distinctive tokens with the
            candidate (guards against hallucinated cites — see 2026-04-20
            "Olly Robbins → White House Mythos" incident). When None,
            behavior is identical to pre-guardrail versions.

    Returns:
        `(kept_items, dropped_rows)` where:
          - `kept_items` is the subset of `items` the agent did NOT
            flag as repeats, preserving original order.
          - `dropped_rows` is a list of records shaped for the
            `dropped_items` table (same shape as
            `flag_previous_brief_overlaps` emits), carrying the source
            + URL for admin /admin/drops visibility.

    Defensively skips verdicts with out-of-range ids or missing fields
    rather than raising — the orchestrator fail-opens on error.
    """
    if not items or not verdicts:
        return list(items), []

    drop_by_idx: dict[int, dict] = {}
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        if not verdict.get("is_repeat"):
            continue
        idx = verdict.get("id")
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            logger.warning(
                "History dedup: verdict id %r is out of range (items=%d) — ignored",
                idx,
                len(items),
            )
            continue
        candidate_headline = items[idx].get("headline", "") if idx < len(items) else ""
        matched_headline = verdict.get("matched_headline") or ""
        passed, fail_reason = _coherence_check_passes(
            candidate_headline, matched_headline, recent_history
        )
        if not passed:
            logger.info(
                "History dedup: REJECTED drop of '%s' — %s (claimed match: '%s')",
                candidate_headline[:60],
                fail_reason,
                matched_headline[:60],
            )
            continue
        # If the agent emits two verdicts for the same id (shouldn't
        # happen, but be tolerant), keep the first.
        drop_by_idx.setdefault(idx, verdict)

    if not drop_by_idx:
        return list(items), []

    kept: list[dict] = []
    dropped_rows: list[dict] = []

    for idx, item in enumerate(items):
        verdict = drop_by_idx.get(idx)
        if verdict is None:
            kept.append(item)
            continue

        matched_headline = verdict.get("matched_headline") or ""
        matched_brief_date = verdict.get("matched_brief_date") or ""
        reason = verdict.get("reason") or "flagged as repeat by history dedup agent"

        # Drop-reason format mirrors `flag_previous_brief_overlaps` for
        # consistency on /admin/drops, but with a distinct prefix so the
        # two stages can be audited separately.
        if matched_headline and matched_brief_date:
            drop_reason = (
                f'{DROP_REASON_PREFIX} — matches "{matched_headline}" '
                f"from {matched_brief_date} ({reason})"
            )
        elif matched_headline:
            drop_reason = (
                f'{DROP_REASON_PREFIX} — matches "{matched_headline}" ({reason})'
            )
        else:
            drop_reason = f"{DROP_REASON_PREFIX} — {reason}"

        dropped_rows.append({
            "headline": item.get("headline", ""),
            "composite_score": item.get("composite_score"),
            "source": item.get("source") or item.get("source_name"),
            "source_url": item.get("source_url"),
            "drop_reason": drop_reason,
            "_matched_brief_date": matched_brief_date or None,
            "_matched_headline": matched_headline or None,
        })

        logger.info(
            "%s HARD DROP: '%s' ↔ '%s' (%s)",
            DROP_REASON_PREFIX,
            str(item.get("headline", ""))[:60],
            matched_headline[:60],
            matched_brief_date or "no-date",
        )

    return kept, dropped_rows
