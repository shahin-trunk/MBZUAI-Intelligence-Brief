"""Stress-test the enricher's URL-fetching layer at various concurrency levels.

Picks ~30 real URLs from today's scout output and times
`fetch_source_url` (trafilatura + Jina fallback, the same function the
Enricher calls) at concurrency 3, 8, 15, 20. Reports total wall-clock,
errors, and slow-URL outliers per run.

Pure I/O — no Anthropic API calls, no cost.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from pipeline.enricher import fetch_source_url  # noqa: E402


SCOUT_PATH = Path(
    "/Users/brayan.vahdat/Desktop/Intelligence Dashboard/backend/output/scout_output_2026-04-17.json"
)
N_URLS = 30
CONCURRENCY_LEVELS = [3, 8, 15, 20]


def load_urls(n: int) -> list[str]:
    """Pick domain-diverse URLs so Jina's per-domain rate limit doesn't skew
    the test. At most 2 URLs per domain."""
    from urllib.parse import urlparse

    items = json.loads(SCOUT_PATH.read_text())
    urls: list[str] = []
    seen_urls: set[str] = set()
    per_domain: dict[str, int] = {}
    for it in items:
        u = (it.get("source_url") or "").strip()
        if not u or u in seen_urls:
            continue
        domain = urlparse(u).netloc
        if per_domain.get(domain, 0) >= 2:
            continue
        seen_urls.add(u)
        per_domain[domain] = per_domain.get(domain, 0) + 1
        urls.append(u)
        if len(urls) >= n:
            break
    return urls


async def fetch_with_sem(
    url: str, sem: asyncio.Semaphore, results: list[tuple[str, float, bool]]
) -> None:
    async with sem:
        start = time.monotonic()
        ok = False
        try:
            out = await fetch_source_url(url)
            ok = bool(out and (out.get("text") or "").strip())
        except Exception:
            ok = False
        elapsed = time.monotonic() - start
        results.append((url, elapsed, ok))


async def run_level(urls: list[str], concurrency: int) -> dict:
    sem = asyncio.Semaphore(concurrency)
    results: list[tuple[str, float, bool]] = []
    wall_start = time.monotonic()
    await asyncio.gather(
        *(fetch_with_sem(u, sem, results) for u in urls)
    )
    wall = time.monotonic() - wall_start
    latencies = [r[1] for r in results]
    ok_count = sum(1 for r in results if r[2])
    return {
        "concurrency": concurrency,
        "wall_seconds": round(wall, 2),
        "n_urls": len(urls),
        "ok": ok_count,
        "fail": len(urls) - ok_count,
        "p50": round(statistics.median(latencies), 2),
        "p95": round(sorted(latencies)[int(0.95 * len(latencies))], 2),
        "max": round(max(latencies), 2),
        "slow_urls": [
            (u, round(t, 1)) for u, t, _ in sorted(results, key=lambda r: -r[1])[:3]
        ],
    }


async def main() -> None:
    urls = load_urls(N_URLS)
    print(f"Loaded {len(urls)} URLs\n")
    rows = []
    for c in CONCURRENCY_LEVELS:
        print(f"--- concurrency={c} ---")
        row = await run_level(urls, c)
        rows.append(row)
        print(json.dumps(row, indent=2))
        print()
        await asyncio.sleep(2)
    print("\n=== Summary ===")
    print(f"{'conc':>6} {'wall(s)':>9} {'ok':>4} {'fail':>5} {'p50':>6} {'p95':>6} {'max':>6}")
    for r in rows:
        print(
            f"{r['concurrency']:>6} {r['wall_seconds']:>9} "
            f"{r['ok']:>4} {r['fail']:>5} {r['p50']:>6} {r['p95']:>6} {r['max']:>6}"
        )


if __name__ == "__main__":
    asyncio.run(main())
