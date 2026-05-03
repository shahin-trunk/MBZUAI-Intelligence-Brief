#!/usr/bin/env python3
"""Upload logos for high-profile entities found in pending_items that
currently lack an entity_logos row.

Uses DuckDuckGo favicon service as primary source (same approach as
upload_real_logos.py). Falls back to direct known URLs for entities
where we know the official icon location.

Usage:
    python3 backend/upload_gap_logos.py
    python3 backend/upload_gap_logos.py --only tesla
    python3 backend/upload_gap_logos.py --dry-run
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
USER_AGENT = "MBZUAIIntelligenceDashboardLogoFetcher/1.0 (+https://mbzuai.ac.ae)"

# (entity_name, category, aliases, logo_source_url)
# logo_source_url: use DuckDuckGo favicon proxy for domains, or direct URLs
GAP_ENTITIES: list[tuple[str, str, list[str], str]] = [
    (
        "Tesla",
        "company",
        ["TSLA", "Tesla Inc"],
        "https://icons.duckduckgo.com/ip3/tesla.com.ico",
    ),
    (
        "SpaceX",
        "company",
        ["Space Exploration Technologies"],
        "https://icons.duckduckgo.com/ip3/spacex.com.ico",
    ),
    (
        "Perplexity",
        "company",
        ["Perplexity AI"],
        "https://icons.duckduckgo.com/ip3/perplexity.ai.ico",
    ),
    (
        "Saudi Aramco",
        "energy",
        ["Aramco", "Saudi Arabian Oil Company"],
        "https://icons.duckduckgo.com/ip3/aramco.com.ico",
    ),
    (
        "Etihad Airways",
        "company",
        ["Etihad"],
        "https://icons.duckduckgo.com/ip3/etihad.com.ico",
    ),
    (
        "Hyundai Motor",
        "company",
        ["Hyundai", "Hyundai Motor Company"],
        "https://icons.duckduckgo.com/ip3/hyundai.com.ico",
    ),
    (
        "Federal Reserve",
        "government",
        ["Fed", "US Federal Reserve", "The Fed"],
        "https://icons.duckduckgo.com/ip3/federalreserve.gov.ico",
    ),
    (
        "PyTorch",
        "model",
        ["pytorch"],
        "https://icons.duckduckgo.com/ip3/pytorch.org.ico",
    ),
    (
        "Salesforce",
        "company",
        ["Slack/Salesforce", "Slack"],
        "https://icons.duckduckgo.com/ip3/salesforce.com.ico",
    ),
    # ── UAE entities ────────────────────────────────────────────────
    (
        "e&",
        "company",
        ["Etisalat", "Emirates Telecommunications Group", "e& Group"],
        "https://icons.duckduckgo.com/ip3/eand.com.ico",
    ),
    (
        "du",
        "company",
        ["Emirates Integrated Telecommunications", "EITC"],
        "https://icons.duckduckgo.com/ip3/du.ae.ico",
    ),
    (
        "Khazna",
        "company",
        ["Khazna Data Centers"],
        "https://icons.duckduckgo.com/ip3/khazna.com.ico",
    ),
    (
        "IHC",
        "company",
        ["International Holding Company", "IHC Group"],
        "https://icons.duckduckgo.com/ip3/ihc.ae.ico",
    ),
    (
        "ADIO",
        "government",
        ["Abu Dhabi Investment Office"],
        "https://icons.duckduckgo.com/ip3/investinabudhabi.gov.ae.ico",
    ),
    (
        "ADGM",
        "finance",
        ["Abu Dhabi Global Market"],
        "https://icons.duckduckgo.com/ip3/adgm.com.ico",
    ),
    (
        "Modon",
        "government",
        ["Modon Properties", "Abu Dhabi Modon"],
        "https://icons.duckduckgo.com/ip3/modon.ae.ico",
    ),
    (
        "Aldar",
        "company",
        ["Aldar Properties"],
        "https://icons.duckduckgo.com/ip3/aldar.com.ico",
    ),
    (
        "ADNOC",
        "energy",
        ["Abu Dhabi National Oil Company"],
        "https://icons.duckduckgo.com/ip3/adnoc.ae.ico",
    ),
    (
        "Mubadala",
        "finance",
        ["Mubadala Investment Company"],
        "https://icons.duckduckgo.com/ip3/mubadala.com.ico",
    ),
    (
        "ADIA",
        "finance",
        ["Abu Dhabi Investment Authority"],
        "https://icons.duckduckgo.com/ip3/adia.ae.ico",
    ),
    (
        "Emirates",
        "company",
        ["Emirates Airline", "Emirates Group"],
        "https://icons.duckduckgo.com/ip3/emirates.com.ico",
    ),
    (
        "DP World",
        "company",
        ["Dubai Ports World"],
        "https://icons.duckduckgo.com/ip3/dpworld.com.ico",
    ),
    (
        "DEWA",
        "government",
        ["Dubai Electricity and Water Authority"],
        "https://icons.duckduckgo.com/ip3/dewa.gov.ae.ico",
    ),
    (
        "Masdar",
        "energy",
        ["Abu Dhabi Future Energy Company"],
        "https://icons.duckduckgo.com/ip3/masdar.ae.ico",
    ),
    # ── International organizations ─────────────────────────────────
    (
        "United Nations",
        "org",
        ["UN", "United Nations Security Council", "UNSC"],
        "https://icons.duckduckgo.com/ip3/un.org.ico",
    ),
    (
        "IMF",
        "org",
        ["International Monetary Fund"],
        "https://icons.duckduckgo.com/ip3/imf.org.ico",
    ),
    (
        "World Bank",
        "org",
        ["World Bank Group", "IBRD"],
        "https://icons.duckduckgo.com/ip3/worldbank.org.ico",
    ),
    (
        "NATO",
        "org",
        ["North Atlantic Treaty Organization"],
        "https://icons.duckduckgo.com/ip3/nato.int.ico",
    ),
    (
        "WHO",
        "org",
        ["World Health Organization"],
        "https://icons.duckduckgo.com/ip3/who.int.ico",
    ),
    (
        "WTO",
        "org",
        ["World Trade Organization"],
        "https://icons.duckduckgo.com/ip3/wto.org.ico",
    ),
    (
        "OPEC",
        "org",
        ["Organization of the Petroleum Exporting Countries", "OPEC+"],
        "https://icons.duckduckgo.com/ip3/opec.org.ico",
    ),
    (
        "IAEA",
        "org",
        ["International Atomic Energy Agency"],
        "https://icons.duckduckgo.com/ip3/iaea.org.ico",
    ),
    (
        "ICC",
        "org",
        ["International Criminal Court"],
        "https://icons.duckduckgo.com/ip3/icc-cpi.int.ico",
    ),
]


def _content_type(data: bytes) -> str:
    """Guess content type from magic bytes."""
    if data[:8].startswith(b"\x89PNG"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    head = data[:512].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        return "image/svg+xml"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"\x00\x00\x01\x00":
        return "image/x-icon"
    return "image/png"  # safe default


def _ext(ct: str) -> str:
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/svg+xml": "svg",
        "image/webp": "webp",
        "image/gif": "gif",
        "image/x-icon": "ico",
    }.get(ct, "png")


def download_logo(name: str, url: str) -> tuple[Path, str] | None:
    """Download logo from URL. Returns (path, content_type) on success."""
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

    data = resp.content
    if len(data) < 100:
        print(f"    ❌ {url} — suspiciously small ({len(data)} bytes)")
        return None

    ct = _content_type(data)
    ext = _ext(ct)
    slug = name.lower().replace(" ", "-").replace("/", "-")
    filename = f"{slug}.{ext}"
    path = LOGOS_DIR / filename
    path.write_bytes(data)
    print(f"    ✅ {url} → {filename} ({len(data)} bytes, {ct})")
    return path, ct


def upload_to_storage(sb, file_path: Path, content_type: str) -> bool:
    filename = file_path.name
    try:
        data = file_path.read_bytes()
        sb.storage.from_(BUCKET).upload(
            filename, data, {"content-type": content_type, "upsert": "true"},
        )
        print(f"    ⬆️  uploaded {filename}")
        return True
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "already exists" in msg:
            try:
                sb.storage.from_(BUCKET).remove([filename])
                sb.storage.from_(BUCKET).upload(
                    filename, file_path.read_bytes(), {"content-type": content_type},
                )
                print(f"    ⬆️  overwrote {filename}")
                return True
            except Exception as e2:
                print(f"    ❌ overwrite failed: {e2}")
                return False
        print(f"    ❌ upload failed: {e}")
        return False


def upsert_row(sb, entity_name: str, logo_path: str, category: str, aliases: list[str]) -> bool:
    try:
        resp = (
            sb.table("entity_logos")
            .select("entity_name")
            .eq("entity_name", entity_name)
            .maybe_single()
            .execute()
        )
        # supabase-py returns None from .execute() when no row matches;
        # normalize to the same object-with-.data shape used below.
        existing = resp if resp else type("O", (), {"data": None})
    except AttributeError:
        rows = (
            sb.table("entity_logos")
            .select("entity_name")
            .eq("entity_name", entity_name)
            .limit(1)
            .execute()
        )
        existing = type("O", (), {"data": rows.data[0] if rows.data else None})

    payload = {
        "entity_name": entity_name,
        "logo_path": logo_path,
        "category": category,
        "aliases": aliases,
    }

    try:
        if existing.data:
            sb.table("entity_logos").update(
                {"logo_path": logo_path, "category": category, "aliases": aliases}
            ).eq("entity_name", entity_name).execute()
            print(f"    💾 updated {entity_name}")
        else:
            sb.table("entity_logos").insert(payload).execute()
            print(f"    💾 inserted {entity_name}")
        return True
    except Exception as e:
        print(f"    ❌ DB write failed for {entity_name}: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Process only entities matching this substring")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for env_path in load_project_env():
        print(f"env: loaded {env_path}")

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    sb = create_client(url, key)

    entries = GAP_ENTITIES
    if args.only:
        needle = args.only.strip().lower()
        entries = [e for e in GAP_ENTITIES if needle in e[0].lower()]
        if not entries:
            print(f"No entity matching --only={args.only}")
            sys.exit(1)

    successes, failures = [], []

    for entity_name, category, aliases, logo_url in entries:
        print(f"\n🔸 {entity_name}")
        result = download_logo(entity_name, logo_url)
        if not result:
            failures.append(entity_name)
            continue
        file_path, ct = result

        if args.dry_run:
            print("    (dry run)")
            successes.append(entity_name)
            continue

        if not upload_to_storage(sb, file_path, ct):
            failures.append(entity_name)
            continue

        if not upsert_row(sb, entity_name, file_path.name, category, aliases):
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
