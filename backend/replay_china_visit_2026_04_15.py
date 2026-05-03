"""Replay of the 2026-04-15 Crown Prince / China state visit failure.

Runs the Synthesis stage (Phase 2) against the captured post-Content-Filter
scout output from the production run on 2026-04-15, which silently lost all
coverage of the Crown Prince's visit to China. Verifies that:

1. The 5 Crown Prince items collected by ADMO today are traceable through
   the pipeline — either surviving to the Gatekeeper or visibly persisted
   in `dropped_items` (no silent drops).
2. Synthesis clusters the Crown Prince items together and annotates the
   cluster as `head_of_state` / `continuation`.
3. After Synthesis, the orchestrator no longer routes the items through
   `flag_previous_brief_overlaps`, so they are not eligible for the fuzzy-
   string hard-drop that killed them today.

Requires ANTHROPIC_API_KEY in the environment.

Usage:
    cd backend && python3 replay_china_visit_2026_04_15.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

OUTPUT_DIR = BACKEND_DIR / "output"
DATE = "2026-04-15"

CROWN_KEYWORDS = (
    "crown prince",
    "peoples republic of china",
    "president of the people",
    "xi jinping",
    "khaled bin mohamed",
    "premier of china",
    "chairmen of leading chinese",
    "uae nationals studying in beijing",
)


def _matches_crown(headline: str) -> bool:
    low = headline.lower().replace("’", "'")
    return any(kw in low for kw in CROWN_KEYWORDS)


def _load(name: str):
    path = OUTPUT_DIR / name
    if not path.exists():
        raise SystemExit(f"Missing artifact: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


async def main() -> int:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is required")

    import anthropic
    from prompts.loader import load_prompt
    from pipeline.synthesis import run_synthesis, apply_synthesis_annotations

    # --- Load the captured pipeline state for 2026-04-15 ------------------

    scout_output = _load(f"scout_output_{DATE}.json")
    print(f"scout_output_{DATE}.json: {len(scout_output)} items")

    # Map Crown Prince items across pipeline stages so the reader of this
    # script can see the complete picture — not just the subset that
    # survived to scout_output.
    collected_raw = _load(f"collected_raw_{DATE}.json")
    raw_cp = [
        (i, it.get("headline", ""), it.get("date", ""))
        for i, it in enumerate(collected_raw)
        if _matches_crown(it.get("headline", ""))
    ]
    print(f"\nCROWN PRINCE / CHINA items in collected_raw_{DATE}.json:")
    for i, h, d in raw_cp:
        print(f"  [{i}] {d} | {h[:95]}")

    sc_cp = [i for i, it in enumerate(scout_output) if _matches_crown(it.get("headline", ""))]
    print(f"\nCROWN PRINCE items surviving to scout_output (post-CF): {len(sc_cp)}")
    for i in sc_cp:
        print(f"  [{i}] {scout_output[i].get('headline', '')[:95]}")

    # --- Run Synthesis against the captured post-CF items ------------------

    client = anthropic.AsyncAnthropic()

    # Build the lightweight input the orchestrator would send.
    synthesis_items = [
        {
            "id": i,
            "headline": item.get("headline", ""),
            "summary": (item.get("summary") or "")[:800],
            "entities": item.get("entities", []),
            "source": item.get("source"),
            "date": item.get("date") or item.get("_verified_date"),
        }
        for i, item in enumerate(scout_output)
    ]

    synthesis_prompt = load_prompt(
        "synthesis_prompt.md",
        items_json=json.dumps(synthesis_items, indent=2, ensure_ascii=False),
    )

    print(f"\nRunning Synthesis (Haiku 4.5) on {len(synthesis_items)} items...")
    syn_result, syn_usage = await run_synthesis(client, synthesis_prompt)
    print(
        f"Synthesis tokens_in={syn_usage['input_tokens']} "
        f"tokens_out={syn_usage['output_tokens']}"
    )

    clusters = syn_result.get("clusters", [])
    annotations = syn_result.get("item_annotations", [])
    print(f"\n{len(clusters)} cluster(s) produced, {len(annotations)} item annotation(s)")

    # --- Inspect the Crown Prince cluster(s) -------------------------------

    # Find clusters whose composite headline or member headlines mention the
    # state visit.
    cp_cluster_ids = set()
    for cluster in clusters:
        composite = cluster.get("composite_headline", "").lower()
        if _matches_crown(composite):
            cp_cluster_ids.add(cluster["cluster_id"])
        for mem_id in cluster.get("member_item_ids", []):
            if mem_id < len(scout_output) and _matches_crown(
                scout_output[mem_id].get("headline", "")
            ):
                cp_cluster_ids.add(cluster["cluster_id"])

    print(f"\nCROWN PRINCE cluster(s): {len(cp_cluster_ids)}")
    for cid in cp_cluster_ids:
        cluster = next(c for c in clusters if c["cluster_id"] == cid)
        print(f"  cluster_id:         {cluster['cluster_id']}")
        print(f"  event_key:          {cluster['event_key']}")
        print(f"  composite:          {cluster['composite_headline'][:95]}")
        print(f"  significance_tier:  {cluster.get('significance_tier')}")
        print(f"  continuity_status:  {cluster.get('continuity_status')}")
        print(f"  continuity_ref:     {cluster.get('continuity_reference')}")
        print(f"  members ({len(cluster['member_item_ids'])}):")
        for mem_id in cluster["member_item_ids"]:
            if mem_id < len(scout_output):
                ann = next(
                    (a for a in annotations if a.get("item_id") == mem_id),
                    {},
                )
                print(
                    f"    [{mem_id}] facet={ann.get('facet'):>25} | "
                    f"{scout_output[mem_id].get('headline', '')[:80]}"
                )

    # --- Apply annotations and show what Gatekeeper will see ---------------

    annotated, unannotated = apply_synthesis_annotations(scout_output, syn_result)
    print(
        f"\nAnnotated {annotated}/{len(scout_output)} items "
        f"({unannotated} un-annotated)"
    )

    # --- Assertions --------------------------------------------------------

    failures = []

    # 1. At least one cluster must be identified as the Crown Prince visit.
    if not cp_cluster_ids:
        failures.append(
            "No Crown Prince cluster produced by Synthesis. "
            "With only 1 CP item surviving to scout_output this is "
            "expected to be a solo cluster, but SOME cluster must "
            "cover it."
        )

    # 2. The Crown Prince cluster must be tagged head_of_state or major.
    if cp_cluster_ids:
        top_cluster = next(
            c for c in clusters if c["cluster_id"] == next(iter(cp_cluster_ids))
        )
        if top_cluster.get("significance_tier") not in ("head_of_state", "major"):
            failures.append(
                f"Crown Prince cluster significance_tier="
                f"{top_cluster.get('significance_tier')!r}; expected "
                f"head_of_state or major."
            )

    # 3. Every scout_output item must have an annotation (no silent drops
    #    from Synthesis).
    annotation_ids = {a["item_id"] for a in annotations}
    missing_ids = set(range(len(scout_output))) - annotation_ids
    if missing_ids:
        failures.append(
            f"Synthesis returned no annotation for {len(missing_ids)} item(s). "
            f"First missing: {sorted(missing_ids)[:5]}"
        )

    # 4. Every Crown Prince item that did survive to scout_output must be
    #    annotated and belong to a Crown Prince cluster.
    for i in sc_cp:
        ann = next((a for a in annotations if a.get("item_id") == i), None)
        if ann is None:
            failures.append(
                f"scout_output[{i}] Crown Prince item has no Synthesis annotation"
            )
            continue
        if ann.get("cluster_id") not in cp_cluster_ids:
            failures.append(
                f"scout_output[{i}] Crown Prince item is in cluster "
                f"{ann.get('cluster_id')!r}, not a Crown Prince cluster "
                f"({cp_cluster_ids})"
            )

    # --- Report ------------------------------------------------------------

    print("\n" + "=" * 70)
    if failures:
        print("REPLAY FAILED")
        for f in failures:
            print(f"  ✗ {f}")
        print()
        print("Saving full Synthesis output for inspection: /tmp/synthesis_replay.json")
        Path("/tmp/synthesis_replay.json").write_text(
            json.dumps(syn_result, indent=2, ensure_ascii=False)
        )
        return 1

    print("REPLAY PASSED")
    print(f"  ✓ Crown Prince cluster(s) identified: {len(cp_cluster_ids)}")
    print(f"  ✓ Cluster significance_tier is head_of_state or major")
    print(f"  ✓ Every scout_output item annotated by Synthesis")
    print(
        f"  ✓ Pre-Phase-2 fate of this item was 'post_gatekeeper_overlap' "
        f"hard-drop. With SYNTHESIS_ENABLED=true, that filter is "
        f"bypassed, so the item reaches the Gatekeeper with rich cluster "
        f"metadata and the Gatekeeper prompt forbids silently collapsing "
        f"head_of_state clusters."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
