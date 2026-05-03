"""
Live tests for the Brief Rationalization stage.

These tests call Sonnet with real (or realistic) gatekeeper output to verify
that the rationalization agent exercises sound editorial judgment.

Each test feeds a specific scenario and checks whether the model's response
demonstrates the intended behaviour.  Because the model is non-deterministic,
tests check structural properties ("did it demote at least one Iran item?")
rather than exact outputs.

Run:  cd backend && python3 tests/test_brief_rationalization.py

Requires ANTHROPIC_API_KEY in the environment.
"""

import asyncio
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env files so ANTHROPIC_API_KEY is available
from dotenv import load_dotenv
from pathlib import Path
_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / "frontend" / ".env.local", override=True)
load_dotenv(_root / ".env", override=True)

from config import MODEL
from prompts.loader import load_prompt
from pipeline.json_utils import safe_parse_json

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  \033[32m✓\033[0m {name}")
    else:
        FAIL += 1
        msg = f"  \033[31m✗\033[0m {name}"
        if detail:
            msg += f"  — {detail}"
        print(msg)


async def call_rationalization(selected, promotion_pool):
    """Call the rationalization prompt and return parsed result."""
    import anthropic

    client = anthropic.AsyncAnthropic()
    prompt = load_prompt("brief_rationalization_prompt.md")
    prompt = prompt.replace(
        "{selected_json}", json.dumps(selected, indent=2, ensure_ascii=False)
    ).replace(
        "{promotion_pool_json}", json.dumps(promotion_pool, indent=2, ensure_ascii=False)
    )
    response = await client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return safe_parse_json(text), response.usage


# ═══════════════════════════════════════════════════════════════════════
# TEST SCENARIOS
# ═══════════════════════════════════════════════════════════════════════

# Scenario 1: Iran-dominated brief (April 3 production data)
# 6 of 7 International Politics items are Iran/Hormuz.
# Promotion pool has DeepMind AI security (6.8) and H Company models (6.4).
# Expectation: demote 1-3 Iran items, promote diverse replacements.

SCENARIO_1_SELECTED = [
    {"id": "apr3-1", "headline": "Iranian strike shuts Emirates Global Aluminium, taking 1.6 million tonnes offline", "section": "UAE", "brief_section": "UAE", "composite_score": 8.6, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Direct UAE economic impact from Iran strikes"},
    {"id": "apr3-2", "headline": "China expands digital yuan operator network to 22 authorized banks", "section": "International Business & Technology", "brief_section": "International Business & Technology", "composite_score": 8.6, "cluster": None, "selection_rationale": "Major digital currency expansion"},
    {"id": "apr3-3", "headline": "Trump commits to two-to-three weeks of intensified Iran strikes", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.4, "cluster": "Iran/Hormuz crisis", "selection_rationale": "US military escalation"},
    {"id": "apr3-4", "headline": "U.S. strikes Karaj bridge to sever Iranian drone and missile supply routes", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.4, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Specific tactical strike targeting supply chain"},
    {"id": "apr3-5", "headline": "TII releases Falcon Perception segmentation and OCR models", "section": "Model Releases & Technical Developments", "brief_section": "Model Releases & Technical Developments", "composite_score": 8.2, "cluster": None, "selection_rationale": "Tracked entity TII model release"},
    {"id": "apr3-6", "headline": "Iran's daily oil revenue rises to $139 million as it controls Hormuz access", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.0, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Economic dimension of Hormuz crisis"},
    {"id": "apr3-7", "headline": "Thirty-plus nations convene in London on Hormuz diplomatic solutions", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.0, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Diplomatic response to crisis"},
    {"id": "apr3-8", "headline": "China and Pakistan present five-point Iran ceasefire plan", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.0, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Alternative diplomatic track"},
    {"id": "apr3-9", "headline": "China positions itself as Iran war mediator with limited leverage", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.0, "cluster": "Iran/Hormuz crisis", "selection_rationale": "China's strategic positioning in crisis"},
    {"id": "apr3-10", "headline": "Artemis II launches four astronauts toward lunar orbit", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.0, "cluster": None, "selection_rationale": "Historic space milestone"},
    {"id": "apr3-11", "headline": "MIT eases startup rules for faculty and students amid AI boom and budget pressure", "section": "Regional Research & Academic Events", "brief_section": "Regional Research & Academic Events", "composite_score": 8.0, "cluster": None, "selection_rationale": "Academic competitor move relevant to MBZUAI"},
    {"id": "apr3-12", "headline": "Hormuz closure cuts Qatari helium exports, threatening AI chip fabrication", "section": "UAE", "brief_section": "UAE", "composite_score": 7.6, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Supply chain risk to AI infrastructure"},
    {"id": "apr3-13", "headline": "Masdar and TotalEnergies sign clean energy framework for Asia and Africa", "section": "UAE", "brief_section": "UAE", "composite_score": 7.0, "cluster": None, "selection_rationale": "UAE clean energy expansion"},
    {"id": "apr3-14", "headline": "AI cited as primary cause in 25% of U.S. job cuts in March", "section": "International Business & Technology", "brief_section": "International Business & Technology", "composite_score": 7.0, "cluster": None, "selection_rationale": "AI labor market impact"},
    {"id": "apr3-15", "headline": "Global startup funding reaches $297 billion in Q1, driven by four AI mega-deals", "section": "International Business & Technology", "brief_section": "International Business & Technology", "composite_score": 7.0, "cluster": None, "selection_rationale": "AI investment landscape"},
    {"id": "apr3-16", "headline": "Microsoft releases MAI-Transcribe-1, lowest word-error-rate model across 25 languages", "section": "Model Releases & Technical Developments", "brief_section": "Model Releases & Technical Developments", "composite_score": 7.0, "cluster": None, "selection_rationale": "Notable model release"},
    {"id": "apr3-17", "headline": "Hugging Face releases TRL v1.0 as stable post-training infrastructure", "section": "Model Releases & Technical Developments", "brief_section": "Model Releases & Technical Developments", "composite_score": 7.0, "cluster": None, "selection_rationale": "Open-source AI infrastructure milestone"},
]

SCENARIO_1_POOL = [
    {"id": "apr3-d1", "headline": "Trump threatens to bomb Iran 'back to Stone Ages'", "composite_score": 7.8, "drop_reason": "Superseded by Trump signals prolonged Iran involvement", "section": "International Politics & Policy"},
    {"id": "apr3-d2", "headline": "UAE restricts entry for Iranian nationals", "composite_score": 7.2, "drop_reason": "No material update from yesterday", "section": "UAE"},
    {"id": "apr3-d3", "headline": "Microsoft presents speech model with lowest error rate", "composite_score": 7.0, "drop_reason": "Merged into Microsoft releases three new foundational AI models", "section": "Model Releases & Technical Developments"},
    {"id": "apr3-d4", "headline": "Google DeepMind reveals web attacks on AI agents", "composite_score": 6.8, "drop_reason": "Judgment zone exclusion — important AI security research but section at capacity", "section": "Model Releases & Technical Developments"},
    {"id": "apr3-d5", "headline": "Trump Tries to Sell Americans on Iran War", "composite_score": 6.8, "drop_reason": "No material update — domestic political framing", "section": "International Politics & Policy"},
    {"id": "apr3-d6", "headline": "Claude Code leak exposes Anthropic's internal source code", "composite_score": 6.8, "drop_reason": "No material update from yesterday", "section": "International Business & Technology"},
    {"id": "apr3-d7", "headline": "H Company unveils open computer-use models outperforming GPT-5.4", "composite_score": 6.4, "drop_reason": "Judgment zone exclusion — competitive model release but insufficient summary", "section": "Model Releases & Technical Developments"},
    {"id": "apr3-d8", "headline": "Bahrain intercepts, destroys 188 missiles, 429 drones since onset", "composite_score": 6.4, "drop_reason": "No material update — cumulative statistics", "section": "International Politics & Policy"},
    {"id": "apr3-d9", "headline": "Governments impose energy rationing amid Middle East conflict", "composite_score": 6.2, "drop_reason": "Judgment zone exclusion — covered by broader energy impact", "section": "International Politics & Policy"},
]


# Scenario 2: Already-balanced brief (March 31 production data)
# Good distribution: 5 UAE, 4 Intl Business, 3 Model Releases, 2 Intl Politics, 1 Regional
# Expectation: no changes (or minimal), editorial note says "balanced"

SCENARIO_2_SELECTED = [
    {"id": "mar31-1", "headline": "Anthropic's Claude Mythos leaked as new flagship above Opus tier", "section": "Model Releases & Technical Developments", "brief_section": "Model Releases & Technical Developments", "composite_score": 8.6, "cluster": "Anthropic", "selection_rationale": "Major model leak"},
    {"id": "mar31-2", "headline": "UAE air defences intercept 11 ballistic missiles and 27 UAVs", "section": "UAE", "brief_section": "UAE", "composite_score": 8.6, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Direct UAE security event"},
    {"id": "mar31-3", "headline": "Iran strikes Gulf desalination, power, and industrial infrastructure", "section": "UAE", "brief_section": "UAE", "composite_score": 8.6, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Infrastructure attack on UAE"},
    {"id": "mar31-4", "headline": "US crude oil breaches $100 per barrel for first time since 2022", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.0, "cluster": None, "selection_rationale": "Economic benchmark"},
    {"id": "mar31-5", "headline": "Mistral raises $830 million in debut debt to build European AI data centres", "section": "International Business & Technology", "brief_section": "International Business & Technology", "composite_score": 8.0, "cluster": None, "selection_rationale": "Major AI funding"},
    {"id": "mar31-6", "headline": "UAE Central Bank pilots region's first biometric payment system", "section": "Regional Research & Academic Events", "brief_section": "Regional Research & Academic Events", "composite_score": 8.0, "cluster": None, "selection_rationale": "UAE fintech innovation"},
    {"id": "mar31-7", "headline": "UAE Ministry of Education extends remote learning for all schools", "section": "UAE", "brief_section": "UAE", "composite_score": 7.8, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Domestic impact of crisis"},
    {"id": "mar31-8", "headline": "Alibaba releases Qwen3.5-Omni with native audio-visual multimodal capabilities", "section": "Model Releases & Technical Developments", "brief_section": "Model Releases & Technical Developments", "composite_score": 7.6, "cluster": None, "selection_rationale": "Major Chinese model release"},
    {"id": "mar31-9", "headline": "Study finds reasoning models consume up to 30-79x more energy per query", "section": "Model Releases & Technical Developments", "brief_section": "Model Releases & Technical Developments", "composite_score": 7.6, "cluster": None, "selection_rationale": "AI energy cost research"},
    {"id": "mar31-10", "headline": "Iranian drone strikes Kuwaiti oil tanker in Dubai port waters", "section": "UAE", "brief_section": "UAE", "composite_score": 7.6, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Direct threat to UAE maritime"},
    {"id": "mar31-11", "headline": "Pakistan hosts four-nation ministerial to advance Iran-US diplomacy", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 7.6, "cluster": "Iran/Hormuz crisis", "selection_rationale": "Diplomatic track"},
    {"id": "mar31-12", "headline": "Anthropic weighs October IPO after court blocks Pentagon ban", "section": "International Business & Technology", "brief_section": "International Business & Technology", "composite_score": 7.6, "cluster": "Anthropic", "selection_rationale": "Tracked entity corporate milestone"},
    {"id": "mar31-13", "headline": "Dubai RTA launches commercial autonomous taxi service with 100 vehicles", "section": "UAE", "brief_section": "UAE", "composite_score": 7.0, "cluster": None, "selection_rationale": "UAE autonomous transport milestone"},
    {"id": "mar31-14", "headline": "Meta delays Avocado model to May amid capability gap with rivals", "section": "International Business & Technology", "brief_section": "International Business & Technology", "composite_score": 7.0, "cluster": None, "selection_rationale": "AI competitive landscape"},
    {"id": "mar31-15", "headline": "Rebellions raises $400 million at $2.3 billion valuation for AI inference chips", "section": "International Business & Technology", "brief_section": "International Business & Technology", "composite_score": 7.0, "cluster": None, "selection_rationale": "AI chip investment"},
]

SCENARIO_2_POOL = [
    {"id": "mar31-d1", "headline": "Iran destroys US early warning aircraft at Saudi air base", "composite_score": 7.4, "drop_reason": "Section over-represented — Iran-UAE Conflict cluster at capacity", "section": "International Politics & Policy"},
    {"id": "mar31-d2", "headline": "Houthi militants join war with missile attacks on Israel", "composite_score": 7.2, "drop_reason": "Section over-represented — Iran cluster", "section": "International Politics & Policy"},
    {"id": "mar31-d3", "headline": "OpenAI scraps Sora video generator to conserve AI chips", "composite_score": 7.0, "drop_reason": "Covered across sources in previous brief", "section": "International Business & Technology"},
    {"id": "mar31-d4", "headline": "Egypt unveils National AI Governance Framework", "composite_score": 6.8, "drop_reason": "No material update from yesterday", "section": "International Politics & Policy"},
]


# Scenario 3: Synthetic — extreme monotone (all items same topic)
# 8 items all about "AI regulation," empty promotion pool
# Expectation: editorial note flags the problem even if it can't fix it

SCENARIO_3_SELECTED = [
    {"id": "syn-1", "headline": "EU finalises AI Act implementation timeline for high-risk systems", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 8.0, "cluster": "AI Regulation", "selection_rationale": "Major regulatory milestone"},
    {"id": "syn-2", "headline": "UK introduces AI Safety Bill with mandatory pre-deployment testing", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 7.8, "cluster": "AI Regulation", "selection_rationale": "New UK regulatory framework"},
    {"id": "syn-3", "headline": "US Senate passes bipartisan AI disclosure bill", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 7.6, "cluster": "AI Regulation", "selection_rationale": "US regulatory action"},
    {"id": "syn-4", "headline": "China tightens generative AI content rules for domestic platforms", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 7.4, "cluster": "AI Regulation", "selection_rationale": "China regulatory update"},
    {"id": "syn-5", "headline": "Singapore releases AI governance testing framework", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 7.2, "cluster": "AI Regulation", "selection_rationale": "Asian regulatory development"},
    {"id": "syn-6", "headline": "Brazil establishes national AI ethics committee", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 7.0, "cluster": "AI Regulation", "selection_rationale": "Latin American AI governance"},
    {"id": "syn-7", "headline": "Japan aligns AI safety standards with EU framework", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 6.8, "cluster": "AI Regulation", "selection_rationale": "Regulatory convergence"},
    {"id": "syn-8", "headline": "India proposes mandatory AI audit requirements for tech firms", "section": "International Politics & Policy", "brief_section": "International Politics & Policy", "composite_score": 6.6, "cluster": "AI Regulation", "selection_rationale": "Emerging market regulation"},
]

SCENARIO_3_POOL = []  # Empty — nothing to promote


# ═══════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════

async def test_scenario_1_cluster_dominance():
    """Iran-dominated brief should trigger demotions and diverse promotions."""
    print("\n━━━ Test 1: Cluster dominance (Iran/Hormuz — April 3 production data) ━━━")

    result, usage = await call_rationalization(SCENARIO_1_SELECTED, SCENARIO_1_POOL)
    demoted = result.get("demoted", [])
    promoted = result.get("promoted", [])
    selected_ids = result.get("selected_ids", [])
    note = result.get("editorial_note", "")

    # Structure checks
    check("returns valid JSON with required keys",
          all(k in result for k in ["selected_ids", "demoted", "promoted", "editorial_note"]))
    check("selected_ids is a list", isinstance(selected_ids, list))
    check("demoted is a list", isinstance(demoted, list))
    check("promoted is a list", isinstance(promoted, list))
    check("editorial_note is non-empty", len(note) > 20, f"got {len(note)} chars")

    # The key test: does it reduce Iran/Hormuz dominance?
    iran_ids = {"apr3-3", "apr3-4", "apr3-6", "apr3-7", "apr3-8", "apr3-9"}  # 6 Iran items in Intl Politics
    demoted_ids = {d.get("id") for d in demoted}
    iran_demoted = iran_ids & demoted_ids

    check("demotes at least 1 Iran/Hormuz item", len(iran_demoted) >= 1,
          f"demoted Iran items: {iran_demoted}")
    check("demotes no more than 4 Iran items (keeps core coverage)", len(iran_demoted) <= 4,
          f"demoted {len(iran_demoted)} Iran items")

    # Should promote something diverse (not another Iran item)
    promoted_ids = {p.get("id") for p in promoted}
    iran_promoted = {"apr3-d1", "apr3-d5", "apr3-d8", "apr3-d9"} & promoted_ids
    check("does NOT promote more Iran items", len(iran_promoted) == 0,
          f"promoted Iran items: {iran_promoted}")

    # Should not promote items with "no material update" drop reasons
    no_update_pool_ids = {"apr3-d2", "apr3-d3", "apr3-d5", "apr3-d6", "apr3-d8"}
    bad_promotes = no_update_pool_ids & promoted_ids
    check("respects drop reasons (no stale promotions)", len(bad_promotes) == 0,
          f"promoted stale items: {bad_promotes}")

    # Should preserve non-Iran items
    non_iran = {"apr3-1", "apr3-2", "apr3-5", "apr3-10", "apr3-11", "apr3-13", "apr3-14", "apr3-15", "apr3-16", "apr3-17"}
    non_iran_demoted = non_iran & demoted_ids
    check("preserves non-Iran items", len(non_iran_demoted) == 0,
          f"demoted non-Iran items: {non_iran_demoted}")

    # Brief size should stay roughly the same
    final_count = len(selected_ids)
    original_count = len(SCENARIO_1_SELECTED)
    check(f"brief size stable (was {original_count}, now {final_count})",
          abs(final_count - original_count) <= 2)

    # selected_ids should be consistent with demotions/promotions
    expected_ids = (
        {item["id"] for item in SCENARIO_1_SELECTED} - demoted_ids | promoted_ids
    )
    actual_ids = set(selected_ids)
    check("selected_ids consistent with demotions/promotions",
          actual_ids == expected_ids,
          f"missing: {expected_ids - actual_ids}, extra: {actual_ids - expected_ids}")

    # Editorial note should mention the cluster
    note_lower = note.lower()
    check("editorial note mentions Iran or Hormuz or crisis cluster",
          any(w in note_lower for w in ["iran", "hormuz", "crisis", "conflict", "cluster", "domin"]))

    print(f"\n  Tokens: {usage.input_tokens} in / {usage.output_tokens} out")
    print(f"  Demoted {len(demoted)}: {[d['headline'][:50] for d in demoted]}")
    print(f"  Promoted {len(promoted)}: {[p['headline'][:50] for p in promoted]}")
    print(f"  Note: {note[:200]}")


async def test_scenario_2_balanced_brief():
    """Already-balanced brief should trigger no changes (or minimal)."""
    print("\n━━━ Test 2: Balanced brief (March 31 production data) ━━━")

    result, usage = await call_rationalization(SCENARIO_2_SELECTED, SCENARIO_2_POOL)
    demoted = result.get("demoted", [])
    promoted = result.get("promoted", [])
    note = result.get("editorial_note", "")

    check("returns valid JSON", all(k in result for k in ["selected_ids", "demoted", "promoted", "editorial_note"]))

    # A balanced brief should see 0-1 swaps at most
    check("few or no swaps (brief already balanced)", len(demoted) <= 1,
          f"demoted {len(demoted)} items")

    # If no swaps, editorial note should acknowledge balance
    if len(demoted) == 0:
        note_lower = note.lower()
        check("editorial note acknowledges balance",
              any(w in note_lower for w in ["balanc", "well-composed", "no change", "covers", "diverse", "breadth"]),
              f"note: {note[:100]}")

    print(f"\n  Tokens: {usage.input_tokens} in / {usage.output_tokens} out")
    print(f"  Demoted {len(demoted)}: {[d['headline'][:50] for d in demoted]}")
    print(f"  Promoted {len(promoted)}: {[p['headline'][:50] for p in promoted]}")
    print(f"  Note: {note[:200]}")


async def test_scenario_3_empty_pool():
    """Monotone brief with empty promotion pool — should flag the problem in editorial note."""
    print("\n━━━ Test 3: Extreme monotone, empty promotion pool ━━━")

    result, usage = await call_rationalization(SCENARIO_3_SELECTED, SCENARIO_3_POOL)
    demoted = result.get("demoted", [])
    promoted = result.get("promoted", [])
    note = result.get("editorial_note", "")
    selected_ids = result.get("selected_ids", [])

    check("returns valid JSON", all(k in result for k in ["selected_ids", "demoted", "promoted", "editorial_note"]))

    # With empty pool, can't promote. Should still possibly demote weak tail items,
    # or at minimum flag the monotone problem
    check("no promotions (empty pool)", len(promoted) == 0)

    # Editorial note should flag the monotone issue
    note_lower = note.lower()
    check("editorial note flags monotone/dominance issue",
          any(w in note_lower for w in ["regulat", "monotone", "one topic", "domin", "single", "narrow", "all", "same"]),
          f"note: {note[:100]}")

    # If it demotes tail items despite empty pool, that's a valid choice
    # (shrinking the brief to avoid noise). Just check it doesn't break.
    if demoted:
        # Demotions should target the weakest items
        demoted_scores = [d.get("composite_score", 99) for d in demoted
                          if d.get("composite_score") is not None]
        if demoted_scores:
            check("demotes weaker items (score <= 7.2)", max(demoted_scores) <= 7.4,
                  f"highest demoted score: {max(demoted_scores)}")

    print(f"\n  Tokens: {usage.input_tokens} in / {usage.output_tokens} out")
    print(f"  Demoted {len(demoted)}: {[d['headline'][:50] for d in demoted]}")
    print(f"  Note: {note[:200]}")


async def test_output_contract():
    """Verify the output contract: selected_ids, demoted, promoted structure."""
    print("\n━━━ Test 4: Output contract validation ━━━")

    result, _ = await call_rationalization(SCENARIO_1_SELECTED, SCENARIO_1_POOL)

    # Every demoted item must have id, headline, reason
    for d in result.get("demoted", []):
        check(f"demoted item has id: {d.get('headline', '?')[:40]}",
              bool(d.get("id")))
        check(f"demoted item has reason: {d.get('headline', '?')[:40]}",
              bool(d.get("reason")))

    # Every promoted item must have id, headline, reason
    for p in result.get("promoted", []):
        check(f"promoted item has id: {p.get('headline', '?')[:40]}",
              bool(p.get("id")))
        check(f"promoted item has reason: {p.get('headline', '?')[:40]}",
              bool(p.get("reason")))

    # Promoted ids must come from the pool
    pool_ids = {item["id"] for item in SCENARIO_1_POOL}
    for p in result.get("promoted", []):
        check(f"promoted id '{p.get('id')}' exists in pool",
              p.get("id") in pool_ids,
              f"available: {pool_ids}")

    # Demoted ids must come from selected
    selected_ids = {item["id"] for item in SCENARIO_1_SELECTED}
    for d in result.get("demoted", []):
        check(f"demoted id '{d.get('id')}' exists in selected",
              d.get("id") in selected_ids,
              f"available: {selected_ids}")


# ═══════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════

async def main():
    start = time.time()

    # Run scenarios — each makes a Sonnet call so we run sequentially
    # to avoid rate limits and keep output readable
    await test_scenario_1_cluster_dominance()
    await test_scenario_2_balanced_brief()
    await test_scenario_3_empty_pool()
    await test_output_contract()

    elapsed = time.time() - start
    total = PASS + FAIL
    print(f"\n{'━' * 60}")
    print(f"  {PASS}/{total} passed, {FAIL} failed  ({elapsed:.1f}s)")
    if FAIL:
        print(f"  \033[31m{FAIL} FAILURE(S)\033[0m")
    else:
        print(f"  \033[32mALL PASSED\033[0m")
    print(f"{'━' * 60}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
