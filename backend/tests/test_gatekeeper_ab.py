"""
A/B test: compare old vs new gatekeeper prompt on cached pipeline inputs.

Runs both prompts against the same input and compares:
- Number of items selected
- Section distribution
- Which items differ (selected by one but not the other)
- Score distributions

Uses real cached scout_output from a recent pipeline run + Supabase
production data for the previous brief context.

Run:  cd backend && python3 tests/test_gatekeeper_ab.py
"""

import asyncio
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / "frontend" / ".env.local", override=True)
load_dotenv(_root / ".env", override=True)

import anthropic
from config import MODEL, OUTPUT_DIR
from prompts.loader import extract_prompt_from_md, load_prompt
from pipeline.json_utils import safe_parse_json

PROMPTS_DIR = _root / "prompts"


def load_prompt_variant(filename: str, scout_output: str = "", override_date: str = "") -> str:
    """Load a prompt file and apply the standard variable replacements.

    If override_date is set, use it instead of today's date so we can
    test against cached data from older runs without date-mismatch issues.
    """
    from config import (
        DELIVERY_FORMAT, USER_PROFILE,
        get_today_date, get_date_variable, get_lookback_cutoff_date,
        get_previous_brief, get_previous_brief_headlines,
    )
    raw_md = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    prompt_text = extract_prompt_from_md(raw_md)

    date_to_use = override_date or get_today_date()
    # Use the override date for lookback cutoff description too
    cutoff_str = get_lookback_cutoff_date().strftime("%Y-%m-%d %H:%M %Z")
    if override_date:
        cutoff_str = f"{override_date} 06:00 GST (approx)"

    replacements = {
        "{date_variable}": get_date_variable() if not override_date else f"{override_date} (test)",
        "{lookback_cutoff}": cutoff_str,
        "{previous_brief_headlines}": get_previous_brief_headlines(),
        "{scout_output}": scout_output,
        "{gatekeeper_output}": "",
        "{ghostwriter_output}": "",
        "{items_json}": "",
        "{user_profile}": USER_PROFILE,
        "{delivery_format}": DELIVERY_FORMAT,
        "{date}": date_to_use,
        "{previous_brief}": get_previous_brief(),
    }
    for placeholder, value in replacements.items():
        prompt_text = prompt_text.replace(placeholder, value)
    return prompt_text


async def run_gatekeeper_with_prompt(client, prompt_text: str) -> dict:
    """Run gatekeeper and return parsed result."""
    response = await client.messages.create(
        model=MODEL,
        max_tokens=32000,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=600,
    )
    text = response.content[0].text.strip()
    # Extract JSON
    fence_match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
    if fence_match:
        return safe_parse_json(fence_match.group(1)), response.usage
    obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if obj_match:
        return safe_parse_json(obj_match.group(1)), response.usage
    raise ValueError("No JSON found in response")


def compare_results(name_a, result_a, name_b, result_b):
    """Compare two gatekeeper results and print analysis."""
    sel_a = result_a.get("selected", [])
    sel_b = result_b.get("selected", [])

    headlines_a = {item.get("headline", "").strip().lower() for item in sel_a}
    headlines_b = {item.get("headline", "").strip().lower() for item in sel_b}

    only_a = headlines_a - headlines_b
    only_b = headlines_b - headlines_a
    common = headlines_a & headlines_b

    print(f"\n  {name_a}: {len(sel_a)} items selected")
    print(f"  {name_b}: {len(sel_b)} items selected")
    print(f"  Common: {len(common)}")
    print(f"  Only in {name_a}: {len(only_a)}")
    print(f"  Only in {name_b}: {len(only_b)}")

    # Section distribution
    for name, sel in [(name_a, sel_a), (name_b, sel_b)]:
        sections = {}
        for item in sel:
            sec = item.get("brief_section", "Unknown")
            sections[sec] = sections.get(sec, 0) + 1
        print(f"\n  {name} sections: {dict(sorted(sections.items()))}")

    # Score comparison
    scores_a = [item.get("composite_score", 0) for item in sel_a if item.get("composite_score")]
    scores_b = [item.get("composite_score", 0) for item in sel_b if item.get("composite_score")]
    if scores_a:
        print(f"\n  {name_a} scores: min={min(scores_a):.1f} avg={sum(scores_a)/len(scores_a):.1f} max={max(scores_a):.1f}")
    if scores_b:
        print(f"  {name_b} scores: min={min(scores_b):.1f} avg={sum(scores_b)/len(scores_b):.1f} max={max(scores_b):.1f}")

    # Show differing items
    if only_a:
        print(f"\n  Only in {name_a}:")
        for h in sorted(only_a):
            item = next((i for i in sel_a if i.get("headline", "").strip().lower() == h), {})
            print(f"    [{item.get('composite_score', '?')}] {item.get('headline', h)[:65]}")

    if only_b:
        print(f"\n  Only in {name_b}:")
        for h in sorted(only_b):
            item = next((i for i in sel_b if i.get("headline", "").strip().lower() == h), {})
            print(f"    [{item.get('composite_score', '?')}] {item.get('headline', h)[:65]}")

    return {
        "common": len(common),
        "only_a": len(only_a),
        "only_b": len(only_b),
        "total_a": len(sel_a),
        "total_b": len(sel_b),
    }


async def test_on_date(client, date: str):
    """Run A/B test on cached scout output for a given date."""
    # Try to load cached scout output
    scout_path = OUTPUT_DIR / f"scout_output_{date}.json"
    if not scout_path.exists():
        print(f"\n  Skipping {date}: no cached scout_output found")
        return None

    scout_items = json.loads(scout_path.read_text(encoding="utf-8"))
    # Strip raw_content for gatekeeper (same as pipeline does)
    KEEP = {"headline", "source", "source_url", "date", "date_evidence",
            "summary", "entities", "category", "significance",
            "also_covered_by", "source_scout", "_date_flag", "_verified_date",
            "uae_exposure", "_merged_from_scouts", "_previous_brief_overlap"}
    lightweight = [{k: v for k, v in item.items() if k in KEEP} for item in scout_items]

    # Cap at 50 items to keep within API timeout limits for testing.
    # Production runs handle 100+ items with longer timeouts.
    if len(lightweight) > 50:
        print(f"  Capping from {len(lightweight)} to 50 items for test speed")
        lightweight = lightweight[:50]

    scout_json = json.dumps(lightweight, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  Date: {date} — {len(lightweight)} items")
    print(f"{'='*60}")

    # Use the cached date as "today" so items aren't stale
    override_date = date

    # Run old prompt
    print(f"  Running v1 (old prompt, 585 lines)...")
    prompt_old = load_prompt_variant("gatekeeper_prompt_v1.md", scout_output=scout_json, override_date=override_date)
    result_old, usage_old = await run_gatekeeper_with_prompt(client, prompt_old)
    print(f"  v1 done: {usage_old.input_tokens} in / {usage_old.output_tokens} out")

    # Run new prompt
    print(f"  Running v2 (new prompt, 238 lines)...")
    prompt_new = load_prompt_variant("gatekeeper_prompt.md", scout_output=scout_json, override_date=override_date)
    result_new, usage_new = await run_gatekeeper_with_prompt(client, prompt_new)
    print(f"  v2 done: {usage_new.input_tokens} in / {usage_new.output_tokens} out")

    # Token savings
    saved = usage_old.input_tokens - usage_new.input_tokens
    pct = 100 * saved / usage_old.input_tokens if usage_old.input_tokens else 0
    print(f"\n  Token savings: {saved:,} input tokens ({pct:.0f}% reduction)")

    stats = compare_results("v1", result_old, "v2", result_new)

    # Check notable decisions
    for name, result in [("v1", result_old), ("v2", result_new)]:
        notable = result.get("brief_summary", {}).get("notable_decisions", "")
        if notable:
            print(f"\n  {name} notable: {notable[:200]}")

    return stats


async def main():
    client = anthropic.AsyncAnthropic()
    start = time.time()

    # Find available dates with cached scout output (post-content-filter).
    # Exclude scout_output_raw_* files — those are pre-filter and too large.
    available = sorted(
        [
            f.stem.replace("scout_output_", "")
            for f in OUTPUT_DIR.glob("scout_output_*.json")
            if "raw" not in f.stem
        ],
        reverse=True,
    )
    # Take the 2 most recent (each takes ~3 min for 2 Sonnet calls)
    test_dates = available[:2]
    print(f"Testing on dates: {test_dates}")

    all_stats = []
    for date in test_dates:
        stats = await test_on_date(client, date)
        if stats:
            all_stats.append(stats)

    # Summary
    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  SUMMARY ({elapsed:.0f}s)")
    print(f"{'='*60}")
    if all_stats:
        avg_common = sum(s["common"] for s in all_stats) / len(all_stats)
        avg_total_a = sum(s["total_a"] for s in all_stats) / len(all_stats)
        avg_total_b = sum(s["total_b"] for s in all_stats) / len(all_stats)
        print(f"  Avg items selected: v1={avg_total_a:.1f}, v2={avg_total_b:.1f}")
        print(f"  Avg overlap: {avg_common:.1f} items in common")
        overlap_pct = 100 * avg_common / max(avg_total_a, avg_total_b) if max(avg_total_a, avg_total_b) else 0
        print(f"  Agreement rate: {overlap_pct:.0f}%")


if __name__ == "__main__":
    asyncio.run(main())
