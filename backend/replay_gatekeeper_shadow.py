#!/usr/bin/env python3.11
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import anthropic


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import (  # noqa: E402
    ANTHROPIC_API_KEY,
    DELIVERY_FORMAT,
    OUTPUT_DIR,
    PROMPTS_DIR,
    USER_PROFILE,
)
from pipeline.gatekeeper import run_gatekeeper  # noqa: E402
from pipeline.orchestrator import (  # noqa: E402
    BRIEF_SECTIONS,
    GATEKEEPER_KEEP_FIELDS,
    _build_raw_content_lookup,
    apply_continuity_penalty,
    flag_previous_brief_overlaps,
    normalize_section_name,
    rejoin_raw_content,
)
from prompts.loader import extract_prompt_from_md  # noqa: E402


GST = ZoneInfo("Asia/Dubai")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the Gatekeeper stage for historical dates using current prompt/code, "
            "then compare the replay against saved gatekeeper artifacts."
        )
    )
    parser.add_argument(
        "--date",
        action="append",
        dest="dates",
        default=[],
        help="Replay a single YYYY-MM-DD date. Repeatable.",
    )
    parser.add_argument(
        "--dates",
        dest="date_csv",
        help="Comma-separated YYYY-MM-DD dates to replay.",
    )
    parser.add_argument(
        "--output",
        default="/tmp/gatekeeper_replay_report.json",
        help="Where to write the JSON replay report.",
    )
    parser.add_argument(
        "--max-previous-days",
        type=int,
        default=3,
        help="How many prior brief days to include in historical continuity context.",
    )
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Build the report inputs and baselines without calling Anthropic.",
    )
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> list[str]:
    dates = list(args.dates)
    if args.date_csv:
        dates.extend(
            part.strip()
            for part in args.date_csv.split(",")
            if part.strip()
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in dates:
        for part in str(raw).split(","):
            value = part.strip()
            if not value or value in seen:
                continue
            datetime.strptime(value, "%Y-%m-%d")
            normalized.append(value)
            seen.add(value)
    if not normalized:
        raise SystemExit("Provide at least one --date or --dates value.")
    return normalized


def historical_lookback_cutoff(target_date: date) -> date:
    if target_date.weekday() == 0:
        days_back = 3
    else:
        days_back = 1
    cutoff_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=GST)
    cutoff_dt = cutoff_dt.replace(hour=6) - timedelta(days=days_back)
    return cutoff_dt.date()


def historical_date_variable(target_date: date) -> str:
    if target_date.weekday() == 0:
        cutoff_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=GST).replace(
            hour=6
        ) - timedelta(days=3)
    else:
        cutoff_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=GST).replace(
            hour=6
        ) - timedelta(days=1)
    return cutoff_dt.strftime("%Y-%m-%d") + " 6:00am GST"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_report(output_path: Path, report: dict) -> None:
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def historical_brief_files(target_date_str: str) -> list[Path]:
    files = sorted(OUTPUT_DIR.glob("brief_*.json"), reverse=True)
    return [
        path
        for path in files
        if path.stem.replace("brief_", "") < target_date_str
    ]


def historical_previous_brief(target_date_str: str) -> str:
    for path in historical_brief_files(target_date_str):
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            continue
    return "No previous brief available. This is the first run."


def historical_previous_brief_headlines(
    target_date_str: str,
    max_days: int,
) -> str:
    all_headlines: list[dict] = []
    days_found = 0

    for path in historical_brief_files(target_date_str):
        if days_found >= max_days:
            break
        try:
            data = load_json(path)
        except Exception:
            continue
        brief_date = path.stem.replace("brief_", "")
        for item in data.get("items", []):
            if item.get("is_placeholder"):
                continue
            all_headlines.append(
                {
                    "brief_date": brief_date,
                    "headline": item.get("headline", ""),
                    "section": item.get("section", ""),
                    "entities": item.get("entities", []),
                    "main_bullet": item.get("main_bullet", ""),
                }
            )
        days_found += 1

    if not all_headlines:
        return "No previous brief available. This is the first run."
    return json.dumps(all_headlines, indent=2, ensure_ascii=False)


def build_gatekeeper_prompt(
    target_date_str: str,
    scout_output_json: str,
    max_previous_days: int,
) -> str:
    raw_md = (PROMPTS_DIR / "gatekeeper_prompt.md").read_text(encoding="utf-8")
    prompt_text = extract_prompt_from_md(raw_md)
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

    replacements = {
        "{date_variable}": historical_date_variable(target_date),
        "{lookback_cutoff}": str(historical_lookback_cutoff(target_date)),
        "{previous_brief_headlines}": historical_previous_brief_headlines(
            target_date_str,
            max_days=max_previous_days,
        ),
        "{scout_output}": scout_output_json,
        "{gatekeeper_output}": "",
        "{ghostwriter_output}": "",
        "{items_json}": "",
        "{user_profile}": USER_PROFILE,
        "{delivery_format}": DELIVERY_FORMAT,
        "{date}": target_date_str,
        "{previous_brief}": historical_previous_brief(target_date_str),
    }

    for placeholder, value in replacements.items():
        prompt_text = prompt_text.replace(placeholder, value)
    return prompt_text


@contextmanager
def patched_previous_brief_headlines(target_date_str: str, max_previous_days: int):
    import pipeline.orchestrator as orchestrator_module

    original = orchestrator_module.get_previous_brief_headlines
    orchestrator_module.get_previous_brief_headlines = (
        lambda max_days=3: historical_previous_brief_headlines(
            target_date_str,
            max_days=min(max_days, max_previous_days),
        )
    )
    try:
        yield
    finally:
        orchestrator_module.get_previous_brief_headlines = original


def normalize_headline(text: str) -> str:
    return " ".join((text or "").lower().split())


def selected_url_set(items: Iterable[dict]) -> set[str]:
    urls: set[str] = set()
    for item in items:
        url = str(item.get("source_url") or "").strip()
        if url:
            urls.add(url)
    return urls


def section_counts(items: list[dict], field: str) -> dict[str, int]:
    counts = {section: 0 for section in BRIEF_SECTIONS}
    for item in items:
        normalized = normalize_section_name(item.get(field))
        if normalized:
            counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def compare_replay(
    baseline_selected: list[dict],
    replay_selected: list[dict],
) -> dict:
    baseline_headlines = {normalize_headline(item.get("headline", "")) for item in baseline_selected}
    replay_headlines = {normalize_headline(item.get("headline", "")) for item in replay_selected}
    headline_overlap = sorted(baseline_headlines & replay_headlines)

    baseline_urls = selected_url_set(baseline_selected)
    replay_urls = selected_url_set(replay_selected)
    url_overlap = sorted(baseline_urls & replay_urls)

    return {
        "baseline_selected_count": len(baseline_selected),
        "replay_selected_count": len(replay_selected),
        "baseline_section_distribution": section_counts(baseline_selected, "brief_section"),
        "replay_section_distribution": section_counts(replay_selected, "brief_section"),
        "headline_overlap_count": len(headline_overlap),
        "headline_overlap_ratio": round(
            len(headline_overlap) / max(len(baseline_headlines), 1),
            3,
        ),
        "headline_overlap_examples": headline_overlap[:10],
        "source_url_overlap_count": len(url_overlap),
        "source_url_overlap_ratio": round(
            len(url_overlap) / max(len(baseline_urls), 1),
            3,
        ),
        "source_url_overlap_examples": url_overlap[:10],
        "top5_baseline": [item.get("headline", "") for item in baseline_selected[:5]],
        "top5_replay": [item.get("headline", "") for item in replay_selected[:5]],
    }


async def replay_date(
    client: anthropic.AsyncAnthropic | None,
    target_date_str: str,
    max_previous_days: int,
    skip_live: bool,
) -> dict:
    scout_path = OUTPUT_DIR / f"scout_output_{target_date_str}.json"
    baseline_path = OUTPUT_DIR / f"gatekeeper_output_{target_date_str}.json"
    if not scout_path.exists():
        raise FileNotFoundError(f"Missing scout artifact: {scout_path}")
    if not baseline_path.exists():
        raise FileNotFoundError(f"Missing baseline artifact: {baseline_path}")

    scout_items = copy.deepcopy(load_json(scout_path))
    baseline = load_json(baseline_path)

    with patched_previous_brief_headlines(target_date_str, max_previous_days):
        scout_items, previous_brief_drops, previous_brief_soft = flag_previous_brief_overlaps(
            scout_items
        )

    continuity_penalized = apply_continuity_penalty(scout_items)
    raw_content_lookup = _build_raw_content_lookup(scout_items)
    lightweight_items = [
        {key: value for key, value in item.items() if key in GATEKEEPER_KEEP_FIELDS}
        for item in scout_items
    ]

    report = {
        "date": target_date_str,
        "input_items": len(lightweight_items),
        "previous_brief_hard_drops": len(previous_brief_drops),
        "previous_brief_soft_flags": previous_brief_soft,
        "continuity_penalized": continuity_penalized,
        "baseline_selected_count": len(baseline.get("selected", [])),
        "baseline_drop_count": len(baseline.get("dropped", [])),
    }

    if skip_live:
        report["skipped_live_replay"] = True
        return report

    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY is required for live replays")

    prompt = build_gatekeeper_prompt(
        target_date_str,
        json.dumps(lightweight_items, indent=2, ensure_ascii=False),
        max_previous_days=max_previous_days,
    )
    replay_result, usage = await run_gatekeeper(client, prompt)
    replay_selected, rejoin_warnings = rejoin_raw_content(
        replay_result.get("selected", []),
        raw_content_lookup,
    )
    replay_result["selected"] = replay_selected

    replay_selected = sorted(
        replay_result.get("selected", []),
        key=lambda item: item.get("rank", 10**9),
    )
    baseline_selected = sorted(
        baseline.get("selected", []),
        key=lambda item: item.get("rank", 10**9),
    )

    report["usage"] = usage
    report["drop_count"] = len(replay_result.get("dropped", []))
    report["rejoin_warnings"] = rejoin_warnings
    report.update(compare_replay(baseline_selected, replay_selected))
    return report


async def main_async(args: argparse.Namespace) -> int:
    dates = resolve_dates(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = None
    if not args.skip_live:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    report = {
        "generated_at": datetime.now(GST).isoformat(timespec="seconds"),
        "dates": dates,
        "skip_live": args.skip_live,
        "results": [],
    }

    for target_date_str in dates:
        print(f"Replaying {target_date_str}...", flush=True)
        try:
            result = await replay_date(
                client=client,
                target_date_str=target_date_str,
                max_previous_days=args.max_previous_days,
                skip_live=args.skip_live,
            )
        except Exception as exc:
            result = {
                "date": target_date_str,
                "error": str(exc),
            }
        report["results"].append(result)
        save_report(output_path, report)
        print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    print(f"\nSaved replay report to {output_path}", flush=True)
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
