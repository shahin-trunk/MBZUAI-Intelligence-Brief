"""Side-by-side comparison: Jina vs Serper /scrape on real URLs.

Picks a domain-diverse set of 10 URLs from recent collected_raw outputs
and fetches each via Jina (the current fallback) and Serper /scrape.
Reports per-URL: success, latency, char count. Runs sequentially to
avoid rate limits on either side.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Load env the same way config.py does so SERPER_API_KEY is available.
from dotenv import load_dotenv  # noqa: E402

MAIN_REPO = Path("/Users/brayan.vahdat/Desktop/Intelligence Dashboard")
load_dotenv(MAIN_REPO / "frontend" / ".env.local")
load_dotenv(MAIN_REPO / ".env")

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
assert SERPER_API_KEY, "SERPER_API_KEY not set"

TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)

# Domain-diverse sample from last 5 days of collected_raw. Picked so no
# single domain dominates — this is the key fix vs my earlier test.
TEST_URLS = [
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


async def fetch_via_jina(client: httpx.AsyncClient, url: str) -> dict:
    """Mirror of enricher._fetch_via_jina (free-tier endpoint)."""
    start = time.monotonic()
    try:
        r = await client.get(f"https://r.jina.ai/{url}")
        r.raise_for_status()
        text = r.text or ""
        return {
            "ok": bool(text.strip()),
            "elapsed_s": round(time.monotonic() - start, 2),
            "chars": len(text),
            "error": None,
            "status": r.status_code,
        }
    except httpx.HTTPStatusError as e:
        return {
            "ok": False,
            "elapsed_s": round(time.monotonic() - start, 2),
            "chars": 0,
            "error": f"HTTP {e.response.status_code}",
            "status": e.response.status_code,
        }
    except Exception as e:
        return {
            "ok": False,
            "elapsed_s": round(time.monotonic() - start, 2),
            "chars": 0,
            "error": type(e).__name__ + ": " + str(e)[:80],
            "status": None,
        }


async def fetch_via_serper(client: httpx.AsyncClient, url: str) -> dict:
    """Call Serper's /scrape endpoint."""
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
            "ok": bool(text.strip()),
            "elapsed_s": round(time.monotonic() - start, 2),
            "chars": len(text),
            "error": None,
            "status": r.status_code,
            "keys": list(data.keys())[:6],
        }
    except httpx.HTTPStatusError as e:
        body = e.response.text[:200] if e.response is not None else ""
        return {
            "ok": False,
            "elapsed_s": round(time.monotonic() - start, 2),
            "chars": 0,
            "error": f"HTTP {e.response.status_code}: {body}",
            "status": e.response.status_code,
        }
    except Exception as e:
        return {
            "ok": False,
            "elapsed_s": round(time.monotonic() - start, 2),
            "chars": 0,
            "error": type(e).__name__ + ": " + str(e)[:80],
            "status": None,
        }


async def main() -> None:
    print(f"Testing {len(TEST_URLS)} URLs across {len({urlparse(u).netloc for u in TEST_URLS})} domains\n")
    rows = []
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        for url in TEST_URLS:
            domain = urlparse(url).netloc
            print(f"--- {domain} ---")
            print(f"  {url}")
            jina = await fetch_via_jina(client, url)
            print(f"  jina:   ok={jina['ok']} chars={jina['chars']:>6} elapsed={jina['elapsed_s']}s err={jina['error']}")
            serper = await fetch_via_serper(client, url)
            print(f"  serper: ok={serper['ok']} chars={serper['chars']:>6} elapsed={serper['elapsed_s']}s err={serper['error']}")
            rows.append({"url": url, "domain": domain, "jina": jina, "serper": serper})
            await asyncio.sleep(0.5)

    print("\n=== Summary ===")
    jina_ok = sum(1 for r in rows if r["jina"]["ok"])
    serper_ok = sum(1 for r in rows if r["serper"]["ok"])
    print(f"Success rate: Jina {jina_ok}/{len(rows)} | Serper {serper_ok}/{len(rows)}")

    jina_lat = [r["jina"]["elapsed_s"] for r in rows if r["jina"]["ok"]]
    serper_lat = [r["serper"]["elapsed_s"] for r in rows if r["serper"]["ok"]]
    if jina_lat:
        print(f"Jina   median latency (ok only): {sorted(jina_lat)[len(jina_lat)//2]}s")
    if serper_lat:
        print(f"Serper median latency (ok only): {sorted(serper_lat)[len(serper_lat)//2]}s")

    jina_chars = [r["jina"]["chars"] for r in rows if r["jina"]["ok"]]
    serper_chars = [r["serper"]["chars"] for r in rows if r["serper"]["ok"]]
    if jina_chars:
        print(f"Jina   median content: {sorted(jina_chars)[len(jina_chars)//2]} chars")
    if serper_chars:
        print(f"Serper median content: {sorted(serper_chars)[len(serper_chars)//2]} chars")

    print("\n=== Per-URL table ===")
    print(f"{'domain':<35} {'jina':>22} {'serper':>22}")
    for r in rows:
        j = r["jina"]
        s = r["serper"]
        j_cell = f"{'OK' if j['ok'] else 'FAIL'} {j['chars']}c {j['elapsed_s']}s"
        s_cell = f"{'OK' if s['ok'] else 'FAIL'} {s['chars']}c {s['elapsed_s']}s"
        print(f"{r['domain']:<35} {j_cell:>22} {s_cell:>22}")


if __name__ == "__main__":
    asyncio.run(main())
