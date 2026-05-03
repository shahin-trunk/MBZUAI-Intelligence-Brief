#!/usr/bin/env python3
"""Source, generate, and upload entity logos to Supabase Storage.

Usage:
    python3.11 source_entity_logos.py           # Full run: generate + download + upload
    python3.11 source_entity_logos.py --fallbacks-only  # Only generate + upload fallback SVGs
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

GOLD = "#D4A843"

# ── Fallback SVGs ──────────────────────────────────────────────────────────

FALLBACK_SVGS = {
    "fallback-government.svg": f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <path d="M256 48l192 96v32H64v-32L256 48z" fill="{GOLD}" opacity="0.9"/>
  <rect x="96" y="192" width="48" height="192" rx="4" fill="{GOLD}" opacity="0.7"/>
  <rect x="184" y="192" width="48" height="192" rx="4" fill="{GOLD}" opacity="0.7"/>
  <rect x="280" y="192" width="48" height="192" rx="4" fill="{GOLD}" opacity="0.7"/>
  <rect x="368" y="192" width="48" height="192" rx="4" fill="{GOLD}" opacity="0.7"/>
  <rect x="64" y="384" width="384" height="48" rx="4" fill="{GOLD}" opacity="0.9"/>
</svg>""",
    "fallback-university.svg": f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <path d="M256 64L64 192l192 96 192-96L256 64z" fill="{GOLD}" opacity="0.9"/>
  <path d="M128 224v128l128 64 128-64V224" fill="none" stroke="{GOLD}" stroke-width="24" opacity="0.7"/>
  <line x1="64" y1="192" x2="64" y2="384" stroke="{GOLD}" stroke-width="16" opacity="0.6"/>
  <circle cx="64" cy="384" r="16" fill="{GOLD}" opacity="0.6"/>
</svg>""",
    "fallback-company.svg": f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect x="128" y="96" width="256" height="352" rx="8" fill="{GOLD}" opacity="0.2"/>
  <rect x="128" y="96" width="256" height="352" rx="8" fill="none" stroke="{GOLD}" stroke-width="16" opacity="0.8"/>
  <rect x="176" y="152" width="48" height="48" rx="4" fill="{GOLD}" opacity="0.5"/>
  <rect x="288" y="152" width="48" height="48" rx="4" fill="{GOLD}" opacity="0.5"/>
  <rect x="176" y="248" width="48" height="48" rx="4" fill="{GOLD}" opacity="0.5"/>
  <rect x="288" y="248" width="48" height="48" rx="4" fill="{GOLD}" opacity="0.5"/>
  <rect x="216" y="344" width="80" height="104" rx="4" fill="{GOLD}" opacity="0.7"/>
</svg>""",
    "fallback-energy.svg": f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <path d="M320 48L176 256h96L208 464l176-240h-96L320 48z" fill="{GOLD}" opacity="0.85"/>
</svg>""",
    "fallback-finance.svg": f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect x="80" y="288" width="72" height="160" rx="4" fill="{GOLD}" opacity="0.6"/>
  <rect x="176" y="208" width="72" height="240" rx="4" fill="{GOLD}" opacity="0.7"/>
  <rect x="272" y="128" width="72" height="320" rx="4" fill="{GOLD}" opacity="0.8"/>
  <rect x="368" y="176" width="72" height="272" rx="4" fill="{GOLD}" opacity="0.9"/>
  <line x1="64" y1="448" x2="448" y2="448" stroke="{GOLD}" stroke-width="8" opacity="0.4"/>
</svg>""",
    "fallback-defense.svg": f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <path d="M256 48C176 48 96 80 96 80v192c0 128 160 192 160 192s160-64 160-192V80S336 48 256 48z"
        fill="{GOLD}" opacity="0.2"/>
  <path d="M256 48C176 48 96 80 96 80v192c0 128 160 192 160 192s160-64 160-192V80S336 48 256 48z"
        fill="none" stroke="{GOLD}" stroke-width="16" opacity="0.8"/>
  <path d="M256 176l24 48 53 8-38 37 9 53-48-25-48 25 9-53-38-37 53-8z" fill="{GOLD}" opacity="0.7"/>
</svg>""",
    "fallback-other.svg": f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <circle cx="256" cy="256" r="192" fill="none" stroke="{GOLD}" stroke-width="16" opacity="0.8"/>
  <ellipse cx="256" cy="256" rx="80" ry="192" fill="none" stroke="{GOLD}" stroke-width="12" opacity="0.5"/>
  <line x1="64" y1="256" x2="448" y2="256" stroke="{GOLD}" stroke-width="12" opacity="0.4"/>
  <path d="M96 176h320" stroke="{GOLD}" stroke-width="8" opacity="0.3"/>
  <path d="M96 336h320" stroke="{GOLD}" stroke-width="8" opacity="0.3"/>
</svg>""",
}

# ── Logo Sources ───────────────────────────────────────────────────────────

# Maps entity key → list of URLs to try (first success wins)
LOGO_SOURCES: dict[str, list[str]] = {
    "openai": [
        "https://cdn.openai.com/API/logo-assets/openai-logomark.png",
        "https://openai.com/apple-touch-icon.png",
    ],
    "anthropic": [
        "https://anthropic.com/apple-touch-icon.png",
        "https://www.anthropic.com/favicon.ico",
    ],
    "google": [
        "https://www.google.com/images/branding/googleg/1x/googleg_standard_color_128dp.png",
        "https://www.google.com/apple-touch-icon.png",
    ],
    "deepmind": [
        "https://deepmind.google/apple-touch-icon.png",
    ],
    "nvidia": [
        "https://www.nvidia.com/apple-touch-icon.png",
    ],
    "meta": [
        "https://about.meta.com/brand/resources/facebookapp/logo/apple-touch-icon.png",
        "https://about.meta.com/apple-touch-icon.png",
    ],
    "microsoft": [
        "https://www.microsoft.com/apple-touch-icon.png",
    ],
    "apple": [
        "https://www.apple.com/apple-touch-icon.png",
    ],
    "amazon": [
        "https://www.amazon.com/apple-touch-icon.png",
    ],
    "mistral": [
        "https://mistral.ai/apple-touch-icon.png",
    ],
    "xai": [
        "https://x.ai/apple-touch-icon.png",
    ],
    "cohere": [
        "https://cohere.com/apple-touch-icon.png",
    ],
    "huggingface": [
        "https://huggingface.co/apple-touch-icon.png",
        "https://huggingface.co/front/assets/huggingface_logo.svg",
    ],
    "tsmc": [
        "https://www.tsmc.com/apple-touch-icon.png",
    ],
    "samsung": [
        "https://www.samsung.com/apple-touch-icon.png",
    ],
    "intel": [
        "https://www.intel.com/apple-touch-icon.png",
    ],
    "amd": [
        "https://www.amd.com/apple-touch-icon.png",
    ],
    "cerebras": [
        "https://cerebras.ai/apple-touch-icon.png",
    ],
    "groq": [
        "https://groq.com/apple-touch-icon.png",
    ],
    "together": [
        "https://www.together.ai/apple-touch-icon.png",
    ],
    "scaleai": [
        "https://scale.com/apple-touch-icon.png",
    ],
    "deepseek": [
        "https://www.deepseek.com/apple-touch-icon.png",
    ],
    "tencent": [
        "https://www.tencent.com/apple-touch-icon.png",
    ],
    "baidu": [
        "https://www.baidu.com/apple-touch-icon.png",
    ],
    "bytedance": [
        "https://www.bytedance.com/apple-touch-icon.png",
    ],
}

# Entity key → filename in seed_entity_logos.py
ENTITY_KEY_TO_FILE: dict[str, str] = {
    "openai": "openai.png",
    "anthropic": "anthropic.png",
    "google": "google.png",
    "deepmind": "deepmind.png",
    "nvidia": "nvidia.png",
    "meta": "meta.png",
    "microsoft": "microsoft.png",
    "apple": "apple.png",
    "amazon": "amazon.png",
    "mistral": "mistral.png",
    "xai": "xai.png",
    "cohere": "cohere.png",
    "huggingface": "huggingface.png",
    "tsmc": "tsmc.png",
    "samsung": "samsung.png",
    "intel": "intel.png",
    "amd": "amd.png",
    "cerebras": "cerebras.png",
    "groq": "groq.png",
    "together": "together.png",
    "scaleai": "scaleai.png",
    "deepseek": "deepseek.png",
    "tencent": "tencent.png",
    "baidu": "baidu.png",
    "bytedance": "bytedance.png",
}


def generate_initial_letter_svg(letter: str, filename: str) -> None:
    """Generate a simple initial-letter SVG as placeholder."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect width="512" height="512" rx="64" fill="#1a1a1a"/>
  <text x="256" y="320" text-anchor="middle" font-family="system-ui,sans-serif"
        font-size="280" font-weight="700" fill="{GOLD}">{letter.upper()}</text>
</svg>"""
    (LOGOS_DIR / filename.replace(".png", ".svg")).write_text(svg)


def download_logo(entity_key: str, urls: list[str]) -> bool:
    """Try downloading a logo from the given URLs. Returns True on success."""
    filename = ENTITY_KEY_TO_FILE.get(entity_key)
    if not filename:
        return False

    filepath = LOGOS_DIR / filename
    if filepath.exists():
        print(f"  {entity_key}: already exists, skipping")
        return True

    for url in urls:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            if resp.status_code == 200 and len(resp.content) > 100:
                filepath.write_bytes(resp.content)
                print(f"  {entity_key}: downloaded from {url} ({len(resp.content)} bytes)")
                return True
        except Exception as e:
            print(f"  {entity_key}: failed {url} ({e})")
            continue

    # Fallback: generate initial letter SVG
    letter = entity_key[0]
    svg_name = filename.replace(".png", ".svg")
    generate_initial_letter_svg(letter, svg_name)
    print(f"  {entity_key}: generated letter placeholder ({svg_name})")
    return False


def upload_to_storage(sb, filepath: Path) -> str | None:
    """Upload a file to entity-logos bucket. Returns the storage path."""
    filename = filepath.name
    content_type = "image/svg+xml" if filename.endswith(".svg") else "image/png"

    try:
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        sb.storage.from_("entity-logos").upload(
            filename, file_bytes,
            {"content-type": content_type, "upsert": "true"},
        )
        print(f"  Uploaded: {filename}")
        return filename
    except Exception as e:
        # May already exist
        if "Duplicate" in str(e) or "already exists" in str(e):
            print(f"  {filename}: already in storage")
            return filename
        print(f"  Upload failed for {filename}: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fallbacks-only", action="store_true")
    args = parser.parse_args()

    for env_path in load_project_env():
        print(f"Loaded env from {env_path}")

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing Supabase credentials")
        sys.exit(1)

    sb = create_client(url, key)

    # Step 1: Generate fallback SVGs
    print("\n=== Generating fallback SVGs ===")
    for name, svg_content in FALLBACK_SVGS.items():
        path = LOGOS_DIR / name
        path.write_text(svg_content.strip())
        print(f"  Generated: {name}")

    # Step 2: Download logos (unless --fallbacks-only)
    if not args.fallbacks_only:
        print("\n=== Downloading logos from web ===")
        success = 0
        for entity_key, urls in LOGO_SOURCES.items():
            if download_logo(entity_key, urls):
                success += 1
            time.sleep(0.3)  # Rate limiting
        print(f"\n  Downloaded {success}/{len(LOGO_SOURCES)} logos")

    # Step 3: Upload all files to Supabase Storage
    print("\n=== Uploading to Supabase Storage ===")
    uploaded = 0
    for filepath in sorted(LOGOS_DIR.iterdir()):
        if filepath.suffix in (".png", ".svg", ".ico", ".jpg"):
            result = upload_to_storage(sb, filepath)
            if result:
                uploaded += 1

    print(f"\n  Uploaded {uploaded} files total")

    # Step 4: Update entity_logos table with actual logo paths
    print("\n=== Updating entity_logos table ===")
    for entity_key, filename in ENTITY_KEY_TO_FILE.items():
        # Check if we have the actual file or an SVG fallback
        if (LOGOS_DIR / filename).exists():
            actual_path = filename
        elif (LOGOS_DIR / filename.replace(".png", ".svg")).exists():
            actual_path = filename.replace(".png", ".svg")
        else:
            continue

        try:
            sb.table("entity_logos").update(
                {"logo_path": actual_path}
            ).eq("entity_name", entity_key.upper()).execute()
            # Also try common casing
            sb.table("entity_logos").update(
                {"logo_path": actual_path}
            ).ilike("entity_name", entity_key).execute()
        except Exception:
            pass

    print("\nDone!")


if __name__ == "__main__":
    main()
