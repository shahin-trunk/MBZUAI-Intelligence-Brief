#!/usr/bin/env python3.11
"""Run ghostwriter on a subset of today's selected items.

Loads the enriched gatekeeper payload, filters to a provided list of
item IDs, and runs the current ghostwriter prompt. No DB writes.

Usage:
    cd backend && python -m evals.run_ghostwriter_subset \\
        --date 2026-04-17 --ids 2026-04-17-s001,2026-04-17-s002
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

for p in [REPO_ROOT / ".env", REPO_ROOT / "frontend" / ".env.local"]:
    if p.exists():
        load_dotenv(p, override=True)

from pipeline.card_batch import run_chunked_card_batches  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--ids", required=True, help="comma-separated item IDs")
    ap.add_argument("--label", default="v3_selected_standard")
    args = ap.parse_args()

    target_ids = {s.strip() for s in args.ids.split(",") if s.strip()}
    enriched_path = BACKEND_DIR / "output" / f"enriched_gatekeeper_output_{args.date}.json"
    full_payload = json.loads(enriched_path.read_text())

    filtered = [it for it in full_payload.get("selected", []) if str(it.get("id")) in target_ids]
    missing = target_ids - {str(it.get("id")) for it in filtered}
    if missing:
        print(f"WARNING: missing from enriched output: {missing}", file=sys.stderr)

    subset = {**full_payload, "selected": filtered}
    print(f"Running ghostwriter on {len(filtered)} of {len(target_ids)} requested IDs")

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    result, usage = await run_chunked_card_batches(
        client=client,
        gatekeeper_payload=subset,
        today=args.date,
    )

    out_dir = BACKEND_DIR / "evals" / "output" / "ghostwriter"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.date}_{args.label}.json"
    out_path.write_text(json.dumps(result or {"items": []}, indent=2))

    print(f"\nWrote {len((result or {}).get('items', []))} items → {out_path}")
    print(f"Tokens: in={usage.get('input_tokens',0):,}  out={usage.get('output_tokens',0):,}")


if __name__ == "__main__":
    asyncio.run(main())
