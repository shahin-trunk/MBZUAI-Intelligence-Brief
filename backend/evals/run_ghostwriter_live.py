#!/usr/bin/env python3.11
"""One-shot runner: re-ghostwriter today's enriched gatekeeper output
with the current prompt, save to a side file for A/B comparison.

Does NOT touch the DB, editor, slop audit, or ingest — only the
Ghostwriter stage. Output goes to backend/evals/output/ghostwriter/
so it doesn't collide with the production artifact at
backend/output/ghostwriter_output_{date}.json.

Usage:
    cd backend && python -m evals.run_ghostwriter_live --date 2026-04-17
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# Load env from root .env
for p in [REPO_ROOT / ".env", REPO_ROOT / "frontend" / ".env.local"]:
    if p.exists():
        load_dotenv(p, override=True)

from pipeline.card_batch import run_chunked_card_batches  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD — used to pick the enriched input and name the output")
    ap.add_argument("--label", default="v2_new_prompt", help="suffix for the output filename")
    args = ap.parse_args()

    enriched_path = BACKEND_DIR / "output" / f"enriched_gatekeeper_output_{args.date}.json"
    if not enriched_path.exists():
        print(f"ERROR: {enriched_path} does not exist", file=sys.stderr)
        sys.exit(1)

    with open(enriched_path) as f:
        gatekeeper_payload = json.load(f)

    n_selected = len(gatekeeper_payload.get("selected", []))
    print(f"Loaded {n_selected} selected items from {enriched_path.name}")
    print("Calling run_chunked_card_batches (this can take a few minutes)...")

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    result, usage = await run_chunked_card_batches(
        client=client,
        gatekeeper_payload=gatekeeper_payload,
        today=args.date,
    )

    out_dir = BACKEND_DIR / "evals" / "output" / "ghostwriter"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.date}_{args.label}.json"
    with open(out_path, "w") as f:
        json.dump(result or {"items": []}, f, indent=2)

    n_items = len((result or {}).get("items", []))
    print(f"\nWrote {n_items} items → {out_path}")
    print(f"Tokens: in={usage.get('input_tokens',0):,}  out={usage.get('output_tokens',0):,}")


if __name__ == "__main__":
    asyncio.run(main())
