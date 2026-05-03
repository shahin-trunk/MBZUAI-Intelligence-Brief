#!/usr/bin/env python3
"""Pass 3 for the 14 entities that still failed after Clearbit attempts.
Key changes from the previous retry:
  - Drop Clearbit entirely (DNS fails on this machine; the free logo
    API was deprecated in late 2024 anyway)
  - Use Google S2 favicon service as a universal fallback:
      https://www.google.com/s2/favicons?domain={domain}&sz=128
    This works for almost any public domain because Google maintains
    its own icon cache.
  - Use a proper User-Agent for Wikimedia (otherwise 429).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import load_project_env
from upload_real_logos import (
    LOGOS_DIR,
    _content_type,
    _extension_from_url,
    update_db_logo_path,
    upload_to_storage,
)

# Wikimedia requires a specific UA format with contact info.
WIKIMEDIA_UA = (
    "MBZUAI-IntelligenceDashboard/1.0 (https://mbzuai-intel.com; "
    "brayan.vahdat@mbzuai.ac.ae)"
)
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _google_s2(domain: str, size: int = 128) -> str:
    return f"https://www.google.com/s2/favicons?domain={domain}&sz={size}"


# Entity → (file stem, list of (url, user_agent_override or None))
# user_agent override lets us send the Wikimedia UA only when needed.
RETRY_SOURCES: dict[str, tuple[str, list[tuple[str, str | None]]]] = {
    # ── Gulf entities ────────────────────────────────────────────────────
    "Abu Dhabi Government": ("abudhabi", [
        (_google_s2("abudhabi.ae", 256), None),
        (_google_s2("u.ae", 256), None),
        ("https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Flag_of_Abu_Dhabi.svg/512px-Flag_of_Abu_Dhabi.svg.png", WIKIMEDIA_UA),
    ]),
    "ADQ": ("adq", [
        (_google_s2("adq.ae", 256), None),
        ("https://upload.wikimedia.org/wikipedia/en/thumb/2/25/ADQ_Holding_PJSC_logo.svg/512px-ADQ_Holding_PJSC_logo.svg.png", WIKIMEDIA_UA),
    ]),
    "ASPIRE": ("aspire", [
        (_google_s2("aspireuae.com", 256), None),
        (_google_s2("aspire.ae", 256), None),
    ]),
    "ATRC": ("atrc", [
        (_google_s2("atrc.ae", 256), None),
    ]),
    "Firmus": ("firmus", [
        (_google_s2("firmus.energy", 256), None),
        (_google_s2("firmusventures.com", 256), None),
    ]),
    "Masdar": ("masdar", [
        (_google_s2("masdar.ae", 256), None),
    ]),
    "MBZUAI": ("mbzuai", [
        (_google_s2("mbzuai.ac.ae", 256), None),
    ]),
    "Saudi Arabia": ("saudi", [
        ("https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Flag_of_Saudi_Arabia.svg/512px-Flag_of_Saudi_Arabia.svg.png", WIKIMEDIA_UA),
        (_google_s2("my.gov.sa", 256), None),
    ]),
    "SDAIA": ("sdaia", [
        (_google_s2("sdaia.gov.sa", 256), None),
    ]),
    "TII": ("tii", [
        (_google_s2("tii.ae", 256), None),
    ]),
    # ── Global tech ──────────────────────────────────────────────────
    "Broadcom": ("broadcom", [
        (_google_s2("broadcom.com", 256), None),
        ("https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Broadcom_Inc._logo.svg/512px-Broadcom_Inc._logo.svg.png", WIKIMEDIA_UA),
    ]),
    "Cerebras": ("cerebras", [
        (_google_s2("cerebras.ai", 256), None),
        (_google_s2("cerebras.net", 256), None),
    ]),
    "Meta": ("meta", [
        (_google_s2("meta.com", 256), None),
        ("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/512px-Meta_Platforms_Inc._logo.svg.png", WIKIMEDIA_UA),
    ]),
    "Together AI": ("together", [
        (_google_s2("together.ai", 256), None),
        (_google_s2("together.xyz", 256), None),
    ]),
}


def download_with_ua(stem: str, urls: list[tuple[str, str | None]]) -> Path | None:
    """Download from a list of (url, optional_ua) tuples."""
    for url, ua in urls:
        headers = {"User-Agent": ua or DEFAULT_UA}
        try:
            with httpx.Client(
                follow_redirects=True, timeout=15, headers=headers
            ) as client:
                resp = client.get(url)
        except Exception as e:
            print(f"    ❌ {url} — {type(e).__name__}: {e}")
            continue
        if resp.status_code != 200:
            print(f"    ❌ {url} — HTTP {resp.status_code}")
            continue
        if len(resp.content) < 200:
            print(f"    ❌ {url} — too small ({len(resp.content)} bytes)")
            continue
        ext = _extension_from_url(url)
        filename = f"{stem}{ext}"
        path = LOGOS_DIR / filename
        path.write_bytes(resp.content)
        print(f"    ✅ {url} → {filename} ({len(resp.content)} bytes)")
        return path
    return None


def main() -> None:
    for env_path in load_project_env():
        print(f"env: loaded {env_path}")

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    sb = create_client(url, key)

    successes: list[str] = []
    failures: list[str] = []

    for entity_name, (stem, urls) in RETRY_SOURCES.items():
        print(f"\n🔸 {entity_name}")
        downloaded = download_with_ua(stem, urls)
        if not downloaded:
            failures.append(entity_name)
            continue
        if not upload_to_storage(sb, downloaded):
            failures.append(entity_name)
            continue
        if not update_db_logo_path(sb, entity_name, downloaded.name):
            failures.append(entity_name)
            continue
        successes.append(entity_name)
        time.sleep(0.3)

    print("\n" + "=" * 60)
    print(f"✅ {len(successes)} succeeded")
    print(f"❌ {len(failures)} failed")
    if failures:
        print("Still failing:")
        for name in failures:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
