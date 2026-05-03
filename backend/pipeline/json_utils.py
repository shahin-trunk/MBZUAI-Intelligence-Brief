"""Shared JSON parsing utilities for LLM output."""

from __future__ import annotations

import json
import logging

from json_repair import repair_json

logger = logging.getLogger(__name__)


def safe_parse_json(raw_text: str) -> dict | list:
    """Parse JSON from LLM output, repairing minor formatting issues.

    Strips markdown fences, then tries json.loads(). On failure,
    uses json-repair to fix trailing commas, unescaped quotes,
    unclosed brackets, etc.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        repaired = repair_json(text)
        size_delta = len(repaired) - len(text)
        # Warn whenever repair runs — Claude returned malformed JSON, which can
        # mean truncation (max_tokens cutoff) and silent fabrication of fields
        # by json_repair. The first 200 chars + the parser error help diagnose.
        logger.warning(
            "JSON repair applied (orig=%d chars, repaired=%d chars, delta=%+d) "
            "— parser error: %s — head: %r",
            len(text),
            len(repaired),
            size_delta,
            exc,
            text[:200],
        )
        return json.loads(repaired)
