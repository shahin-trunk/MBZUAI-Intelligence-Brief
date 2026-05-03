#!/usr/bin/env python3.11
"""Date filter eval.

Verifies whether the date filter is incorrectly dropping items that actually
have valid recent publication dates. Re-fetches source URLs from dropped items
and extracts their publication date using the same logic as date_verify.py.

Usage:
    cd backend && python -m evals.eval_date_filter
    cd backend && python -m evals.eval_date_filter --dates 2026-03-10,2026-03-09
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import OUTPUT_DIR  # noqa: E402
from pipeline.date_verify import (  # noqa: E402
    extract_date_from_html,
    FETCH_TIMEOUT,
    MAX_BYTES,
    MAX_CONCURRENT,
)

GST = ZoneInfo("Asia/Dubai")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify date filter isn't dropping items with valid recent dates.",
    )
    parser.add_argument(
        "--dates",
        default=None,
        help="Comma-separated YYYY-MM-DD dates. Default: 5 most recent with artifacts.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=3,
        help="Max age in days for a date to count as 'recent' relative to the brief date (default: 3).",
    )
    return parser.parse_args()


def find_recent_dates(n: int = 5) -> list[str]:
    """Find the N most recent dates with dropped_by_date artifacts."""
    files = sorted(OUTPUT_DIR.glob("dropped_by_date_*.json"), reverse=True)
    dates: list[str] = []
    for f in files:
        d = f.stem.replace("dropped_by_date_", "")
        dates.append(d)
        if len(dates) >= n:
            break
    return dates


async def fetch_and_extract_date(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
) -> tuple[str, date | None, str | None]:
    """Fetch a URL and extract its publication date.

    Returns (url, extracted_date_or_None, error_or_None).
    """
    if not url or not url.startswith("http"):
        return url, None, "invalid_url"

    async with semaphore:
        try:
            resp = await client.get(
                url,
                follow_redirects=True,
                timeout=FETCH_TIMEOUT,
            )
            if resp.status_code != 200:
                return url, None, f"http_{resp.status_code}"

            html = resp.text[:MAX_BYTES]
            d = extract_date_from_html(html)
            return url, d, None

        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as e:
            return url, None, type(e).__name__
        except Exception as e:
            return url, None, str(e)


async def verify_dropped_items(
    dropped_items: list[dict],
    brief_date: date,
    max_age_days: int,
) -> dict:
    """Re-verify dates for dropped items. Returns analysis dict."""
    items_with_urls = [
        item for item in dropped_items
        if (item.get("source_url") or "").startswith("http")
    ]

    if not items_with_urls:
        return {
            "total_dropped": len(dropped_items),
            "items_with_urls": 0,
            "items_verified": 0,
            "false_drops": [],
            "false_drop_count": 0,
            "false_drop_rate": 0.0,
        }

    # Deduplicate URLs
    url_to_items: dict[str, list[dict]] = {}
    for item in items_with_urls:
        url = item["source_url"].strip()
        url_to_items.setdefault(url, []).append(item)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        http2=False,
    ) as client:
        tasks = [
            fetch_and_extract_date(client, semaphore, url)
            for url in url_to_items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    cutoff_date = brief_date - timedelta(days=max_age_days)
    items_verified = 0
    false_drops: list[dict] = []

    for result in results:
        if isinstance(result, Exception):
            continue

        url, extracted_date, error = result
        if error or extracted_date is None:
            continue

        items_verified += 1

        # Check if the extracted date is recent enough
        if extracted_date >= cutoff_date:
            # This item was dropped but has a valid recent date -- false drop
            for item in url_to_items.get(url, []):
                false_drops.append({
                    "headline": item.get("headline", ""),
                    "source_url": url,
                    "verified_date": extracted_date.isoformat(),
                    "brief_date": brief_date.isoformat(),
                    "age_days": (brief_date - extracted_date).days,
                    "drop_reason": item.get("_drop_reason", item.get("reason", "unknown")),
                    "source": item.get("source", ""),
                })

    return {
        "total_dropped": len(dropped_items),
        "items_with_urls": len(items_with_urls),
        "urls_checked": len(url_to_items),
        "items_verified": items_verified,
        "false_drops": false_drops,
        "false_drop_count": len(false_drops),
        "false_drop_rate": round(len(false_drops) / max(len(items_with_urls), 1), 3),
    }


async def evaluate_date(date_str: str, max_age_days: int) -> dict:
    """Evaluate date filter accuracy for a single date."""
    path = OUTPUT_DIR / f"dropped_by_date_{date_str}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    dropped_items = data.get("dropped", [])
    cutoff = data.get("cutoff", "")
    brief_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    print(f"  Dropped items: {len(dropped_items)}, cutoff: {cutoff}")

    result = await verify_dropped_items(dropped_items, brief_date, max_age_days)
    result["date"] = date_str
    result["original_cutoff"] = cutoff
    return result


async def main() -> None:
    args = parse_args()

    if args.dates:
        dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    else:
        dates = find_recent_dates(5)

    if not dates:
        print("No dates found with dropped_by_date artifacts.")
        sys.exit(1)

    print(f"Date filter eval")
    print(f"Dates: {', '.join(dates)}")
    print(f"Max age threshold: {args.max_age_days} days")
    print("-" * 60)

    results: list[dict] = []
    for date_str in dates:
        print(f"\nEvaluating {date_str}...")
        try:
            result = await evaluate_date(date_str, args.max_age_days)
            results.append(result)
        except FileNotFoundError:
            print(f"  SKIP: dropped_by_date_{date_str}.json not found")
        except Exception as e:
            print(f"  ERROR: {e}")

    # Print report
    print("\n" + "=" * 60)
    print("DATE FILTER EVAL REPORT")
    print("=" * 60)

    total_dropped_all = 0
    total_false_all = 0
    total_verified_all = 0

    for r in results:
        print(f"\n--- {r['date']} ---")
        print(f"  Total dropped: {r['total_dropped']}")
        print(f"  Items with URLs: {r['items_with_urls']}")
        print(f"  URLs verified: {r['items_verified']}")
        print(f"  False drops: {r['false_drop_count']} "
              f"(rate: {r['false_drop_rate']:.1%})")

        total_dropped_all += r["total_dropped"]
        total_false_all += r["false_drop_count"]
        total_verified_all += r["items_verified"]

        if r["false_drops"]:
            print(f"  False drop details:")
            for fd in r["false_drops"]:
                print(f"    - [{fd['verified_date']}, age {fd['age_days']}d] "
                      f"{fd['headline'][:80]}")
                print(f"      URL: {fd['source_url'][:100]}")
                print(f"      Drop reason: {fd['drop_reason']}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"  Dates evaluated: {len(results)}")
    print(f"  Total items dropped across all dates: {total_dropped_all}")
    print(f"  Total URLs verified: {total_verified_all}")
    print(f"  Total false drops: {total_false_all}")
    overall_rate = total_false_all / max(total_verified_all, 1)
    print(f"  Overall false drop rate: {overall_rate:.1%}")
    if total_false_all > 0:
        print(f"  ACTION: Review date filter logic -- {total_false_all} items "
              f"with valid recent dates were incorrectly dropped.")
    else:
        print(f"  Date filter is working correctly -- no false drops detected.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
