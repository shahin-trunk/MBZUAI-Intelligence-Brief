#!/usr/bin/env python3
"""Download real logos for every row in entity_logos and upload to Supabase
Storage. Uses the official apple-touch-icon as the primary source (most
reliable, usually 180x180 or 192x192 PNG with transparent background), with
alternate URLs per entity as fallbacks.

Usage:
    python3 backend/upload_real_logos.py                  # download + upload all
    python3 backend/upload_real_logos.py --only mubadala  # single entity
    python3 backend/upload_real_logos.py --dry-run        # no upload, just report
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
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


# Map entity_name (case-sensitive, matching DB) → (file_stem, list[source_url]).
# The first URL to return >1KB of binary wins. Using apple-touch-icon is the
# most reliable across the modern web (Apple requires >= 180x180).
ENTITY_SOURCES: dict[str, tuple[str, list[str]]] = {
    # ── Gulf entities ────────────────────────────────────────────────────
    "Abu Dhabi Government": ("abudhabi", [
        "https://www.abudhabi.ae/apple-touch-icon.png",
        "https://www.tamm.abudhabi/apple-touch-icon.png",
        "https://u.ae/apple-touch-icon.png",
    ]),
    "ADIA": ("adia", [
        "https://www.adia.ae/apple-touch-icon.png",
        "https://www.adia.ae/favicon.ico",
    ]),
    "ADNOC": ("adnoc", [
        "https://www.adnoc.ae/apple-touch-icon.png",
        "https://www.adnoc.ae/favicon.ico",
    ]),
    "ADQ": ("adq", [
        "https://www.adq.ae/apple-touch-icon.png",
        "https://www.adq.ae/favicon.ico",
    ]),
    "ASPIRE": ("aspire", [
        "https://aspireuae.com/apple-touch-icon.png",
        "https://aspireuae.com/favicon.ico",
    ]),
    "ATRC": ("atrc", [
        "https://atrc.ae/apple-touch-icon.png",
        "https://atrc.ae/favicon.ico",
    ]),
    "Core42": ("core42", [
        "https://core42.ai/apple-touch-icon.png",
        "https://core42.ai/favicon.ico",
    ]),
    "DEWA": ("dewa", [
        "https://www.dewa.gov.ae/apple-touch-icon.png",
        "https://www.dewa.gov.ae/favicon.ico",
    ]),
    "Firmus": ("firmus", [
        "https://www.firmus.energy/apple-touch-icon.png",
        "https://firmus.energy/apple-touch-icon.png",
        "https://firmus.energy/favicon.ico",
    ]),
    "G42": ("g42", [
        "https://www.g42.ai/apple-touch-icon.png",
        "https://g42.ai/apple-touch-icon.png",
        "https://g42.ai/favicon.ico",
    ]),
    "KAUST": ("kaust", [
        "https://www.kaust.edu.sa/apple-touch-icon.png",
        "https://www.kaust.edu.sa/favicon.ico",
    ]),
    "Khalifa University": ("khalifa", [
        "https://www.ku.ac.ae/apple-touch-icon.png",
        "https://www.ku.ac.ae/favicon.ico",
    ]),
    "Masdar": ("masdar", [
        "https://masdar.ae/apple-touch-icon.png",
        "https://masdar.ae/favicon.ico",
    ]),
    "MBZUAI": ("mbzuai", [
        "https://mbzuai.ac.ae/apple-touch-icon.png",
        "https://mbzuai.ac.ae/favicon.ico",
    ]),
    "Mubadala": ("mubadala", [
        "https://www.mubadala.com/apple-touch-icon.png",
        "https://www.mubadala.com/favicon.ico",
    ]),
    "Presight": ("presight", [
        "https://www.presight.ai/apple-touch-icon.png",
        "https://presight.ai/apple-touch-icon.png",
        "https://presight.ai/favicon.ico",
    ]),
    "Saudi Arabia": ("saudi", [
        "https://www.my.gov.sa/apple-touch-icon.png",
        "https://www.my.gov.sa/favicon.ico",
    ]),
    "SDAIA": ("sdaia", [
        "https://sdaia.gov.sa/apple-touch-icon.png",
        "https://sdaia.gov.sa/en/favicon.ico",
    ]),
    "TII": ("tii", [
        "https://www.tii.ae/apple-touch-icon.png",
        "https://tii.ae/apple-touch-icon.png",
        "https://tii.ae/favicon.ico",
    ]),
    "UAE Government": ("uae", [
        "https://u.ae/apple-touch-icon.png",
        "https://u.ae/favicon.ico",
    ]),
    # ── Global AI/tech ─────────────────────────────────────────────────
    "Amazon": ("amazon", [
        "https://www.amazon.com/apple-touch-icon.png",
        "https://www.aboutamazon.com/apple-touch-icon.png",
    ]),
    "AMD": ("amd", [
        "https://www.amd.com/apple-touch-icon.png",
        "https://www.amd.com/favicon.ico",
    ]),
    "Anthropic": ("anthropic", [
        "https://www.anthropic.com/apple-touch-icon.png",
        "https://anthropic.com/apple-touch-icon.png",
    ]),
    "Apple": ("apple", [
        "https://www.apple.com/apple-touch-icon.png",
    ]),
    "Baidu": ("baidu", [
        "https://www.baidu.com/favicon.ico",
    ]),
    "Broadcom": ("broadcom", [
        "https://www.broadcom.com/apple-touch-icon.png",
        "https://www.broadcom.com/favicon.ico",
    ]),
    "ByteDance": ("bytedance", [
        "https://www.bytedance.com/apple-touch-icon.png",
        "https://www.bytedance.com/favicon.ico",
    ]),
    "Cerebras": ("cerebras", [
        "https://www.cerebras.ai/apple-touch-icon.png",
        "https://cerebras.ai/apple-touch-icon.png",
    ]),
    "Cohere": ("cohere", [
        "https://cohere.com/apple-touch-icon.png",
        "https://cohere.com/favicon.ico",
    ]),
    "DeepSeek": ("deepseek", [
        "https://www.deepseek.com/apple-touch-icon.png",
        "https://www.deepseek.com/favicon.ico",
    ]),
    "Google": ("google", [
        "https://www.google.com/images/branding/googleg/1x/googleg_standard_color_128dp.png",
        "https://www.google.com/favicon.ico",
    ]),
    "Google DeepMind": ("deepmind", [
        "https://deepmind.google/apple-touch-icon.png",
        "https://deepmind.google/favicon.ico",
    ]),
    "Groq": ("groq", [
        "https://groq.com/apple-touch-icon.png",
        "https://groq.com/favicon.ico",
    ]),
    "Hugging Face": ("huggingface", [
        "https://huggingface.co/apple-touch-icon.png",
        "https://huggingface.co/favicon.ico",
    ]),
    "Intel": ("intel", [
        "https://www.intel.com/apple-touch-icon.png",
        "https://www.intel.com/favicon.ico",
    ]),
    "Meta": ("meta", [
        "https://about.meta.com/apple-touch-icon.png",
        "https://about.fb.com/apple-touch-icon.png",
    ]),
    "Microsoft": ("microsoft", [
        "https://www.microsoft.com/apple-touch-icon.png",
        "https://www.microsoft.com/favicon.ico",
    ]),
    "Mistral": ("mistral", [
        "https://mistral.ai/apple-touch-icon.png",
        "https://mistral.ai/favicon.ico",
    ]),
    "NVIDIA": ("nvidia", [
        "https://www.nvidia.com/apple-touch-icon.png",
        "https://www.nvidia.com/favicon.ico",
    ]),
    "OpenAI": ("openai", [
        "https://openai.com/apple-touch-icon.png",
        "https://openai.com/favicon.ico",
    ]),
    "Samsung": ("samsung", [
        "https://www.samsung.com/apple-touch-icon.png",
        "https://www.samsung.com/favicon.ico",
    ]),
    "Scale AI": ("scaleai", [
        "https://scale.com/apple-touch-icon.png",
        "https://scale.com/favicon.ico",
    ]),
    "Tencent": ("tencent", [
        "https://www.tencent.com/apple-touch-icon.png",
        "https://www.tencent.com/en-us/favicon.ico",
    ]),
    "Together AI": ("together", [
        "https://www.together.ai/apple-touch-icon.png",
        "https://together.ai/apple-touch-icon.png",
    ]),
    "TSMC": ("tsmc", [
        "https://www.tsmc.com/apple-touch-icon.png",
        "https://www.tsmc.com/favicon.ico",
    ]),
    "xAI": ("xai", [
        "https://x.ai/apple-touch-icon.png",
        "https://x.ai/favicon.ico",
    ]),
    "Zhipu AI": ("zhipu", [
        "https://www.zhipuai.cn/apple-touch-icon.png",
        "https://zhipuai.cn/favicon.ico",
    ]),
}


def _extension_from_url(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    if path.endswith(".svg"):
        return ".svg"
    if path.endswith(".ico"):
        return ".ico"
    if path.endswith(".jpg") or path.endswith(".jpeg"):
        return ".jpg"
    return ".png"


def _content_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".svg"):
        return "image/svg+xml"
    if lower.endswith(".ico"):
        return "image/x-icon"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    return "image/png"


def download_logo(stem: str, urls: list[str]) -> Path | None:
    """Try each URL in order. Returns the saved file path on success."""
    with httpx.Client(
        follow_redirects=True,
        timeout=15,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for url in urls:
            try:
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


def upload_to_storage(sb, file_path: Path) -> bool:
    filename = file_path.name
    try:
        data = file_path.read_bytes()
        sb.storage.from_(BUCKET).upload(
            filename,
            data,
            {"content-type": _content_type(filename), "upsert": "true"},
        )
        print(f"    ⬆️  uploaded {filename}")
        return True
    except Exception as e:
        msg = str(e)
        if "Duplicate" in msg or "already exists" in msg.lower():
            print(f"    ⬆️  {filename} already in storage (overwriting not supported; fine)")
            return True
        print(f"    ❌ upload failed: {e}")
        return False


def update_db_logo_path(sb, entity_name: str, logo_path: str) -> bool:
    try:
        sb.table("entity_logos").update({"logo_path": logo_path}).eq(
            "entity_name", entity_name
        ).execute()
        print(f"    💾 entity_logos.logo_path = {logo_path}")
        return True
    except Exception as e:
        print(f"    ❌ DB update failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Process only this entity (case-insensitive)")
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

    successes: list[str] = []
    failures: list[str] = []

    entities = ENTITY_SOURCES.items()
    if args.only:
        needle = args.only.strip().lower()
        entities = [
            (name, src)
            for name, src in ENTITY_SOURCES.items()
            if needle in name.lower() or needle in src[0].lower()
        ]
        if not entities:
            print(f"No entities matching --only={args.only}")
            sys.exit(1)

    for entity_name, (stem, urls) in entities:
        print(f"\n🔸 {entity_name}")
        downloaded = download_logo(stem, urls)
        if not downloaded:
            failures.append(entity_name)
            continue

        if args.dry_run:
            print("    (dry run — not uploading)")
            successes.append(entity_name)
            time.sleep(0.2)
            continue

        if not upload_to_storage(sb, downloaded):
            failures.append(entity_name)
            continue

        if not update_db_logo_path(sb, entity_name, downloaded.name):
            failures.append(entity_name)
            continue

        successes.append(entity_name)
        time.sleep(0.3)  # polite pacing

    print("\n" + "=" * 60)
    print(f"✅ {len(successes)} succeeded")
    print(f"❌ {len(failures)} failed")
    if failures:
        print("Failed entities:")
        for name in failures:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
