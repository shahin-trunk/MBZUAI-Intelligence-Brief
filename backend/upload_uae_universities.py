#!/usr/bin/env python3
"""Upload logos for UAE universities to entity_logos."""

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

# (entity_name, aliases, url)
UAE_UNIVERSITIES: list[tuple[str, list[str], str]] = [
    (
        "MBZUAI",
        ["Mohamed bin Zayed University of Artificial Intelligence"],
        "https://www.google.com/s2/favicons?domain=mbzuai.ac.ae&sz=128",
    ),
    (
        "NYUAD",
        ["New York University Abu Dhabi", "NYU Abu Dhabi"],
        "https://icons.duckduckgo.com/ip3/nyuad.nyu.edu.ico",
    ),
    (
        "Sorbonne Abu Dhabi",
        ["Sorbonne University Abu Dhabi", "Paris-Sorbonne Abu Dhabi"],
        "https://icons.duckduckgo.com/ip3/sorbonne.ae.ico",
    ),
    (
        "UAEU",
        ["United Arab Emirates University", "UAE University"],
        "https://www.google.com/s2/favicons?domain=uaeu.ac.ae&sz=128",
    ),
    (
        "University of Sharjah",
        ["UoS"],
        "https://www.google.com/s2/favicons?domain=sharjah.ac.ae&sz=128",
    ),
    (
        "Khalifa University",
        ["KU", "Khalifa University of Science and Technology"],
        # No favicon found — insert with empty logo_path
        "",
    ),
    (
        "Zayed University",
        ["ZU"],
        "https://www.google.com/s2/favicons?domain=zu.ac.ae&sz=128",
    ),
    (
        "American University of Sharjah",
        ["AUS"],
        "https://icons.duckduckgo.com/ip3/aus.edu.ico",
    ),
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
    successes, failures = [], []

    for entity_name, aliases, logo_url in UAE_UNIVERSITIES:
        print(f"\n🔸 {entity_name}")

        if not logo_url:
            # No logo available — insert with fallback
            if upsert_row(sb, entity_name, "", "university", aliases):
                successes.append(entity_name)
            else:
                failures.append(entity_name)
            continue

        try:
            with httpx.Client(timeout=15, follow_redirects=True,
                              headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(logo_url)
        except Exception as e:
            print(f"    ❌ {logo_url} — {e}")
            failures.append(entity_name)
            continue

        if resp.status_code != 200 or len(resp.content) < 100:
            print(f"    ❌ {logo_url} — HTTP {resp.status_code} ({len(resp.content)} bytes)")
            # Still insert the row with empty logo_path
            upsert_row(sb, entity_name, "", "university", aliases)
            successes.append(entity_name)
            continue

        data = resp.content
        ct = _content_type(data)
        ext = _ext(ct)
        slug = entity_name.lower().replace(" ", "-").replace("/", "-")
        filename = f"{slug}.{ext}"
        path = LOGOS_DIR / filename
        path.write_bytes(data)
        print(f"    ✅ → {filename} ({len(data)} bytes, {ct})")

        if not upload_to_storage(sb, path, ct):
            failures.append(entity_name)
            continue

        if not upsert_row(sb, entity_name, filename, "university", aliases):
            failures.append(entity_name)
            continue

        successes.append(entity_name)
        time.sleep(0.3)

    print("\n" + "=" * 60)
    print(f"✅ {len(successes)} succeeded")
    print(f"❌ {len(failures)} failed")
    if failures:
        for name in failures:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
