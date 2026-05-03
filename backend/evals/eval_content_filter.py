"""Evaluate the Haiku content filter by having Sonnet re-judge a sample.

Loads kept and dropped items from pipeline output files, samples from each
pool, asks Sonnet to independently classify NEWS vs NOT_NEWS using the same
criteria, and reports agreement/disagreement rates.

Usage:
    cd backend && python -m evals.eval_content_filter
    cd backend && python -m evals.eval_content_filter --dates 2026-03-10,2026-03-09
    cd backend && python -m evals.eval_content_filter --sample-size 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_project_env

load_project_env()

import anthropic

OUTPUT_DIR = BACKEND_DIR / "output"
PROMPTS_DIR = BACKEND_DIR.parent / "prompts"
SONNET_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _available_dates() -> list[str]:
    """Return sorted list of dates that have both content filter outputs."""
    cf_dates: set[str] = set()
    for p in OUTPUT_DIR.glob("content_filter_output_*.json"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        if m:
            cf_dates.add(m.group(1))

    drop_dates: set[str] = set()
    for p in OUTPUT_DIR.glob("dropped_by_content_filter_*.json"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        if m:
            drop_dates.add(m.group(1))

    raw_dates: set[str] = set()
    for p in OUTPUT_DIR.glob("scout_output_raw_*.json"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        if m:
            raw_dates.add(m.group(1))

    # Need all three files to evaluate a date
    common = cf_dates & drop_dates & raw_dates
    return sorted(common)


def _load_json(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_raw_items(date: str) -> list[dict]:
    """Load full scout items for a date (pre-content-filter)."""
    path = OUTPUT_DIR / f"scout_output_raw_{date}.json"
    if not path.exists():
        return []
    data = _load_json(path)
    return data if isinstance(data, list) else []


def _load_kept_items(date: str) -> list[dict]:
    """Load items Haiku marked as NEWS (keep=true) with their full text.

    Returns list of dicts with keys: headline, summary, source, date,
    haiku_verdict (NEWS), verdict_reason.
    """
    cf_path = OUTPUT_DIR / f"content_filter_output_{date}.json"
    if not cf_path.exists():
        return []
    cf_data = _load_json(cf_path)
    verdicts = cf_data.get("verdicts", [])

    raw_items = _load_raw_items(date)

    kept: list[dict] = []
    for v in verdicts:
        # Handle both verdict shapes (the content-filter prompt was rewritten
        # 2026-04-22 to emit `decision: "KEEP"/"DROP"`; the legacy prompt used
        # `keep: bool` or `verdict: "NEWS"/"NOT_NEWS"`).
        decision = v.get("decision")
        if decision == "DROP":
            continue
        if decision != "KEEP" and not v.get("keep") and v.get("verdict") != "NEWS":
            continue
        idx = v.get("id") if v.get("id") is not None else v.get("index")
        if idx is None:
            continue

        # Look up full item from raw scout output by index
        full_item = raw_items[idx] if idx < len(raw_items) else {}

        kept.append({
            "headline": v.get("headline", full_item.get("headline", "")),
            "summary": full_item.get("summary", ""),
            "source": full_item.get("source", ""),
            "date": full_item.get("date", ""),
            "haiku_verdict": "NEWS",
            "verdict_reason": v.get("reason", ""),
            "eval_date": date,
        })
    return kept


def _load_dropped_items(date: str) -> list[dict]:
    """Load items Haiku marked as NOT_NEWS with their full text.

    Returns list of dicts matching the same schema as _load_kept_items.
    """
    drop_path = OUTPUT_DIR / f"dropped_by_content_filter_{date}.json"
    if not drop_path.exists():
        return []
    drop_data = _load_json(drop_path)
    dropped_entries = drop_data.get("dropped", [])

    # The dropped file only has headline + drop_reason. We need to match
    # back to raw items by headline to get summary text.
    raw_items = _load_raw_items(date)
    raw_by_headline: dict[str, dict] = {}
    for item in raw_items:
        hl = item.get("headline", "")
        if hl:
            raw_by_headline[hl] = item

    result: list[dict] = []
    for entry in dropped_entries:
        hl = entry.get("headline", "")
        full_item = raw_by_headline.get(hl, {})
        result.append({
            "headline": hl,
            "summary": full_item.get("summary", ""),
            "source": full_item.get("source", ""),
            "date": full_item.get("date", ""),
            "haiku_verdict": "NOT_NEWS",
            "verdict_reason": entry.get("drop_reason", ""),
            "eval_date": date,
        })
    return result


# ---------------------------------------------------------------------------
# Sonnet judge
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = """\
You are evaluating whether a news item describes a concrete event (NEWS) \
or is opinion/analysis/preview/characterization (NOT_NEWS).

Apply these rules strictly:

NEWS (pass) if the item describes: a meeting, announcement, launch, deal, \
appointment, policy change, product release, funding round, signing, \
enforcement action, disclosed result, or measurable development.

NOT_NEWS (fail) if the item is:
- Opinion / analysis / commentary
- Executive characterization of market conditions (not announcing an action)
- Forward-looking preview (event not yet produced results)
- Professional services publication (law firm guide, whitepaper)
- Roundup / survey / compilation of older events
- Reputational / characterization by third party
- Duplicate (another item covers the same event better)

A trivial news item is still NEWS. A fascinating opinion piece is still NOT_NEWS.

Ask: "What specific thing happened?" If you can answer with a concrete \
action/event/decision, it is NEWS. If you can only answer with a description \
or expectation, it is NOT_NEWS.

Respond with ONLY a JSON object:
{"verdict": "NEWS" or "NOT_NEWS", "reason": "brief explanation"}
"""


async def _judge_item(
    client: anthropic.AsyncAnthropic,
    item: dict,
    semaphore: asyncio.Semaphore,
) -> str:
    """Ask Sonnet to judge a single item. Returns 'NEWS' or 'NOT_NEWS'."""
    user_msg = (
        f"Headline: {item['headline']}\n"
        f"Source: {item['source']}\n"
        f"Date: {item['date']}\n"
        f"Summary: {item['summary']}"
    )

    async with semaphore:
        response = await client.messages.create(
            model=SONNET_MODEL,
            max_tokens=256,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )

    text = response.content[0].text if response.content else ""
    # Extract verdict from JSON response
    try:
        m = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            return result.get("verdict", "UNKNOWN")
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: look for NEWS or NOT_NEWS in raw text
    if "NOT_NEWS" in text:
        return "NOT_NEWS"
    if "NEWS" in text:
        return "NEWS"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

async def run_eval(dates: list[str], sample_size: int) -> None:
    client = anthropic.AsyncAnthropic()
    semaphore = asyncio.Semaphore(10)  # limit concurrency

    # Collect items across all dates
    all_kept: list[dict] = []
    all_dropped: list[dict] = []

    for date in dates:
        kept = _load_kept_items(date)
        dropped = _load_dropped_items(date)
        all_kept.extend(kept)
        all_dropped.extend(dropped)
        print(f"  {date}: {len(kept)} kept, {len(dropped)} dropped")

    print(f"\nTotal pool: {len(all_kept)} kept (NEWS), "
          f"{len(all_dropped)} dropped (NOT_NEWS)")

    # Sample
    kept_sample = random.sample(all_kept, min(sample_size, len(all_kept)))
    dropped_sample = random.sample(all_dropped, min(sample_size, len(all_dropped)))

    print(f"Sampled: {len(kept_sample)} from kept, "
          f"{len(dropped_sample)} from dropped\n")

    # Judge all sampled items concurrently
    all_items = kept_sample + dropped_sample
    print(f"Sending {len(all_items)} items to Sonnet for re-judging...")

    tasks = [_judge_item(client, item, semaphore) for item in all_items]
    sonnet_verdicts = await asyncio.gather(*tasks)

    # Analyze results
    false_positives: list[dict] = []   # Haiku=NOT_NEWS, Sonnet=NEWS
    false_negatives: list[dict] = []   # Haiku=NEWS, Sonnet=NOT_NEWS
    agreements = 0
    unknown_count = 0

    for item, sonnet_verdict in zip(all_items, sonnet_verdicts):
        haiku = item["haiku_verdict"]

        if sonnet_verdict == "UNKNOWN":
            unknown_count += 1
            continue

        if haiku == sonnet_verdict:
            agreements += 1
        elif haiku == "NOT_NEWS" and sonnet_verdict == "NEWS":
            false_positives.append({
                "headline": item["headline"],
                "source": item["source"],
                "date": item["eval_date"],
                "haiku_reason": item["verdict_reason"],
            })
        elif haiku == "NEWS" and sonnet_verdict == "NOT_NEWS":
            false_negatives.append({
                "headline": item["headline"],
                "source": item["source"],
                "date": item["eval_date"],
            })

    # Report
    total_judged = agreements + len(false_positives) + len(false_negatives)
    dropped_judged = len(dropped_sample) - sum(
        1 for item, v in zip(all_items[:len(dropped_sample)], sonnet_verdicts[:len(dropped_sample)])
        if v == "UNKNOWN"
    )
    kept_judged = len(kept_sample) - sum(
        1 for item, v in zip(all_items[len(kept_sample):], sonnet_verdicts[len(kept_sample):])
        if v == "UNKNOWN"
    )

    print("\n" + "=" * 70)
    print("CONTENT FILTER EVAL REPORT")
    print("=" * 70)
    print(f"Dates evaluated:     {', '.join(dates)}")
    print(f"Items judged:        {total_judged} "
          f"({unknown_count} unknown/skipped)")
    print(f"Agreement rate:      {agreements}/{total_judged} "
          f"({agreements / total_judged * 100:.1f}%)" if total_judged else "N/A")
    print()

    fp_rate = len(false_positives) / dropped_judged * 100 if dropped_judged else 0
    fn_rate = len(false_negatives) / kept_judged * 100 if kept_judged else 0

    print(f"False positive rate: {len(false_positives)}/{dropped_judged} "
          f"({fp_rate:.1f}%)")
    print(f"  (Haiku said NOT_NEWS, Sonnet says NEWS = wrongly filtered out)")
    print()
    print(f"False negative rate: {len(false_negatives)}/{kept_judged} "
          f"({fn_rate:.1f}%)")
    print(f"  (Haiku said NEWS, Sonnet says NOT_NEWS = should have been filtered)")

    if false_positives:
        print(f"\n{'─' * 70}")
        print(f"FALSE POSITIVES ({len(false_positives)}) — items Haiku dropped "
              f"that Sonnet thinks are NEWS:")
        print(f"{'─' * 70}")
        for i, fp in enumerate(false_positives, 1):
            print(f"  {i}. [{fp['date']}] {fp['headline']}")
            print(f"     Source: {fp['source']}")
            print(f"     Haiku reason: {fp['haiku_reason']}")
            print()

    if false_negatives:
        print(f"{'─' * 70}")
        print(f"FALSE NEGATIVES ({len(false_negatives)}) — items Haiku kept "
              f"that Sonnet thinks are NOT_NEWS:")
        print(f"{'─' * 70}")
        for i, fn in enumerate(false_negatives, 1):
            print(f"  {i}. [{fn['date']}] {fn['headline']}")
            print(f"     Source: {fn['source']}")
            print()

    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate content filter accuracy (Haiku vs Sonnet)"
    )
    parser.add_argument(
        "--dates",
        type=str,
        default=None,
        help="Comma-separated dates (YYYY-MM-DD). Default: last 5 available.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=25,
        help="Number of items to sample per category (kept/dropped). Default: 25.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling. Default: 42.",
    )
    args = parser.parse_args()

    random.seed(args.seed)

    if args.dates:
        dates = [d.strip() for d in args.dates.split(",")]
    else:
        available = _available_dates()
        if not available:
            print("No evaluation data found in output/. "
                  "Run the pipeline first to generate content filter outputs.")
            sys.exit(1)
        dates = available[-5:]

    print(f"Content Filter Eval")
    print(f"Dates: {', '.join(dates)}")
    print(f"Sample size: {args.sample_size} per category")
    print(f"Seed: {args.seed}")
    print(f"Judge model: {SONNET_MODEL}")
    print()

    asyncio.run(run_eval(dates, args.sample_size))


if __name__ == "__main__":
    main()
