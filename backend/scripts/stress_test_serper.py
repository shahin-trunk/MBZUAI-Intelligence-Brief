"""Q2 from the Phase 1 plan: can Serper /scrape handle concurrency 10 and 15
without degrading success/latency?

Uses the same 10 domain-diverse URLs as compare_jina_serper.py but fires them
concurrently at different levels. Reports success rate, p50/p95/max latency.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

MAIN_REPO = Path("/Users/brayan.vahdat/Desktop/Intelligence Dashboard")
load_dotenv(MAIN_REPO / "frontend" / ".env.local")
load_dotenv(MAIN_REPO / ".env")

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
assert SERPER_API_KEY, "SERPER_API_KEY not set"

TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)

# Domain-diverse URLs from the compare script. Repeat 3x to create a pool
# of 30 for the parallelism test.
BASE_URLS = [
    "https://www.wam.ae/en/article/bzrg2hy-hamriyah-municipality-launches-model-community",
    "https://www.wam.ae/en/article/176celx-malaysia%E2%80%99s-halal-exports-hit-rm6852-2025-109",
    "https://www.mediaoffice.abudhabi/en/government/crown-prince-of-abu-dhabi/",
    "https://www.tii.ae/news",
    "https://khaznadatacenters.com/",
    "https://www.g42.ai/",
    "https://www.ku.ac.ae/",
    "https://www.presight.ai/",
    "https://www.gulftoday.ae/",
    "https://www.zawya.com/en",
]
URLS = BASE_URLS * 3  # 30 URLs


async def fetch_via_serper(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        start = time.monotonic()
        try:
            r = await client.post(
                "https://scrape.serper.dev",
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"url": url},
            )
            r.raise_for_status()
            data = r.json()
            text = data.get("text") or data.get("content") or data.get("markdown") or ""
            return {
                "url": url,
                "ok": bool(text.strip()),
                "elapsed_s": round(time.monotonic() - start, 2),
                "chars": len(text),
                "status": r.status_code,
            }
        except httpx.HTTPStatusError as e:
            return {
                "url": url,
                "ok": False,
                "elapsed_s": round(time.monotonic() - start, 2),
                "chars": 0,
                "status": e.response.status_code,
                "error": f"HTTP {e.response.status_code}",
            }
        except Exception as e:
            return {
                "url": url,
                "ok": False,
                "elapsed_s": round(time.monotonic() - start, 2),
                "chars": 0,
                "status": None,
                "error": type(e).__name__ + ": " + str(e)[:80],
            }


async def run_level(concurrency: int) -> dict:
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        wall_start = time.monotonic()
        results = await asyncio.gather(
            *(fetch_via_serper(client, u, sem) for u in URLS)
        )
        wall = time.monotonic() - wall_start
    latencies = [r["elapsed_s"] for r in results]
    ok = sum(1 for r in results if r["ok"])
    return {
        "concurrency": concurrency,
        "wall_seconds": round(wall, 2),
        "n_urls": len(URLS),
        "ok": ok,
        "fail": len(URLS) - ok,
        "p50": round(statistics.median(latencies), 2),
        "p95": round(sorted(latencies)[int(0.95 * len(latencies))], 2),
        "max": round(max(latencies), 2),
        "failures_by_status": {},
    }


async def main() -> None:
    print(f"Testing Serper /scrape with {len(URLS)} URLs at concurrency levels\n")
    rows = []
    for c in [5, 10, 15, 20]:
        print(f"--- concurrency={c} ---")
        row = await run_level(c)
        rows.append(row)
        print(json.dumps(row, indent=2))
        print()
        await asyncio.sleep(3)  # brief cool-down between runs

    print("=== Summary ===")
    print(f"{'conc':>6} {'wall(s)':>9} {'ok':>4} {'fail':>5} {'p50':>6} {'p95':>6} {'max':>6}")
    for r in rows:
        print(
            f"{r['concurrency']:>6} {r['wall_seconds']:>9} "
            f"{r['ok']:>4} {r['fail']:>5} {r['p50']:>6} {r['p95']:>6} {r['max']:>6}"
        )


if __name__ == "__main__":
    asyncio.run(main())
