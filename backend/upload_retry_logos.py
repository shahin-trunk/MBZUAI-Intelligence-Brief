#!/usr/bin/env python3
"""One-shot retry for entities that failed the DuckDuckGo favicon lookup.
Uses alternative URLs (Google favicon, alternate domains).
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
from upload_gap_logos import _content_type, _ext, upload_to_storage, upsert_row

LOGOS_DIR = Path(__file__).resolve().parent / "logos"
LOGOS_DIR.mkdir(exist_ok=True)

USER_AGENT = "MBZUAIIntelligenceDashboardLogoFetcher/1.0 (+https://mbzuai.ac.ae)"

# (entity_name, category, aliases, url)
RETRY_ENTITIES = [
    (
        "IHC",
        "company",
        ["International Holding Company", "IHC Group"],
        "https://icons.duckduckgo.com/ip3/ihcuae.com.ico",
    ),
    (
        "Mubadala",
        "finance",
        ["Mubadala Investment Company"],
        "https://www.google.com/s2/favicons?domain=mubadala.com&sz=128",
    ),
    (
        "IMF",
        "org",
        ["International Monetary Fund"],
        "https://www.google.com/s2/favicons?domain=imf.org&sz=128",
    ),
    # Khazna and Masdar: no reliable favicon source found.
    # Insert rows with empty logo_path so they show up in the admin
    # grid (with fallback glyph) and can have logos uploaded manually.
]

# Entities to insert with no logo (fallback glyph).
FALLBACK_ONLY = [
    ("Khazna", "company", ["Khazna Data Centers"]),
    ("Masdar", "energy", ["Abu Dhabi Future Energy Company"]),
]


def main() -> None:
    for env_path in load_project_env():
        print(f"env: loaded {env_path}")

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing env vars")
        sys.exit(1)

    sb = create_client(url, key)

    for entity_name, category, aliases, logo_url in RETRY_ENTITIES:
        print(f"\n🔸 {entity_name}")
        try:
            with httpx.Client(timeout=15, follow_redirects=True,
                              headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(logo_url)
        except Exception as e:
            print(f"    ❌ {logo_url} — {e}")
            continue

        if resp.status_code != 200 or len(resp.content) < 100:
            print(f"    ❌ {logo_url} — HTTP {resp.status_code} ({len(resp.content)} bytes)")
            continue

        data = resp.content
        ct = _content_type(data)
        ext = _ext(ct)
        slug = entity_name.lower().replace(" ", "-").replace("/", "-")
        filename = f"{slug}.{ext}"
        path = LOGOS_DIR / filename
        path.write_bytes(data)
        print(f"    ✅ {logo_url} → {filename} ({len(data)} bytes, {ct})")

        if not upload_to_storage(sb, path, ct):
            continue
        upsert_row(sb, entity_name, filename, category, aliases)
        time.sleep(0.3)

    # Insert fallback-only rows
    for entity_name, category, aliases in FALLBACK_ONLY:
        print(f"\n🔸 {entity_name} (fallback only)")
        upsert_row(sb, entity_name, "", category, aliases)

    print("\n✅ Done")


if __name__ == "__main__":
    main()
