#!/usr/bin/env python3.11
"""A/B test: does removing Rule 4 + adding bullet-2 positive guidance
shift the Ghostwriter's analysis bullet 2 from absence inventories to
second reportable beats?

Runs the Ghostwriter on 3 synthetic gatekeeper items (today's DIFC,
Trump-Iran, WAIFC) against two prompts:

  A (before) = /tmp/ghostwriter_prompt_old.md   (HEAD — still has Rule 4)
  B (after)  = prompts/ghostwriter_prompt.md    (working tree — Rule 4 removed)

3 trials per item per variant. For each output, prints bullet 2 and a
rough classification (ABSENCE-INVENTORY vs SECOND-BEAT) driven by a
cheap regex heuristic. Writes full artefact to evals/output/ghostwriter.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

for p in [REPO_ROOT / ".env", REPO_ROOT / "frontend" / ".env.local"]:
    if p.exists():
        load_dotenv(p, override=True)

from pipeline.card_batch import run_chunked_card_batches  # noqa: E402

INPUTS_PATH = (
    BACKEND_DIR / "evals" / "output" / "ghostwriter" / "ghostwriter_b2_ab_inputs.json"
)
OLD_PROMPT_PATH = "/tmp/ghostwriter_prompt_old.md"
NEW_PROMPT_PATH = str(REPO_ROOT / "prompts" / "ghostwriter_prompt.md")

# Cheap heuristic: a bullet is an ABSENCE-INVENTORY if its subject or
# main verb lands on "not disclosed / not released / not reported /
# not been detailed / remain undisclosed / have not commented". Not
# bulletproof — but good enough to scan 18 outputs at a glance.
ABSENCE_PATTERNS = [
    r"\bwere?\s+not\s+(disclosed|released|reported|detailed|announced)\b",
    r"\bhave\s+not\s+been\s+(disclosed|released|reported|detailed|announced)\b",
    r"\bhas\s+not\s+been\s+(disclosed|released|reported|detailed|announced)\b",
    r"\b(remains?|remained)\s+(undisclosed|unconfirmed|unreported)\b",
    r"\bwere\s+all\s+undisclosed\b",
    r"\bhave\s+not\s+commented\b",
    r"\bwas\s+not\s+disclosed\b",
    r"\bnot\s+disclosed\s+in\s+the\s+announcement\b",
    r"\bdeclined\s+to\s+comment\b",  # treated as absence-adjacent
]
_ABSENCE_RE = re.compile("|".join(ABSENCE_PATTERNS), re.IGNORECASE)


def _classify_bullet(text: str) -> str:
    """Return 'ABSENCE' if bullet ends on/with an absence clause, else 'BEAT'."""
    if not text:
        return "EMPTY"
    hits = _ABSENCE_RE.findall(text)
    if not hits:
        return "BEAT"
    # Count as ABSENCE only if the absence language dominates the bullet —
    # ie. the bullet is structurally about what wasn't disclosed, not just
    # mentioning one absence as a supporting detail.
    total_words = len(text.split())
    absence_hits = len(hits)
    # Heuristic: ≥1 absence phrase AND absence phrase sits in last 40% of bullet
    last_40_pct = text[int(len(text) * 0.6):]
    if _ABSENCE_RE.search(last_40_pct):
        return "ABSENCE"
    return "BEAT-with-absence-mention"


def _bullet2(item: dict) -> str:
    analysis = item.get("analysis") or ""
    parts = [p.strip() for p in analysis.split("\n") if p.strip()]
    if len(parts) < 2:
        return ""
    b2 = parts[1]
    return b2.lstrip("- ").strip()


async def one_run(
    client: anthropic.AsyncAnthropic,
    item: dict,
    prompt_path: str,
) -> dict | None:
    payload = {
        "selected": [item],
        "allowed_ids": [item["id"]],
        "dropped": [],
        "brief_summary": {},
    }
    result, usage = await run_chunked_card_batches(
        client=client,
        gatekeeper_payload=payload,
        today="2026-04-22",
        standard_prompt_filename=prompt_path,
        include_dropped=False,
    )
    items = (result or {}).get("items") or []
    if not items:
        return None
    out = items[0]
    return {
        "id": out.get("id"),
        "headline": out.get("headline"),
        "key_bullets": out.get("key_bullets") or [],
        "analysis": out.get("analysis") or "",
        "bullet2": _bullet2(out),
        "usage": usage,
    }


async def main() -> None:
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    inputs = json.loads(INPUTS_PATH.read_text(encoding="utf-8"))
    assert isinstance(inputs, list) and inputs, "no A/B inputs found"

    trials = 3
    collected: dict = {}
    print(f"Bullet-2 A/B — {len(inputs)} item(s) × {trials} trial(s) × 2 variant(s)")
    print("=" * 70)

    for item in inputs:
        print(f"\n### {item['id']} — {item.get('headline','')[:70]}")
        collected[item["id"]] = {"A_before": [], "B_after": []}

        for variant_label, prompt_path in [
            ("A_before", OLD_PROMPT_PATH),
            ("B_after", NEW_PROMPT_PATH),
        ]:
            print(f"\n  --- {variant_label} ---")
            for t in range(1, trials + 1):
                try:
                    out = await one_run(client, item, prompt_path)
                except Exception as e:  # noqa: BLE001
                    print(f"    trial {t}: ERROR {e}")
                    continue
                if not out:
                    print(f"    trial {t}: no output")
                    continue
                b2 = out["bullet2"]
                cls = _classify_bullet(b2)
                print(f"    trial {t}  [{cls}]  {b2[:140]}...")
                collected[item["id"]][variant_label].append(out)

    out_dir = BACKEND_DIR / "evals" / "output" / "ghostwriter"
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    out_path = out_dir / f"bullet2_ab_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(collected, f, indent=2, ensure_ascii=False)
    print(f"\nWrote artefact → {out_path}")

    # Roll-up summary
    print("\n" + "=" * 70)
    print("SUMMARY — bullet 2 classification by variant")
    print("=" * 70)
    for item_id, runs in collected.items():
        for variant in ("A_before", "B_after"):
            counts = {"ABSENCE": 0, "BEAT": 0, "BEAT-with-absence-mention": 0, "EMPTY": 0}
            for out in runs[variant]:
                counts[_classify_bullet(out["bullet2"])] += 1
            print(
                f"  {item_id}  {variant:10s}  ABSENCE={counts['ABSENCE']}  "
                f"BEAT={counts['BEAT']}  BEAT-mention={counts['BEAT-with-absence-mention']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
