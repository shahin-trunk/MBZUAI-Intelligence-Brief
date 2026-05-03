"""Deterministic post-agent exhibit formatter.

Runs after the Ghostwriter / model-release agent returns. Cleans up
exhibit data so it renders well in narrow card columns regardless of
what the LLM produced. Same philosophy as ghostwriter_validate.py:
the LLM produces whatever it wants; code makes it display-safe.

Handles all four exhibit types: benchmark_table, comparison_table,
metric_highlight, timeline.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Benchmark name abbreviations
# ---------------------------------------------------------------------------

# Known benchmark families → short display name. Checked case-insensitively.
# Add entries as new benchmarks appear in production output.
BENCHMARK_ABBREVS: dict[str, str] = {
    "humanity's last exam": "HLE",
    "humanitys last exam": "HLE",
    "hle": "HLE",
    "arc-agi-2": "ARC-AGI-2",
    "arc agi 2": "ARC-AGI-2",
    "arc-agi": "ARC-AGI",
    "gpqa diamond": "GPQA Diamond",
    "gpqa": "GPQA",
    "swe-bench verified": "SWE-bench Verified",
    "swe-bench": "SWE-bench",
    "swe bench": "SWE-bench",
    "sweagent bench": "SWE-agent",
    "terminal-bench 2.0": "Terminal-Bench 2.0",
    "terminal-bench hard": "Terminal-Bench Hard",
    "terminal bench": "Terminal-Bench",
    "mmlu": "MMLU",
    "mmlu-pro": "MMLU-Pro",
    "math-500": "MATH-500",
    "math 500": "MATH-500",
    "humaneval": "HumanEval",
    "human eval": "HumanEval",
    "code arena": "Code Arena",
    "livecodebench": "LiveCodeBench",
    "live code bench": "LiveCodeBench",
    "artificial analysis intelligence index": "AA Intelligence",
    "artificial analysis intelligence": "AA Intelligence",
    "artificial analysis": "AA Intelligence",
    "aime 2025": "AIME 2025",
    "aime 2024": "AIME 2024",
    "pinchbench": "PinchBench",
    "simpleqa": "SimpleQA",
    "simple qa": "SimpleQA",
    "codeforces": "Codeforces",
    "chatbot arena": "Chatbot Arena",
    "lmsys arena": "LMSYS Arena",
    "arena elo": "Arena Elo",
    "mt-bench": "MT-Bench",
    "ifeval": "IFEval",
    "hellaswag": "HellaSwag",
    "winogrande": "WinoGrande",
    "bigbench hard": "BBH",
    "big bench hard": "BBH",
    "drop": "DROP",
    "triviaqa": "TriviaQA",
    "natural questions": "NQ",
}

MAX_BENCHMARK_NAME_CHARS = 30
MAX_COLUMN_HEADERS = 6
MAX_CELL_CHARS = 20
MAX_METRIC_LABEL_CHARS = 18
MAX_METRIC_VALUE_CHARS = 15
MAX_TIMELINE_DESC_CHARS = 80


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _abbreviate_benchmark(name: str) -> str:
    """Shorten a benchmark name using the lookup table + heuristics."""
    if not name:
        return name

    # Extract condition in parentheses at the end: "HLE (no tools)"
    condition = ""
    paren_match = re.search(r"\(([^)]+)\)\s*$", name)
    if paren_match:
        condition = paren_match.group(0).strip()
        base = name[: paren_match.start()].strip()
    else:
        base = name.strip()

    # Strip common noise patterns
    # "Humanity's Last Exam - Academic reasoning (full set, text + MM) - No tools"
    # → split on " - " and take only the first segment as the base name
    if " - " in base:
        segments = [s.strip() for s in base.split(" - ")]
        base = segments[0]
        # If there's a short condition-like segment at the end, capture it.
        # Only match segments that ARE conditions (≤30 chars, contain
        # known condition keywords). Skip long descriptive segments
        # like "Academic reasoning (full set, text + MM)".
        for seg in segments[1:]:
            seg_lower = seg.lower().strip()
            if len(seg_lower) > 30:
                continue  # too long to be a condition
            if any(
                kw in seg_lower
                for kw in (
                    "no tool", "with tool", "search", "code",
                    "verified", "hard", "lite", "harness",
                )
            ):
                if not condition:
                    condition = f"({seg.strip()})"

    # Try lookup table (case-insensitive)
    base_lower = base.lower().strip()
    # Try exact match first
    if base_lower in BENCHMARK_ABBREVS:
        short = BENCHMARK_ABBREVS[base_lower]
        return f"{short} {condition}".strip() if condition else short

    # Try without possessives and special chars
    base_clean = re.sub(r"[''`]s?\b", "", base_lower).strip()
    if base_clean in BENCHMARK_ABBREVS:
        short = BENCHMARK_ABBREVS[base_clean]
        return f"{short} {condition}".strip() if condition else short

    # No match — truncate if needed
    result = f"{base} {condition}".strip() if condition else base
    if len(result) > MAX_BENCHMARK_NAME_CHARS:
        result = result[: MAX_BENCHMARK_NAME_CHARS - 1].rstrip() + "…"
    return result


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, breaking at word boundary."""
    if not text or len(text) <= max_chars:
        return text or ""
    cut = text[: max_chars - 1].rstrip()
    # Try to break at last space
    last_space = cut.rfind(" ")
    if last_space > max_chars // 2:
        cut = cut[:last_space]
    return cut + "…"


def _clean_cell(value: str) -> str:
    """Clean a table cell value: keep numbers/percentages/dashes only."""
    if not value:
        return "—"
    v = str(value).strip()
    if not v or v in ("", "null", "None", "N/A", "n/a"):
        return "—"
    # Already a clean score: number, percentage, dash, fraction
    if re.match(r"^[\d.,]+%?$|^—$|^[\d.]+/[\d.]+$|^[<>~≈]?[\d.,]+", v):
        return _truncate(v, MAX_CELL_CHARS)
    # Has a number somewhere — extract it
    num_match = re.search(r"[\d.,]+%?", v)
    if num_match and len(v) > MAX_CELL_CHARS:
        return num_match.group(0)
    return _truncate(v, MAX_CELL_CHARS)


def _shorten_model_name(name: str) -> str:
    """Shorten a model column header for display."""
    if not name or len(name) <= 20:
        return name or ""
    # Drop common suffixes that add noise in a comparison context
    for suffix in (" Thinking (High)", " Thinking (Max)", " Thinking (xhigh)",
                    " (High)", " (Max)", " (xhigh)", " Preview"):
        if name.endswith(suffix) and len(name) - len(suffix) >= 4:
            name = name[: -len(suffix)]
            break
    return _truncate(name, 22)


# ---------------------------------------------------------------------------
# Per-exhibit-type formatters
# ---------------------------------------------------------------------------


def _format_benchmark_table(exhibit: dict) -> dict:
    """Clean up a benchmark_table exhibit for card display."""
    data = exhibit.get("data") or exhibit
    models = data.get("models") or []
    rows = data.get("rows") or []

    # Shorten model names
    models = [_shorten_model_name(m) for m in models]

    # Cap columns
    if len(models) > MAX_COLUMN_HEADERS:
        # Keep first (released model) + strongest comparators
        models = models[:MAX_COLUMN_HEADERS]
        for row in rows:
            scores = row.get("scores") or []
            row["scores"] = scores[:MAX_COLUMN_HEADERS]

    # Abbreviate benchmark names and clean cells
    for row in rows:
        row["benchmark"] = _abbreviate_benchmark(row.get("benchmark", ""))
        row["scores"] = [_clean_cell(s) for s in (row.get("scores") or [])]
        # Pad if scores list is shorter than models list
        while len(row["scores"]) < len(models):
            row["scores"].append("—")

    # Truncate summary
    summary = data.get("summary") or ""
    if len(summary) > 200:
        summary = _truncate(summary, 200)

    data["models"] = models
    data["rows"] = rows
    if summary:
        data["summary"] = summary

    return exhibit


def _format_comparison_table(exhibit: dict) -> dict:
    """Clean up a comparison_table exhibit for card display."""
    data = exhibit.get("data") or exhibit
    columns = data.get("columns") or []
    rows = data.get("rows") or []

    # Truncate column headers
    data["columns"] = [_truncate(c, 20) for c in columns]

    # Clean cell values
    for row in rows:
        if isinstance(row, dict):
            for key in row:
                if isinstance(row[key], str):
                    row[key] = _truncate(row[key], 30)

    return exhibit


def _format_metric_highlight(exhibit: dict) -> dict:
    """Clean up a metric_highlight exhibit for card display."""
    data = exhibit.get("data") or exhibit
    metrics = data.get("metrics") or []

    for metric in metrics:
        if metric.get("label"):
            metric["label"] = _truncate(metric["label"], MAX_METRIC_LABEL_CHARS)
        if metric.get("value"):
            metric["value"] = _truncate(str(metric["value"]), MAX_METRIC_VALUE_CHARS)

    return exhibit


def _format_timeline(exhibit: dict) -> dict:
    """Clean up a timeline exhibit for card display."""
    data = exhibit.get("data") or exhibit
    events = data.get("events") or []

    for event in events:
        if event.get("description"):
            event["description"] = _truncate(
                event["description"], MAX_TIMELINE_DESC_CHARS
            )

    return exhibit


# ---------------------------------------------------------------------------
# Per-exhibit-type formatters for model_release_data
# ---------------------------------------------------------------------------


def format_model_release_data(mrd: dict) -> dict:
    """Clean up model_release_data fields for card display."""
    if not mrd:
        return mrd

    # Key numbers
    for kn in mrd.get("key_numbers") or []:
        if kn.get("label"):
            kn["label"] = _truncate(kn["label"], MAX_METRIC_LABEL_CHARS)
        if kn.get("value"):
            kn["value"] = _truncate(str(kn["value"]), MAX_METRIC_VALUE_CHARS)

    # Benchmarks (uses the same logic as benchmark_table exhibits)
    benchmarks = mrd.get("benchmarks")
    if benchmarks:
        _format_benchmark_table({"data": benchmarks})

    # Summary pitch
    pitch = mrd.get("summary_pitch") or ""
    if len(pitch) > 150:
        mrd["summary_pitch"] = _truncate(pitch, 150)

    return mrd


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_FORMATTERS = {
    "benchmark_table": _format_benchmark_table,
    "comparison_table": _format_comparison_table,
    "metric_highlight": _format_metric_highlight,
    "timeline": _format_timeline,
}


def format_exhibits(items: list[dict]) -> list[dict]:
    """Run all exhibit formatters on a list of Ghostwriter output items.

    Modifies items in place and returns the same list. Safe to call on
    items with no exhibits (no-op).
    """
    formatted_count = 0
    for item in items:
        # Format standalone exhibits
        exhibits = item.get("exhibits") or []
        for exhibit in exhibits:
            exhibit_type = exhibit.get("type") or ""
            formatter = _FORMATTERS.get(exhibit_type)
            if formatter:
                formatter(exhibit)
                formatted_count += 1

        # Format model_release_data (has its own benchmarks/key_numbers)
        mrd = item.get("model_release_data")
        if mrd and isinstance(mrd, dict):
            format_model_release_data(mrd)
            formatted_count += 1

    if formatted_count:
        logger.info("exhibit_formatter: formatted %d exhibit(s)", formatted_count)

    return items
