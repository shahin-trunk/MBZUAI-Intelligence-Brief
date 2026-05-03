#!/usr/bin/env python3
"""Retry the 17 entities that failed in the first run of
upload_real_logos.py. Uses alternate sources: Clearbit Logo API for
public domains, and hand-curated Wikipedia/brand-page URLs for
entities that Clearbit doesn't have.
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
    BUCKET,
    LOGOS_DIR,
    _content_type,
    _extension_from_url,
    download_logo,
    update_db_logo_path,
    upload_to_storage,
    USER_AGENT,
)


# Failed entities from the first run, each with an expanded URL list.
# Clearbit Logo API: https://logo.clearbit.com/{domain} — free, returns
# PNG at ~128x128, works for most well-known public domains.
RETRY_SOURCES: dict[str, tuple[str, list[str]]] = {
    # ── Gulf entities ────────────────────────────────────────────────────
    "Abu Dhabi Government": ("abudhabi", [
        "https://logo.clearbit.com/abudhabi.ae",
        "https://logo.clearbit.com/tamm.abudhabi",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Flag_of_Abu_Dhabi.svg/512px-Flag_of_Abu_Dhabi.svg.png",
    ]),
    "ADQ": ("adq", [
        "https://logo.clearbit.com/adq.ae",
        "https://upload.wikimedia.org/wikipedia/en/thumb/2/25/ADQ_Holding_PJSC_logo.svg/512px-ADQ_Holding_PJSC_logo.svg.png",
    ]),
    "ASPIRE": ("aspire", [
        "https://logo.clearbit.com/aspireuae.com",
        "https://aspireuae.com/favicon-32x32.png",
        "https://aspireuae.com/favicon-96x96.png",
    ]),
    "ATRC": ("atrc", [
        "https://logo.clearbit.com/atrc.ae",
        "https://atrc.ae/favicon-32x32.png",
        "https://atrc.ae/favicon-96x96.png",
    ]),
    "Firmus": ("firmus", [
        "https://logo.clearbit.com/firmus.energy",
        "https://logo.clearbit.com/firmusventures.com",
        "https://firmus.energy/favicon-32x32.png",
    ]),
    "Masdar": ("masdar", [
        "https://logo.clearbit.com/masdar.ae",
        "https://masdar.ae/favicon-32x32.png",
        "https://masdar.ae/favicon.png",
    ]),
    "MBZUAI": ("mbzuai", [
        "https://logo.clearbit.com/mbzuai.ac.ae",
        "https://mbzuai.ac.ae/favicon-32x32.png",
        "https://mbzuai.ac.ae/favicon.png",
    ]),
    "Saudi Arabia": ("saudi", [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Flag_of_Saudi_Arabia.svg/512px-Flag_of_Saudi_Arabia.svg.png",
        "https://logo.clearbit.com/my.gov.sa",
    ]),
    "SDAIA": ("sdaia", [
        "https://logo.clearbit.com/sdaia.gov.sa",
        "https://sdaia.gov.sa/en/favicon-32x32.png",
        "https://sdaia.gov.sa/favicon.png",
    ]),
    "TII": ("tii", [
        "https://logo.clearbit.com/tii.ae",
        "https://tii.ae/favicon-32x32.png",
        "https://tii.ae/sites/default/files/favicon.png",
    ]),
    # ── Global AI/tech ────────────────────────────────────────────────
    "Anthropic": ("anthropic", [
        "https://logo.clearbit.com/anthropic.com",
        "https://claude.ai/apple-touch-icon.png",
        "https://claude.ai/favicon.ico",
    ]),
    "Broadcom": ("broadcom", [
        "https://logo.clearbit.com/broadcom.com",
        "https://www.broadcom.com/themes/custom/broadcom/favicon.ico",
    ]),
    "Cerebras": ("cerebras", [
        "https://logo.clearbit.com/cerebras.net",
        "https://cerebras.ai/favicon.ico",
        "https://www.cerebras.ai/favicon.ico",
    ]),
    "Meta": ("meta", [
        "https://logo.clearbit.com/meta.com",
        "https://about.meta.com/favicon.ico",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/512px-Meta_Platforms_Inc._logo.svg.png",
    ]),
    "Samsung": ("samsung", [
        "https://logo.clearbit.com/samsung.com",
        "https://images.samsung.com/is/image/samsung/assets/global/about-us/brand/logo/mo/360_197_1.png",
    ]),
    "Tencent": ("tencent", [
        "https://logo.clearbit.com/tencent.com",
        "https://www.tencent.com/favicon.ico",
    ]),
    "Together AI": ("together", [
        "https://logo.clearbit.com/together.ai",
        "https://logo.clearbit.com/together.xyz",
        "https://www.together.ai/favicon.ico",
    ]),
}


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
        downloaded = download_logo(stem, urls)
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
