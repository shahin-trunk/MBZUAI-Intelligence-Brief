#!/usr/bin/env python3
"""Audit every file currently in the entity-logos bucket, identify the
ones that are HTML error pages masquerading as images (byte signature
check), delete them, and re-download from alternate sources with the
same validator enforced.

Many Pass 1 downloads looked successful (HTTP 200, >1KB) but actually
returned HTML instead of the requested apple-touch-icon. This pass
enforces an image-signature check and only accepts bytes that start
with PNG, ICO, JPEG, GIF, or WebP magic numbers (or a valid SVG root).

Usage:
    python3 backend/validate_and_repair_logos.py            # full audit + repair
    python3 backend/validate_and_repair_logos.py --audit    # report only, no changes
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
# Wikimedia requires a specific UA format (ProductName/Version ContactInfo)
# per https://meta.wikimedia.org/wiki/User-Agent_policy. Unrecognized UAs
# get 429s.
WIKIMEDIA_USER_AGENT = (
    "MBZUAIIntelligenceDashboardLogoFetcher/1.0 "
    "(https://mbzuai.ac.ae; admin@mbzuai.ac.ae) httpx/0.27"
)


def _ua_for_url(url: str) -> str:
    host = url.split("/", 3)[2] if "://" in url else ""
    if "wikimedia" in host or "wikipedia" in host:
        return WIKIMEDIA_USER_AGENT
    return USER_AGENT


# ── Image signature validation ─────────────────────────────────────────────

def detect_image_kind(data: bytes) -> str | None:
    """Return 'png' | 'jpeg' | 'gif' | 'webp' | 'ico' | 'svg' | None."""
    if len(data) < 8:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:4] == b"\x00\x00\x01\x00":
        return "ico"
    # SVG: check the first ~500 bytes for an <svg> root (with or without XML prolog)
    head = data[:512].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        if b"<svg" in data[:2048]:
            return "svg"
    return None


def extension_for(kind: str) -> str:
    return {
        "png": ".png",
        "jpeg": ".jpg",
        "gif": ".gif",
        "webp": ".webp",
        "ico": ".ico",
        "svg": ".svg",
    }[kind]


def content_type_for(kind: str) -> str:
    return {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "ico": "image/x-icon",
        "svg": "image/svg+xml",
    }[kind]


# ── Sources per entity ─────────────────────────────────────────────────────
# One canonical filename stem per entity. Multiple URLs to try in order.
# Only includes the 47 entities in entity_logos. Fallback-*.svg files live
# separately and are not touched by this script.
SOURCES: dict[str, tuple[str, list[str]]] = {
    "Abu Dhabi Government": ("abudhabi", [
        "https://www.abudhabi.ae/apple-touch-icon.png",
        "https://u.ae/apple-touch-icon.png",
        "https://www.google.com/s2/favicons?domain=abudhabi.ae&sz=128",
    ]),
    "ADIA": ("adia", [
        "https://www.adia.ae/apple-touch-icon.png",
        "https://www.adia.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=adia.ae&sz=128",
    ]),
    "ADNOC": ("adnoc", [
        "https://www.adnoc.ae/apple-touch-icon.png",
        "https://www.adnoc.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=adnoc.ae&sz=128",
    ]),
    "ADQ": ("adq", [
        "https://www.adq.ae/apple-touch-icon.png",
        "https://www.adq.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=adq.ae&sz=128",
    ]),
    "Amazon": ("amazon", [
        "https://www.amazon.com/apple-touch-icon.png",
        "https://www.google.com/s2/favicons?domain=amazon.com&sz=128",
    ]),
    "AMD": ("amd", [
        "https://icons.duckduckgo.com/ip3/amd.com.ico",
        "https://www.amd.com/content/dam/amd/en/images/logos/amd-logo-300x300.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/AMD_Logo.svg/512px-AMD_Logo.svg.png",
    ]),
    "Anthropic": ("anthropic", [
        "https://claude.ai/apple-touch-icon.png",
        "https://www.google.com/s2/favicons?domain=anthropic.com&sz=128",
    ]),
    "Apple": ("apple", [
        "https://www.apple.com/apple-touch-icon.png",
        "https://www.google.com/s2/favicons?domain=apple.com&sz=128",
    ]),
    "ASPIRE": ("aspire", [
        "https://aspireuae.com/wp-content/uploads/2023/03/aspire-logo.png",
        "https://aspireuae.com/wp-content/themes/aspire/assets/images/logo.png",
        "https://aspireuae.com/logo.png",
        "https://icons.duckduckgo.com/ip3/aspireuae.com.ico",
        "https://icons.duckduckgo.com/ip3/aspire.atrc.ae.ico",
        "https://aspireuae.com/apple-touch-icon.png",
    ]),
    "ATRC": ("atrc", [
        "https://atrc.ae/apple-touch-icon.png",
        "https://atrc.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=atrc.ae&sz=128",
    ]),
    "Baidu": ("baidu", [
        "https://www.baidu.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=baidu.com&sz=128",
    ]),
    "Broadcom": ("broadcom", [
        "https://www.google.com/s2/favicons?domain=broadcom.com&sz=128",
    ]),
    "ByteDance": ("bytedance", [
        "https://icons.duckduckgo.com/ip3/bytedance.com.ico",
        "https://p16-capcut-sign-va.ibyteimg.com/tos-maliva-i-ejpugu1e9q-us/7b61a3f1c8384d7f94cf2dc20a4b8f9c~tplv-ejpugu1e9q-image.image",
        "https://www.google.com/s2/favicons?domain=tiktok.com&sz=128",
    ]),
    "Cerebras": ("cerebras", [
        "https://www.google.com/s2/favicons?domain=cerebras.net&sz=128",
        "https://www.google.com/s2/favicons?domain=cerebras.ai&sz=128",
    ]),
    "Cohere": ("cohere", [
        "https://cohere.com/apple-touch-icon.png",
        "https://www.google.com/s2/favicons?domain=cohere.com&sz=128",
    ]),
    "Core42": ("core42", [
        "https://core42.ai/apple-touch-icon.png",
        "https://core42.ai/favicon.ico",
        "https://www.google.com/s2/favicons?domain=core42.ai&sz=128",
    ]),
    "DeepSeek": ("deepseek", [
        "https://www.deepseek.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=deepseek.com&sz=128",
    ]),
    "DEWA": ("dewa", [
        "https://www.dewa.gov.ae/apple-touch-icon.png",
        "https://www.dewa.gov.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=dewa.gov.ae&sz=128",
    ]),
    "Firmus": ("firmus", [
        "https://firmus.energy/apple-touch-icon.png",
        "https://firmus.energy/favicon.ico",
        "https://www.google.com/s2/favicons?domain=firmus.energy&sz=128",
    ]),
    "G42": ("g42", [
        "https://www.g42.ai/apple-touch-icon.png",
        "https://g42.ai/favicon.ico",
        "https://www.google.com/s2/favicons?domain=g42.ai&sz=128",
    ]),
    "Google": ("google", [
        "https://www.google.com/images/branding/googleg/1x/googleg_standard_color_128dp.png",
        "https://www.google.com/s2/favicons?domain=google.com&sz=128",
    ]),
    "Google DeepMind": ("deepmind", [
        "https://deepmind.google/favicon.ico",
        "https://www.google.com/s2/favicons?domain=deepmind.google&sz=128",
    ]),
    "Groq": ("groq", [
        "https://groq.com/apple-touch-icon.png",
        "https://www.google.com/s2/favicons?domain=groq.com&sz=128",
    ]),
    "Hugging Face": ("huggingface", [
        "https://huggingface.co/favicon.ico",
        "https://www.google.com/s2/favicons?domain=huggingface.co&sz=128",
    ]),
    "Intel": ("intel", [
        "https://www.intel.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=intel.com&sz=128",
    ]),
    "KAUST": ("kaust", [
        "https://www.kaust.edu.sa/apple-touch-icon.png",
        "https://www.kaust.edu.sa/favicon.ico",
        "https://www.google.com/s2/favicons?domain=kaust.edu.sa&sz=128",
    ]),
    "Khalifa University": ("khalifa", [
        "https://www.ku.ac.ae/apple-touch-icon.png",
        "https://www.ku.ac.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=ku.ac.ae&sz=128",
    ]),
    "Masdar": ("masdar", [
        "https://masdar.ae/apple-touch-icon.png",
        "https://masdar.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=masdar.ae&sz=128",
    ]),
    "MBZUAI": ("mbzuai", [
        "https://mbzuai.ac.ae/apple-touch-icon.png",
        "https://mbzuai.ac.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=mbzuai.ac.ae&sz=128",
    ]),
    "Meta": ("meta", [
        "https://about.meta.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=meta.com&sz=128",
    ]),
    "Microsoft": ("microsoft", [
        "https://www.microsoft.com/apple-touch-icon.png",
        "https://www.google.com/s2/favicons?domain=microsoft.com&sz=128",
    ]),
    "Mistral": ("mistral", [
        "https://mistral.ai/apple-touch-icon.png",
        "https://www.google.com/s2/favicons?domain=mistral.ai&sz=128",
    ]),
    "Mubadala": ("mubadala", [
        "https://www.mubadala.com/apple-touch-icon.png",
        "https://www.mubadala.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=mubadala.com&sz=128",
    ]),
    "NVIDIA": ("nvidia", [
        "https://www.nvidia.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=nvidia.com&sz=128",
    ]),
    "OpenAI": ("openai", [
        "https://openai.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=openai.com&sz=128",
    ]),
    "Presight": ("presight", [
        "https://www.presight.ai/apple-touch-icon.png",
        "https://presight.ai/favicon.ico",
        "https://www.google.com/s2/favicons?domain=presight.ai&sz=128",
    ]),
    "Samsung": ("samsung", [
        "https://images.samsung.com/is/image/samsung/assets/global/about-us/brand/logo/mo/360_197_1.png",
        "https://www.google.com/s2/favicons?domain=samsung.com&sz=128",
    ]),
    "Saudi Arabia": ("saudi", [
        "https://www.my.gov.sa/apple-touch-icon.png",
        "https://www.my.gov.sa/favicon.ico",
        "https://www.google.com/s2/favicons?domain=my.gov.sa&sz=128",
    ]),
    "Scale AI": ("scaleai", [
        "https://scale.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=scale.com&sz=128",
    ]),
    "SDAIA": ("sdaia", [
        # Wikipedia infobox image (Arabic-titled SVG, rendered to PNG by
        # Wikimedia's thumb service). Found via REST API page summary.
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/%D8%B4%D8%B9%D8%A7%D8%B1_%D8%A7%D9%84%D9%87%D9%8A%D8%A6%D8%A9_%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9_%D9%84%D9%84%D8%A8%D9%8A%D8%A7%D9%86%D8%A7%D8%AA_%D9%88%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1_%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A_SDAIA.svg/330px-%D8%B4%D8%B9%D8%A7%D8%B1_%D8%A7%D9%84%D9%87%D9%8A%D8%A6%D8%A9_%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9_%D9%84%D9%84%D8%A8%D9%8A%D8%A7%D9%86%D8%A7%D8%AA_%D9%88%D8%A7%D9%84%D8%B0%D9%83%D8%A7%D8%A1_%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A_SDAIA.svg.png",
    ]),
    "Tencent": ("tencent", [
        "https://www.tencent.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=tencent.com&sz=128",
    ]),
    "TII": ("tii", [
        "https://www.tii.ae/apple-touch-icon.png",
        "https://www.tii.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=tii.ae&sz=128",
    ]),
    "Together AI": ("together", [
        "https://www.google.com/s2/favicons?domain=together.ai&sz=128",
    ]),
    "TSMC": ("tsmc", [
        "https://www.tsmc.com/favicon.ico",
        "https://www.google.com/s2/favicons?domain=tsmc.com&sz=128",
    ]),
    "UAE Government": ("uae", [
        "https://u.ae/apple-touch-icon.png",
        "https://u.ae/favicon.ico",
        "https://www.google.com/s2/favicons?domain=u.ae&sz=128",
    ]),
    "xAI": ("xai", [
        "https://x.ai/apple-touch-icon.png",
        "https://x.ai/favicon.ico",
        "https://www.google.com/s2/favicons?domain=x.ai&sz=128",
    ]),
    "Zhipu AI": ("zhipu", [
        "https://www.google.com/s2/favicons?domain=zhipuai.cn&sz=128",
        "https://www.google.com/s2/favicons?domain=bigmodel.cn&sz=128",
    ]),
}


# ── Helpers ────────────────────────────────────────────────────────────────

def download_and_validate(stem: str, urls: list[str]) -> tuple[Path, str] | None:
    """Try each URL, return (saved_path, kind) for the first one whose
    bytes have a valid image signature. None if all fail."""
    with httpx.Client(follow_redirects=True, timeout=15) as client:
        for url in urls:
            try:
                resp = client.get(url, headers={"User-Agent": _ua_for_url(url)})
            except Exception as e:
                print(f"    ❌ {url} — {type(e).__name__}")
                continue
            if resp.status_code != 200:
                print(f"    ❌ {url} — HTTP {resp.status_code}")
                continue
            if len(resp.content) < 200:
                print(f"    ❌ {url} — too small ({len(resp.content)} bytes)")
                continue
            kind = detect_image_kind(resp.content)
            if not kind:
                head_preview = resp.content[:32].decode("ascii", errors="replace").replace("\n", " ")
                print(f"    ❌ {url} — not an image ({len(resp.content)} bytes, head: {head_preview!r})")
                continue
            ext = extension_for(kind)
            filename = f"{stem}{ext}"
            path = LOGOS_DIR / filename
            path.write_bytes(resp.content)
            print(f"    ✅ {url} → {filename} ({kind}, {len(resp.content)} bytes)")
            return path, kind
    return None


def upload(sb, file_path: Path, kind: str) -> bool:
    try:
        data = file_path.read_bytes()
        sb.storage.from_(BUCKET).upload(
            file_path.name,
            data,
            {"content-type": content_type_for(kind), "upsert": "true"},
        )
        print(f"    ⬆️  uploaded {file_path.name}")
        return True
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "already exists" in msg:
            # Retry with remove+upload to overwrite
            try:
                sb.storage.from_(BUCKET).remove([file_path.name])
                data = file_path.read_bytes()
                sb.storage.from_(BUCKET).upload(
                    file_path.name,
                    data,
                    {"content-type": content_type_for(kind)},
                )
                print(f"    ⬆️  overwrote {file_path.name}")
                return True
            except Exception as e2:
                print(f"    ❌ overwrite failed: {e2}")
                return False
        print(f"    ❌ upload failed: {e}")
        return False


def update_db(sb, entity_name: str, logo_path: str) -> bool:
    try:
        sb.table("entity_logos").update({"logo_path": logo_path}).eq(
            "entity_name", entity_name
        ).execute()
        print(f"    💾 entity_logos.logo_path = {logo_path}")
        return True
    except Exception as e:
        print(f"    ❌ DB update failed: {e}")
        return False


def audit_storage(sb) -> dict[str, str]:
    """Return {entity_name: current_logo_path} from the DB."""
    rows = sb.table("entity_logos").select("entity_name, logo_path").execute().data
    return {r["entity_name"]: r["logo_path"] for r in rows or []}


def check_existing(public_base: str, logo_path: str) -> str:
    """Fetch the first few KB of an existing storage file and classify it.
    Returns 'valid:{kind}', 'invalid:html', 'invalid:empty', or 'missing'."""
    url = f"{public_base}/storage/v1/object/public/{BUCKET}/{logo_path}"
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(url)
    except Exception:
        return "missing"
    if resp.status_code != 200:
        return "missing"
    data = resp.content
    if len(data) < 16:
        return "invalid:empty"
    kind = detect_image_kind(data)
    if kind:
        return f"valid:{kind}"
    head = data[:32].decode("ascii", errors="replace")
    if "<!DOCTYPE" in head.upper() or "<HTML" in head.upper() or head.lstrip().startswith("<"):
        return "invalid:html"
    return "invalid:unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true", help="Report only, no changes")
    parser.add_argument("--only", help="Process only this entity (case-insensitive substring)")
    parser.add_argument(
        "--force",
        nargs="+",
        help="Force repair of these entity names even if their file is valid "
        "(useful when the DB points at the wrong filename)",
    )
    args = parser.parse_args()

    for env_path in load_project_env():
        print(f"env: loaded {env_path}")

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    sb = create_client(url, key)

    print("\n=== Auditing current storage state ===\n")
    current = audit_storage(sb)
    broken: list[str] = []
    ok: list[str] = []
    fallbacks: list[str] = []

    for entity_name in sorted(current):
        logo_path = current[entity_name]
        if not logo_path or logo_path.startswith("fallback"):
            fallbacks.append(entity_name)
            continue
        status = check_existing(url, logo_path)
        marker = "✅" if status.startswith("valid") else "❌"
        print(f"  {marker} {entity_name:30s} {logo_path:25s} → {status}")
        if status.startswith("valid"):
            ok.append(entity_name)
        else:
            broken.append(entity_name)

    print()
    print(f"  {len(ok)} valid, {len(broken)} broken, {len(fallbacks)} fallback")

    if args.audit:
        print("\n(audit-only mode, skipping repair)")
        return

    # Repair broken ones + any forced entities
    targets = list(broken)
    if args.force:
        for name in args.force:
            if name in current and name not in targets:
                targets.append(name)
                print(f"  🔧 forcing repair of {name} (currently {current[name]})")
    if args.only:
        needle = args.only.lower()
        targets = [n for n in targets if needle in n.lower()]

    if not targets:
        print("\n✨ Nothing to repair")
        return

    print(f"\n=== Repairing {len(targets)} broken entities ===\n")

    repaired: list[str] = []
    still_broken: list[str] = []

    for entity_name in targets:
        if entity_name not in SOURCES:
            print(f"\n🔸 {entity_name} — no sources defined, skipping")
            still_broken.append(entity_name)
            continue
        stem, urls = SOURCES[entity_name]
        print(f"\n🔸 {entity_name}")
        result = download_and_validate(stem, urls)
        if not result:
            still_broken.append(entity_name)
            continue
        path, kind = result
        if not upload(sb, path, kind):
            still_broken.append(entity_name)
            continue
        if not update_db(sb, entity_name, path.name):
            still_broken.append(entity_name)
            continue
        repaired.append(entity_name)
        time.sleep(0.3)

    print("\n" + "=" * 60)
    print(f"✅ {len(repaired)} repaired")
    print(f"❌ {len(still_broken)} still broken")
    if still_broken:
        print("Still broken:")
        for name in still_broken:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
