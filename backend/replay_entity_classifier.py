"""Live-API replay of the Entity Classifier against captured Ghostwriter output.

Loads `backend/output/ghostwriter_output_{date}.json` for one or more dates,
runs the classifier against each, and prints the resulting
`primary_entity_category` per item side-by-side with the entity + headline so
a human can spot-check plausibility.

Intended as a pre-deploy check — we verified the 2026-04-15 run has 15 items
with primary_entity populated; we expect the classifier to return a
plausible category for each (mostly country/government/company).

Usage:
    cd backend && python3 replay_entity_classifier.py             # default: 2026-04-15
    cd backend && python3 replay_entity_classifier.py --dates 2026-04-15,2026-04-09
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_project_env  # noqa: E402

load_project_env()

OUTPUT_DIR = BACKEND_DIR / "output"


async def replay_one(client, date: str) -> dict:
    from prompts.loader import load_prompt
    from pipeline.entity_classifier import (
        apply_entity_classifications,
        build_classifier_input_items,
        run_entity_classifier,
    )

    path = OUTPUT_DIR / f"ghostwriter_output_{date}.json"
    if not path.exists():
        return {"date": date, "error": f"missing {path.name}"}

    ghostwriter = json.loads(path.read_text(encoding="utf-8"))
    items = list(ghostwriter.get("items", []))
    n_total = len(items)
    n_with_entity = sum(1 for it in items if it.get("primary_entity"))

    print(f"\n--- {date} --- {n_total} item(s), {n_with_entity} with primary_entity")

    classifiable = build_classifier_input_items(items)
    if not classifiable:
        print("  (no items with primary_entity to classify)")
        return {"date": date, "items": n_total, "classifiable": 0}

    prompt = load_prompt(
        "entity_classifier_prompt.md",
        items_json=json.dumps(classifiable, indent=2, ensure_ascii=False),
    )
    result, usage = await run_entity_classifier(client, prompt)
    print(
        f"  tokens_in={usage['input_tokens']} tokens_out={usage['output_tokens']}"
    )

    apply_entity_classifications(items, result)

    # Print one row per item: category | entity | headline
    for item in items:
        cat = item.get("primary_entity_category") or "---"
        entity = item.get("primary_entity") or "<none>"
        headline = (item.get("headline", "") or "")[:80]
        print(f"  {cat:<12} | {entity:<40} | {headline}")

    return {
        "date": date,
        "items": n_total,
        "classified": sum(1 for it in items if it.get("primary_entity_category")),
        "tokens_in": usage["input_tokens"],
        "tokens_out": usage["output_tokens"],
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", default="2026-04-15")
    args = parser.parse_args()

    dates = [d.strip() for d in args.dates.split(",") if d.strip()]

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set in env")

    import anthropic

    client = anthropic.AsyncAnthropic()

    results = []
    for date in dates:
        try:
            results.append(await replay_one(client, date))
        except Exception as e:
            print(f"  ✗ {date} failed: {e}")
            results.append({"date": date, "error": str(e)})

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for r in results:
        if "error" in r:
            print(f"  {r['date']}  ERROR: {r['error']}")
        else:
            print(
                f"  {r['date']}  items={r['items']}  classified={r.get('classified', 0)}"
                f"  tokens_in={r.get('tokens_in', 0)}  tokens_out={r.get('tokens_out', 0)}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
