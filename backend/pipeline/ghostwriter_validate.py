"""Post-agent deterministic validators for Ghostwriter output.

These checks run in code *after* the Ghostwriter (or model-release
agent) returns, replacing rules that previously lived in the prompt.
Moving enforcement from the prompt into code means:

* the prompt stays short and focused on voice + contracts;
* detection is deterministic (a regex/len check, not a model hope);
* we don't prime the model by naming the tics we're trying to ban
  (the "priming effect" called out in Anthropic's Claude 4.6 guidance).

The canonical ``BANNED_PHRASES`` list lives here. The eval harness
imports from this module so the two stay in sync automatically.

Violations are surfaced three different ways depending on severity:

+----------------------------+--------+-----------------------+
| Check                      | Level  | Action                |
+----------------------------+--------+-----------------------+
| Banned phrases             | hard   | Trigger 1 voice retry |
| ID contract mismatch       | hard   | Already handled by    |
|                            |        | run_card_batch        |
| Sentence >25 words         | soft   | Log only              |
| Word budget overshoot      | soft   | Log only              |
+----------------------------+--------+-----------------------+

Only hard-fails drive a retry. Soft checks are eval signal.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical banned-phrase list.
#
# Reader of last resort: backend/evals/eval_ghostwriter_ab.py imports
# BANNED_PHRASES from this module. Keep the list here, not there.
#
# Each entry is a Python regex (re.IGNORECASE). Add an entry only when a
# voice tic has been observed in production output AND cannot be
# suppressed by positive voice examples in the prompt alone.
# ---------------------------------------------------------------------------
BANNED_PHRASES: list[str] = [
    # Analyst-thesaurus abstractions
    r"\brisk calculus\b",
    r"\bstrategic posture\b",
    r"\bstrategic envelope\b",
    r"\bdirectional shift\b",
    r"\brecalibration\b",
    r"\bconvergence point\b",
    r"\badjacent but distinct\b",
    r"\bmaterially shifts\b",
    r"\bconstitutes? a differentiated offer\b",
    r"\bmechanism for converting [A-Za-z ]+ into\b",
    r"\bstructurally (critical|important|significant)\b",
    r"\bthe gap between .+ is narrowing\b",
    # House-style tic that recurred across briefs
    r"compute sovereignty is the successor to oil sovereignty",
    # Reader-institution flattery (MBZUAI specifically)
    r"\btalent pipeline anchor\b",
    # Meta-editorial instructions to the reader about the brief itself
    r"\bflagged for follow[- ]up\b",
    # Second-person advice dressed as third-person analysis
    r"\brecruitment window\b",
    r"\bFor (Gulf|UAE|university|MBZUAI)[^\.]*this [a-z ]+ represents\b",
    # Meta-sourcing: outlet attribution is already rendered as a UI chip
    # (source_name / source_url / additional_sources). Patterns enumerate
    # outlet names rather than matching any proper noun, to avoid false
    # positives on legitimate phrases like "according to the filing" or
    # speaker attribution ("ASML CEO ... said").
    r"\bthe\s+story\s+was\s+reported\b",
    r"\b(Reuters|Bloomberg|TechCrunch|The\s+Information|WSJ|FT|Axios|The\s+Wall\s+Street\s+Journal|The\s+Financial\s+Times|The\s+New\s+York\s+Times|The\s+Washington\s+Post|The\s+Economist|TLDR\s+AI)\s+(first\s+)?reported\b",
    r"\bfirst\s+reported\s+by\s+(The\s+)?[A-Z]",
    r"\bcorroborated\s+by\s+(The\s+)?[A-Z]",
    r"\baccording\s+to\s+(The\s+)?(Reuters|Bloomberg|TechCrunch|The\s+Information|WSJ|FT|Axios|The\s+Wall\s+Street\s+Journal|The\s+Financial\s+Times|The\s+New\s+York\s+Times|The\s+Washington\s+Post|The\s+Economist|TLDR\s+AI)\b",
    r"\bper\s+(The\s+)?(Reuters|Bloomberg|TechCrunch|The\s+Information|WSJ|FT|Axios|The\s+Wall\s+Street\s+Journal|The\s+Financial\s+Times|TLDR\s+AI)\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in BANNED_PHRASES]

# Per-sentence word cap. Anything over this is a soft violation (logged,
# not retried). Matches the voice guidance in the Ghostwriter prompt —
# v4 analysis bullets are single sentences of 30–45 words, so the cap
# sits at 50 to leave slack without masking genuine run-ons.
MAX_SENTENCE_WORDS = 50

# Word-budget table (matches the prompt's depth → budget contract).
# v4 emits 3 telegraphic key_bullets + 2 dense sentence-bullets capped
# at ≤110 words total; all cards set depth="standard", so the
# "standard" value is the one that matters for the main Ghostwriter.
# Model-release cards keep the same prose budget and vary depth only
# to control richness of `model_release_data` (the validator's prose
# scan does not count structured data).
DEPTH_BUDGETS = {"full": 110, "standard": 110, "brief": 80}


# ---------------------------------------------------------------------------
# Per-item scanners
# ---------------------------------------------------------------------------


def _item_prose_fields(item: dict) -> list[str]:
    """Return the text fields on a card item we scan for voice violations.

    We scan the analysis and key bullets. Headlines are enforced by the
    Editor; main_bullet/context/implication are returned empty under the
    current schema.
    """
    fields: list[str] = []
    analysis = item.get("analysis")
    if isinstance(analysis, str):
        fields.append(analysis)
    bullets = item.get("key_bullets") or []
    if isinstance(bullets, list):
        fields.extend(b for b in bullets if isinstance(b, str))
    return fields


def scan_item_for_banned_phrases(item: dict) -> list[str]:
    """Return the list of banned-phrase matches found in one item.

    Returns an empty list if clean. Each match is the literal surface
    form that was found — easier to feed back to the model in a retry
    note than the regex pattern that caught it.
    """
    hits: list[str] = []
    for field in _item_prose_fields(item):
        for rx in _COMPILED:
            for m in rx.finditer(field):
                hits.append(m.group(0))
    return hits


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


def count_sentence_length_overruns(item: dict, cap: int = MAX_SENTENCE_WORDS) -> int:
    """Count sentences over the word cap across all prose fields."""
    overruns = 0
    for field in _item_prose_fields(item):
        for sentence in _split_sentences(field):
            if len(sentence.split()) > cap:
                overruns += 1
    return overruns


def total_word_count(item: dict) -> int:
    total = 0
    for field in _item_prose_fields(item):
        total += len(field.split())
    return total


def budget_for(item: dict) -> int:
    depth = (item.get("depth") or "standard").strip()
    return DEPTH_BUDGETS.get(depth, DEPTH_BUDGETS["standard"])


# ---------------------------------------------------------------------------
# Batch-level validation + retry decision
# ---------------------------------------------------------------------------


@dataclass
class ValidationReport:
    """Summary of per-item validation results for one batch."""

    banned_hits_by_id: dict[str, list[str]]
    sentence_overruns_by_id: dict[str, int]
    budget_exceeded_ids: list[str]

    @property
    def needs_voice_retry(self) -> bool:
        """True iff any item has banned-phrase hits.

        Sentence-length and word-budget overshoots are soft — they go
        to logs, not to a retry.
        """
        return bool(self.banned_hits_by_id)


def validate_batch(items_by_id: dict[str, dict]) -> ValidationReport:
    """Run all post-agent deterministic checks on a batch of items."""
    banned_hits: dict[str, list[str]] = {}
    overruns: dict[str, int] = {}
    over_budget: list[str] = []

    for item_id, item in items_by_id.items():
        hits = scan_item_for_banned_phrases(item)
        if hits:
            banned_hits[item_id] = hits

        n = count_sentence_length_overruns(item)
        if n > 0:
            overruns[item_id] = n

        if total_word_count(item) > budget_for(item):
            over_budget.append(item_id)

    return ValidationReport(
        banned_hits_by_id=banned_hits,
        sentence_overruns_by_id=overruns,
        budget_exceeded_ids=over_budget,
    )


def build_voice_retry_suffix(banned_hits_by_id: dict[str, list[str]]) -> str:
    """Produce a targeted retry correction note.

    The note names the offending phrases and asks for a rewrite that
    preserves all facts. We name the phrases only once, in a retry
    context — not in the prompt body, so there's no standing priming
    effect on normal runs.
    """
    if not banned_hits_by_id:
        return ""

    # Deduplicate phrases within each item for a cleaner instruction.
    lines = []
    for item_id, hits in banned_hits_by_id.items():
        unique = sorted({h.lower() for h in hits})
        sample = ", ".join(f'"{h}"' for h in unique[:4])
        lines.append(f"  - {item_id}: remove {sample}")

    return (
        "\n\nVOICE RETRY:\n"
        "Your previous output used phrases that read like consulting-deck "
        "filler for this reader. Rewrite ONLY the following items, "
        "preserving every fact but avoiding the flagged expressions and "
        "any near-variants. Return valid JSON in the same shape as before.\n"
        + "\n".join(lines)
    )


def log_soft_violations(report: ValidationReport, batch_label: str = "main") -> None:
    """Emit warnings for sentence-length + word-budget overruns."""
    for item_id, n in report.sentence_overruns_by_id.items():
        logger.warning(
            "Ghostwriter %s: item %s has %d sentence(s) over %d words",
            batch_label, item_id, n, MAX_SENTENCE_WORDS,
        )
    for item_id in report.budget_exceeded_ids:
        logger.warning(
            "Ghostwriter %s: item %s exceeds its word budget",
            batch_label, item_id,
        )
