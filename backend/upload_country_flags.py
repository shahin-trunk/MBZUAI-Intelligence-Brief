#!/usr/bin/env python3
"""Upload country flags for the top ~50 economies to the entity-logos
bucket and upsert corresponding rows into entity_logos.

Flags are sourced from the `flag-icons` project (lipis/flag-icons on
GitHub, MIT licensed) as 4x3 SVGs. Uploaded under `country-{iso2}.svg`
in the entity-logos bucket. Rows are created with category='country'
so the card reader can render them without the white-plate treatment
used for brand logos.

The list covers the 50 largest economies by GDP plus the European Union.
Existing rows (e.g. from the earlier G20-only run) are updated in place.

Usage:
    python3 backend/upload_country_flags.py             # download + upload + upsert
    python3 backend/upload_country_flags.py --dry-run   # download only, no side effects
    python3 backend/upload_country_flags.py --only ae   # single country by iso2
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import load_project_env

LOGOS_DIR = Path(__file__).resolve().parent / "logos"
LOGOS_DIR.mkdir(exist_ok=True)

BUCKET = "entity-logos"
FLAG_URL = "https://raw.githubusercontent.com/lipis/flag-icons/main/flags/4x3/{code}.svg"
USER_AGENT = "MBZUAIIntelligenceDashboardLogoFetcher/1.0 (+https://mbzuai.ac.ae)"


# (entity_name, iso2, aliases). Ordered roughly by GDP rank.
# Includes the original G20 members plus ~30 additional top economies.
TOP_COUNTRIES: list[tuple[str, str, list[str]]] = [
    # ── G20 members (existing) ──────────────────────────────────────
    ("United States",        "us", ["USA", "US", "America", "United States of America"]),
    ("China",                "cn", ["People's Republic of China", "PRC"]),
    ("Germany",              "de", []),
    ("Japan",                "jp", []),
    ("India",                "in", []),
    ("United Kingdom",       "gb", ["UK", "Britain", "Great Britain"]),
    ("France",               "fr", []),
    ("Italy",                "it", []),
    ("Brazil",               "br", []),
    ("Canada",               "ca", []),
    ("Russia",               "ru", ["Russian Federation"]),
    ("Mexico",               "mx", []),
    ("Australia",            "au", []),
    ("South Korea",          "kr", ["Republic of Korea", "Korea"]),
    ("Indonesia",            "id", []),
    ("Turkey",               "tr", ["Türkiye", "Turkiye"]),
    ("Saudi Arabia",         "sa", ["Kingdom of Saudi Arabia", "KSA"]),
    ("Argentina",            "ar", []),
    ("South Africa",         "za", []),
    ("European Union",       "eu", ["EU"]),
    # ── Additional top economies ────────────────────────────────────
    ("Spain",                "es", []),
    ("Netherlands",          "nl", ["Holland"]),
    ("Switzerland",          "ch", ["Swiss Confederation"]),
    ("Poland",               "pl", []),
    ("Sweden",               "se", []),
    ("Norway",               "no", []),
    ("Belgium",              "be", []),
    ("Ireland",              "ie", []),
    ("Israel",               "il", []),
    ("Austria",              "at", []),
    ("Thailand",             "th", []),
    ("United Arab Emirates", "ae", ["UAE", "Emirates"]),
    ("Nigeria",              "ng", []),
    ("Singapore",            "sg", []),
    ("Bangladesh",           "bd", []),
    ("Egypt",                "eg", []),
    ("Philippines",          "ph", []),
    ("Malaysia",             "my", []),
    ("Denmark",              "dk", []),
    ("Colombia",             "co", []),
    ("Vietnam",              "vn", []),
    ("Pakistan",             "pk", []),
    ("Chile",                "cl", []),
    ("Czech Republic",       "cz", ["Czechia"]),
    ("Romania",              "ro", []),
    ("Finland",              "fi", []),
    ("Portugal",             "pt", []),
    ("New Zealand",          "nz", []),
    ("Peru",                 "pe", []),
    ("Greece",               "gr", []),
    ("Iraq",                 "iq", []),
    # ── Gap-fill from pending_items analysis ────────────────────────
    ("Iran",                 "ir", ["Islamic Republic of Iran"]),
    ("Qatar",                "qa", []),
    ("Kuwait",               "kw", []),
    ("Bahrain",              "bh", []),
    ("Oman",                 "om", ["Sultanate of Oman"]),
    ("Hungary",              "hu", []),
]


def download_flag(iso2: str) -> Path | None:
    """Download the 4x3 SVG from flag-icons. Returns saved path on success."""
    url = FLAG_URL.format(code=iso2)
    try:
        with httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = client.get(url)
    except Exception as e:
        print(f"    ❌ {url} — {type(e).__name__}: {e}")
        return None

    if resp.status_code != 200:
        print(f"    ❌ {url} — HTTP {resp.status_code}")
        return None

    content = resp.content
    # Signature sanity check: SVGs start with `<?xml` or `<svg`
    head = content[:512].lstrip()
    if not (head.startswith(b"<?xml") or head.startswith(b"<svg")):
        print(f"    ❌ {url} — not an SVG (head: {content[:32]!r})")
        return None

    filename = f"country-{iso2}.svg"
    path = LOGOS_DIR / filename
    path.write_bytes(content)
    print(f"    ✅ {url} → {filename} ({len(content)} bytes)")
    return path


def upload_to_storage(sb, file_path: Path) -> bool:
    filename = file_path.name
    try:
        data = file_path.read_bytes()
        sb.storage.from_(BUCKET).upload(
            filename,
            data,
            {"content-type": "image/svg+xml", "upsert": "true"},
        )
        print(f"    ⬆️  uploaded {filename}")
        return True
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "already exists" in msg:
            try:
                sb.storage.from_(BUCKET).remove([filename])
                sb.storage.from_(BUCKET).upload(
                    filename,
                    file_path.read_bytes(),
                    {"content-type": "image/svg+xml"},
                )
                print(f"    ⬆️  overwrote {filename}")
                return True
            except Exception as e2:
                print(f"    ❌ overwrite failed: {e2}")
                return False
        print(f"    ❌ upload failed: {e}")
        return False


def upsert_row(sb, entity_name: str, logo_path: str, aliases: list[str]) -> bool:
    """Upsert a row in entity_logos. Uses update-then-insert because the
    table's PK constraint doesn't always play well with supabase-py's
    upsert() — doing it explicitly is simpler and more predictable."""
    try:
        resp = (
            sb.table("entity_logos")
            .select("entity_name")
            .eq("entity_name", entity_name)
            .maybe_single()
            .execute()
        )
        # supabase-py returns None from .execute() when no row matches;
        # normalize to the same object-with-.data shape used by the
        # AttributeError fallback below.
        existing = resp if resp else type("O", (), {"data": None})
    except AttributeError:
        existing_rows = (
            sb.table("entity_logos")
            .select("entity_name")
            .eq("entity_name", entity_name)
            .limit(1)
            .execute()
        )
        existing = type("O", (), {"data": existing_rows.data[0] if existing_rows.data else None})

    payload = {
        "entity_name": entity_name,
        "logo_path": logo_path,
        "category": "country",
        "aliases": aliases,
    }

    try:
        if existing.data:
            sb.table("entity_logos").update(
                {
                    "logo_path": logo_path,
                    "category": "country",
                    "aliases": aliases,
                }
            ).eq("entity_name", entity_name).execute()
            print(f"    💾 updated {entity_name} → {logo_path}")
        else:
            sb.table("entity_logos").insert(payload).execute()
            print(f"    💾 inserted {entity_name} → {logo_path}")
        return True
    except Exception as e:
        print(f"    ❌ DB write failed for {entity_name}: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Process only this ISO2 code or name substring")
    parser.add_argument("--dry-run", action="store_true", help="Download but do not upload or update DB")
    args = parser.parse_args()

    for env_path in load_project_env():
        print(f"env: loaded {env_path}")

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    sb = create_client(url, key)

    countries = TOP_COUNTRIES
    if args.only:
        needle = args.only.strip().lower()
        countries = [
            (name, iso, aliases)
            for (name, iso, aliases) in TOP_COUNTRIES
            if iso == needle or needle in name.lower()
        ]
        if not countries:
            print(f"No country matching --only={args.only}")
            sys.exit(1)

    successes: list[str] = []
    failures: list[str] = []

    for entity_name, iso2, aliases in countries:
        print(f"\n🔸 {entity_name} ({iso2.upper()})")
        downloaded = download_flag(iso2)
        if not downloaded:
            failures.append(entity_name)
            continue

        if args.dry_run:
            print("    (dry run — not uploading or updating DB)")
            successes.append(entity_name)
            time.sleep(0.1)
            continue

        if not upload_to_storage(sb, downloaded):
            failures.append(entity_name)
            continue

        if not upsert_row(sb, entity_name, downloaded.name, aliases):
            failures.append(entity_name)
            continue

        successes.append(entity_name)
        time.sleep(0.2)  # polite pacing

    print("\n" + "=" * 60)
    print(f"✅ {len(successes)} succeeded")
    print(f"❌ {len(failures)} failed")
    if failures:
        print("Failed:")
        for name in failures:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
