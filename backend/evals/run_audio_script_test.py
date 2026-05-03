#!/usr/bin/env python3.11
"""Generate an audio script only — no TTS, no Supabase writes.

Tests the podcast_script_prompt voice without any production side
effects. Loads a local brief JSON (backend/output/brief_{date}.json)
and runs the English script generator.

Usage:
    cd backend && python -m evals.run_audio_script_test --date 2026-04-09
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

for p in [REPO_ROOT / ".env", REPO_ROOT / "frontend" / ".env.local"]:
    if p.exists():
        load_dotenv(p, override=True)

from generate_audio import _build_shared_outline, _generate_and_prepare_script  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--lang", default="en", choices=["en", "fr"])
    args = ap.parse_args()

    brief_path = BACKEND_DIR / "output" / f"brief_{args.date}.json"
    if not brief_path.exists():
        print(f"ERROR: {brief_path} does not exist", file=sys.stderr)
        sys.exit(1)

    brief_json = json.loads(brief_path.read_text())
    print(f"Loaded {len(brief_json.get('items', []))} items from {brief_path.name}")

    shared_outline, outline_items = _build_shared_outline(brief_json)
    print(f"Built outline: {len(outline_items)} items")
    print(f"Generating {args.lang.upper()} script…\n")

    script = _generate_and_prepare_script(
        brief_json,
        shared_outline=shared_outline,
        outline_items=outline_items,
        lang=args.lang,
    )

    out_dir = BACKEND_DIR / "evals" / "output" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.date}_{args.lang}_test.txt"
    out_path.write_text(script)

    print("=" * 80)
    print(script)
    print("=" * 80)
    print(f"\nWord count: {len(script.split())}")
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    main()
