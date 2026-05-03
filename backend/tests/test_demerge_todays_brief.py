"""Replay test: would the demerge step have saved today's UAE Cabinet article?

Reconstructs the exact scenario from the 2026-03-30 pipeline run using CI logs
and the final brief, then verifies the demerge step would have split the merged
item into two separate selections — one for the Iran attack, one for the Cabinet
meeting.

Run:  cd backend && python3 tests/test_demerge_todays_brief.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

_backend = str(Path(__file__).resolve().parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

# Import demerge (copied version to avoid enricher.py 3.10 syntax issue)
from tests.test_demerge import demerge_selected_items, _normalize_for_match

_HR = "=" * 70
passed = 0
failed = 0


def _report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    icon = "\u2705" if ok else "\u274c"
    print(f"  {icon} {name}")
    if detail and not ok:
        for line in detail.splitlines():
            print(f"      {line}")
    if ok:
        passed += 1
    else:
        failed += 1


def main():
    global passed, failed

    print(f"\n{_HR}")
    print("REPLAY TEST: 2026-03-30 — Would demerge save the Cabinet article?")
    print(_HR)

    # ─────────────────────────────────────────────────────────────────────
    # STEP 1: Reconstruct the gatekeeper's merged selected item
    #
    # From CI enricher log:
    #   [enricher] Enriching: Iran attacks Kuwait military camp, Jordan,
    #   and Qatar; UAE Cabinet praises armed forces ... (50 words)
    #
    # The enricher receives items directly from the gatekeeper's selected
    # list (after rejoin_raw_content). The headline above is exactly what
    # the gatekeeper produced — semicolon-merged.
    # ─────────────────────────────────────────────────────────────────────

    merged_selected_item = {
        "headline": (
            "Iran attacks Kuwait military camp, Jordan, and Qatar; "
            "UAE Cabinet praises armed forces"
        ),
        "rank": 1,
        "brief_section": "UAE",
        "composite_score": 9.0,
        "topic_relevance": 9,
        "news_significance": 9,
        "selection_rationale": "Major regional security event with direct UAE government response",
        "cluster": "Iran-Gulf Conflict",
        "source": "WAM",
        "source_url": "https://www.wam.ae/en/article/uae-condemns-irans-attack-on-kuwaiti-military",
        "date": "2026-03-29",
        "date_evidence": "Published date from sitemap collector",
        "summary": "UAE strongly condemns Iran's unprovoked terrorist attack on Kuwait military camp",
        "raw_content": "",  # already stripped/rejoined
        "additional_context": "",
        "entities": [],
        "also_covered_by": [],
    }

    # The other 12 selected items (non-merged, from enricher logs)
    other_selected = [
        {"headline": "Iran warns against US invasion after Marines arrive; US and Israel struck nuclear sites",
         "rank": 2, "brief_section": "International Politics & Policy",
         "composite_score": 8.5, "source": "Various", "source_url": "https://example.com/iran-warns"},
        {"headline": "Iran disrupts Strait of Hormuz; Brent hits $112; S&P 500 falls 1.7%",
         "rank": 3, "brief_section": "International Politics & Policy",
         "composite_score": 8.0, "source": "Various", "source_url": "https://example.com/hormuz"},
        {"headline": "Drone attack on residence of Iraqi Kurdistan Region President Nechirvan Barzani",
         "rank": 4, "brief_section": "International Politics & Policy",
         "composite_score": 7.5, "source": "Various", "source_url": "https://example.com/drone"},
        {"headline": "Ukraine signs drone defence deal with UAE",
         "rank": 5, "brief_section": "UAE",
         "composite_score": 7.5, "source": "WAM", "source_url": "https://www.wam.ae/en/article/ukraine-drone-deal"},
        {"headline": "Bahrain's Foulath Holding declares force majeure due to regional conditions",
         "rank": 6, "brief_section": "UAE",
         "composite_score": 7.0, "source": "Various", "source_url": "https://example.com/foulath"},
        {"headline": "Zayed International Airport resumes limited operations after airspace disruption",
         "rank": 7, "brief_section": "UAE",
         "composite_score": 7.0, "source": "WAM", "source_url": "https://www.wam.ae/en/article/airport"},
        {"headline": "NeurIPS reverses US-sanctioned entity paper ban following Chinese boycott pressure",
         "rank": 8, "brief_section": "Regional Research & Academic Events",
         "composite_score": 7.5, "source": "Various", "source_url": "https://example.com/neurips"},
        {"headline": "Anthropic wins preliminary injunction halting Pentagon supply-chain risk designation",
         "rank": 9, "brief_section": "International Politics & Policy",
         "composite_score": 7.5, "source": "Various", "source_url": "https://example.com/anthropic"},
        {"headline": "H100 GPU rental prices surge amid reasoning model demand",
         "rank": 10, "brief_section": "Model Releases & Technical Developments",
         "composite_score": 7.0, "source": "Various", "source_url": "https://example.com/h100"},
        {"headline": "SoftBank's $40B loan from JPMorgan and Goldman signals potential 2026 OpenAI IPO",
         "rank": 11, "brief_section": "International Business & Technology",
         "composite_score": 7.0, "source": "Various", "source_url": "https://example.com/softbank"},
        {"headline": "Egypt unveils National AI Governance Framework",
         "rank": 12, "brief_section": "Regional Research & Academic Events",
         "composite_score": 7.0, "source": "Various", "source_url": "https://example.com/egypt"},
        {"headline": "Huawei AI chip gains traction as ByteDance and Alibaba plan orders",
         "rank": 13, "brief_section": "International Business & Technology",
         "composite_score": 7.0, "source": "Various", "source_url": "https://example.com/huawei"},
    ]

    all_selected = [merged_selected_item] + other_selected

    print(f"\n  Original gatekeeper output: {len(all_selected)} selected items")
    print(f"  Item 1 (merged): \"{merged_selected_item['headline']}\"")

    # ─────────────────────────────────────────────────────────────────────
    # STEP 2: Reconstruct the scout items available for matching
    #
    # From CI dedup logs:
    #   Dedup (semantic): merged 2 items -> 'UAE Cabinet praises heroic
    #     defence spirit of UAE Armed Force'
    #   Dedup (semantic): merged 3 items -> 'UAE strongly condemns Iran's
    #     unprovoked terrorist attack on '
    #
    # These are the surviving scout items after dedup — the gatekeeper's
    # input. Each was a separate item the gatekeeper could have selected.
    # ─────────────────────────────────────────────────────────────────────

    scout_items = [
        # The Cabinet article — this is what we want demerge to recover
        {
            "headline": (
                "UAE Cabinet praises heroic defence spirit of UAE Armed Forces, "
                "high national spirit by both citizens, residents, outstanding "
                "sense of responsibility by all work teams"
            ),
            "source": "WAM",
            "source_url": "https://www.wam.ae/en/article/bzg4ujj-uae-cabinet-chaired-mohammed-bin-rashid-praises",
            "date": "2026-03-29",
            "date_evidence": "Published date from sitemap collector",
            "summary": (
                "UAE Cabinet praises heroic defence spirit of UAE Armed Forces, "
                "high national spirit by both citizens, residents, outstanding "
                "sense of responsibility by all work teams"
            ),
            "raw_content": (
                "UAE Cabinet praises heroic defence spirit of UAE Armed Forces, "
                "high national spirit by both citizens, residents, outstanding "
                "sense of responsibility by all work teams"
            ),
            "additional_context": "",
            "entities": [],
            "category": "",
            "also_covered_by": [],
            "source_scout": "uae",
        },
        # The Iran attack / UAE condemns article
        {
            "headline": (
                "UAE strongly condemns Iran's unprovoked terrorist attack on "
                "Kuwaiti military camp"
            ),
            "source": "WAM",
            "source_url": "https://www.wam.ae/en/article/uae-condemns-irans-attack-on-kuwaiti-military",
            "date": "2026-03-29",
            "date_evidence": "Published date from sitemap collector",
            "summary": (
                "UAE strongly condemns Iran's unprovoked terrorist attack on "
                "Kuwaiti military camp"
            ),
            "raw_content": (
                "UAE strongly condemns Iran's unprovoked terrorist attack on "
                "Kuwaiti military camp"
            ),
            "additional_context": "",
            "entities": [],
            "category": "",
            "also_covered_by": [],
            "source_scout": "uae",
        },
        # Iran attacks Kuwait (direct attack story)
        {
            "headline": "Iran attacks Kuwait military camp, injuring 10 soldiers",
            "source": "Gulf News",
            "source_url": "https://gulfnews.com/uae/iran-attacks-kuwait",
            "date": "2026-03-29",
            "date_evidence": "Published date from scraper collector",
            "summary": "Iran attacks Kuwait military camp, injuring 10 soldiers",
            "raw_content": "Iran attacks Kuwait military camp",
            "additional_context": "",
            "entities": [],
            "category": "",
            "also_covered_by": [],
            "source_scout": "uae",
        },
        # Jordan targeted
        {
            "headline": "Jordan Armed Forces: Iran targeted Jordan with one missile, two drones intercepted",
            "source": "Reuters",
            "source_url": "https://reuters.com/jordan-iran-missile",
            "date": "2026-03-29",
            "date_evidence": "Published date from scraper collector",
            "summary": "Jordan Armed Forces: Iran targeted Jordan with one missile, two drones intercepted",
            "raw_content": "Jordan Armed Forces say Iran targeted Jordan",
            "additional_context": "",
            "entities": [],
            "category": "",
            "also_covered_by": [],
            "source_scout": "international",
        },
        # Qatar drone
        {
            "headline": "Qatar intercepts Iranian drone amid regional strikes",
            "source": "Al Jazeera",
            "source_url": "https://aljazeera.com/qatar-drone",
            "date": "2026-03-29",
            "date_evidence": "Published date from scraper collector",
            "summary": "Qatar intercepts Iranian drone amid regional strikes",
            "raw_content": "Qatar intercepts drone",
            "additional_context": "",
            "entities": [],
            "category": "",
            "also_covered_by": [],
            "source_scout": "international",
        },
    ]

    print(f"  Scout items available for matching: {len(scout_items)}")
    for s in scout_items:
        print(f"    • {s['headline'][:75]}...")

    # ─────────────────────────────────────────────────────────────────────
    # STEP 3: Run demerge
    # ─────────────────────────────────────────────────────────────────────

    print(f"\n  --- Running demerge_selected_items ---")

    result, merge_count = demerge_selected_items(all_selected, scout_items)

    print(f"\n  After demerge: {len(result)} items (was {len(all_selected)})")

    # ─────────────────────────────────────────────────────────────────────
    # STEP 4: Verify the Cabinet article is now a separate item
    # ─────────────────────────────────────────────────────────────────────

    print(f"\n  --- Verification ---\n")

    _report("Merged item was detected and split", merge_count >= 1,
            f"merge_count={merge_count}")

    _report("Total items increased (13 → 14+)", len(result) > len(all_selected),
            f"Before: {len(all_selected)}, After: {len(result)}")

    # Find the Cabinet item in the results
    cabinet_item = None
    iran_item = None
    for item in result:
        h = item["headline"].lower()
        if "cabinet" in h and "praises" in h:
            cabinet_item = item
        if ("iran" in h and "attack" in h and "kuwait" in h) or \
           ("condemns" in h and "iran" in h and "attack" in h):
            iran_item = item

    _report("Cabinet article exists as separate item", cabinet_item is not None,
            "No item with 'cabinet' + 'praises' found in results")

    _report("Iran attack article exists as separate item", iran_item is not None,
            "No item with 'iran' + 'attack' + 'kuwait' found in results")

    if cabinet_item:
        print(f"\n  Cabinet item recovered:")
        print(f"    Headline:  {cabinet_item['headline'][:80]}")
        print(f"    Source:    {cabinet_item.get('source', '?')}")
        print(f"    URL:       {cabinet_item.get('source_url', '?')[:70]}")
        print(f"    Score:     {cabinet_item.get('composite_score', '?')}")
        print(f"    Section:   {cabinet_item.get('brief_section', '?')}")
        print(f"    Rank:      {cabinet_item.get('rank', '?')}")

        _report("Cabinet item has correct WAM source URL",
                "bzg4ujj" in cabinet_item.get("source_url", ""),
                f"URL: {cabinet_item.get('source_url', '')}")

        _report("Cabinet item has WAM source",
                cabinet_item.get("source") == "WAM")

        _report("Cabinet item inherits gatekeeper score (9.0)",
                cabinet_item.get("composite_score") == 9.0,
                f"Score: {cabinet_item.get('composite_score')}")

        _report("Cabinet item is in UAE section",
                cabinet_item.get("brief_section") == "UAE",
                f"Section: {cabinet_item.get('brief_section')}")

    if iran_item:
        print(f"\n  Iran attack item recovered:")
        print(f"    Headline:  {iran_item['headline'][:80]}")
        print(f"    URL:       {iran_item.get('source_url', '?')[:70]}")

    # Verify no items were lost
    non_merged_headlines = {item["headline"] for item in other_selected}
    result_headlines = {item["headline"] for item in result}
    missing = non_merged_headlines - result_headlines
    _report("All non-merged items preserved", len(missing) == 0,
            f"Missing: {missing}" if missing else "")

    # Verify ranks are sequential
    ranks = [r["rank"] for r in result]
    _report("Ranks are sequential", ranks == list(range(1, len(result) + 1)),
            f"Ranks: {ranks}")

    # ─────────────────────────────────────────────────────────────────────
    # STEP 5: Trace what happens AFTER demerge in the pipeline
    # ─────────────────────────────────────────────────────────────────────

    if cabinet_item:
        print(f"\n  --- What happens next in the pipeline ---")
        print(f"  1. assign_gatekeeper_ids: Cabinet item gets ID '2026-03-30-s0XX'")
        print(f"  2. Enricher: Cabinet item is thin ({len(cabinet_item.get('raw_content','').split())} words)")
        print(f"     → Step 1: trafilatura fetch of WAM URL (will fail — SPA)")
        print(f"     → Step 2: Serper search for headline → finds third-party coverage")
        print(f"     → Gets 700-1100+ words about Space Strategy, Genome Council, etc.")
        print(f"  3. Ghostwriter: receives enriched content, writes ONE rich brief item")
        print(f"     with key decisions in the body (Space Strategy 2031, Genome Council,")
        print(f"     120 international agreements, etc.)")

    print(f"\n{_HR}")
    print(f"Results: {passed} passed, {failed} failed")
    print(_HR)
    return failed == 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ok = main()
    sys.exit(0 if ok else 1)
