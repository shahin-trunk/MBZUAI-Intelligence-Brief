"""Tests for the post-gatekeeper demerge step.

Run:  cd backend && python3 tests/test_demerge.py

Suite 1: Unit tests — synthetic data, no network / API key required.
Suite 2: Historical replay — runs demerge against real gatekeeper outputs
         and scout data from the output/ directory.
"""

from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

_backend = str(Path(__file__).resolve().parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger("test_demerge")


# Copied from orchestrator.py to avoid importing the full module
# (enricher.py uses dict|None syntax incompatible with Python 3.9)
def _normalize_for_match(headline: str) -> str:
    """Normalize a headline for fuzzy matching during rejoin."""
    return re.sub(r"[^\w\s]", "", headline.lower()).strip()[:60]


def demerge_selected_items(
    selected: list[dict],
    scout_items: list[dict],
) -> tuple[list[dict], int]:
    """Split gatekeeper-selected items that contain semicolon-merged headlines."""
    if not scout_items:
        return selected, 0

    result: list[dict] = []
    merge_count = 0

    for item in selected:
        headline = item.get("headline", "")

        if ";" not in headline:
            result.append(item)
            continue

        parts = [p.strip() for p in headline.split(";") if p.strip()]
        if len(parts) < 2:
            result.append(item)
            continue

        matched_any = False
        demerged_items = []

        for part in parts:
            part_norm = _normalize_for_match(part)
            best_match = None
            best_score = 0.0

            for scout in scout_items:
                scout_headline = scout.get("headline", "")
                scout_norm = _normalize_for_match(scout_headline)
                score = SequenceMatcher(None, part_norm, scout_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_match = scout

            if best_match and best_score >= 0.4:
                matched_any = True
                new_item = dict(item)
                new_item["headline"] = best_match.get("headline", part)
                new_item["source"] = best_match.get("source", item.get("source", ""))
                new_item["source_url"] = best_match.get("source_url", item.get("source_url", ""))
                new_item["summary"] = best_match.get("summary", "")
                new_item["entities"] = best_match.get("entities", [])
                new_item["raw_content"] = best_match.get("raw_content", "")
                new_item["additional_context"] = best_match.get("additional_context", "")
                new_item["date"] = best_match.get("date", item.get("date", ""))
                new_item["date_evidence"] = best_match.get("date_evidence", item.get("date_evidence", ""))
                new_item["also_covered_by"] = best_match.get("also_covered_by", [])
                new_item.pop("id", None)
                demerged_items.append(new_item)
            else:
                new_item = dict(item)
                new_item["headline"] = part
                new_item.pop("id", None)
                demerged_items.append(new_item)

        if matched_any and len(demerged_items) >= 2:
            result.extend(demerged_items)
            merge_count += 1
            logger.info(
                f"Demerge: split '{headline[:60]}' → "
                f"{len(demerged_items)} items"
            )
        else:
            result.append(item)

    for i, item in enumerate(result, start=1):
        item["rank"] = i

    return result, merge_count

# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _make_scout(headline: str, url: str = "", source: str = "TestSource") -> dict:
    return {
        "headline": headline,
        "source": source,
        "source_url": url or f"https://example.com/{headline[:20].replace(' ','-')}",
        "date": "2026-03-30",
        "date_evidence": "Published date from test",
        "summary": headline,
        "raw_content": headline,
        "additional_context": "",
        "entities": [],
        "category": "",
    }


def _make_selected(headline: str, score: float = 7.5, section: str = "UAE", rank: int = 1) -> dict:
    return {
        "headline": headline,
        "rank": rank,
        "brief_section": section,
        "composite_score": score,
        "topic_relevance": 8,
        "news_significance": 7,
        "selection_rationale": "Test",
        "source": "TestSource",
        "source_url": "https://example.com/merged",
        "date": "2026-03-30",
        "raw_content": "",
        "additional_context": "",
    }


# ── SUITE 1: Unit Tests ──────────────────────────────────────────────────────

def test_no_semicolons_passthrough():
    """Items without semicolons pass through unchanged."""
    scouts = [_make_scout("UAE signs deal with India")]
    selected = [_make_selected("UAE signs deal with India")]
    result, count = demerge_selected_items(selected, scouts)
    assert count == 0, f"Expected 0 merges, got {count}"
    assert len(result) == 1
    assert result[0]["headline"] == "UAE signs deal with India"


def test_semicolon_split():
    """Semicolon-merged headline is split into two separate items."""
    scouts = [
        _make_scout("Iran attacks Kuwait military camp", url="https://wam.ae/iran-attacks"),
        _make_scout("UAE Cabinet praises armed forces", url="https://wam.ae/cabinet-praises"),
    ]
    selected = [_make_selected(
        "Iran attacks Kuwait military camp; UAE Cabinet praises armed forces",
        score=9.0,
    )]
    result, count = demerge_selected_items(selected, scouts)
    assert count == 1, f"Expected 1 merge split, got {count}"
    assert len(result) == 2, f"Expected 2 items, got {len(result)}"
    # Each should have matched back to its scout item
    headlines = {r["headline"] for r in result}
    assert "Iran attacks Kuwait military camp" in headlines
    assert "UAE Cabinet praises armed forces" in headlines
    # Source URLs should come from the scout items, not the merged item
    urls = {r["source_url"] for r in result}
    assert "https://wam.ae/iran-attacks" in urls
    assert "https://wam.ae/cabinet-praises" in urls


def test_scoring_inherited():
    """Demerged items inherit the gatekeeper's scoring metadata."""
    scouts = [
        _make_scout("Story A"),
        _make_scout("Story B"),
    ]
    selected = [_make_selected("Story A; Story B", score=8.5, section="UAE")]
    result, count = demerge_selected_items(selected, scouts)
    assert count == 1
    for item in result:
        assert item["composite_score"] == 8.5
        assert item["brief_section"] == "UAE"


def test_ranks_renumbered():
    """Ranks are sequential after demerge."""
    scouts = [_make_scout("A"), _make_scout("B"), _make_scout("C")]
    selected = [
        _make_selected("A; B", rank=1),
        _make_selected("C", rank=2),
    ]
    result, count = demerge_selected_items(selected, scouts)
    assert count == 1
    ranks = [r["rank"] for r in result]
    assert ranks == [1, 2, 3], f"Expected [1,2,3], got {ranks}"


def test_no_match_keeps_original():
    """If no scout item matches, keep the merged item as-is."""
    scouts = [_make_scout("Completely unrelated story")]
    selected = [_make_selected("Alpha event; Beta event")]
    result, count = demerge_selected_items(selected, scouts)
    # Can't match either part — should keep original
    assert count == 0
    assert len(result) == 1


def test_mixed_items():
    """Mix of merged and non-merged items."""
    scouts = [
        _make_scout("Iran attacks Kuwait"),
        _make_scout("UAE Cabinet praises armed forces"),
        _make_scout("NeurIPS reverses paper ban"),
    ]
    selected = [
        _make_selected("Iran attacks Kuwait; UAE Cabinet praises armed forces", rank=1),
        _make_selected("NeurIPS reverses paper ban", rank=2),
    ]
    result, count = demerge_selected_items(selected, scouts)
    assert count == 1
    assert len(result) == 3
    headlines = [r["headline"] for r in result]
    assert "NeurIPS reverses paper ban" in headlines


def test_three_way_merge():
    """Three items merged with two semicolons."""
    scouts = [_make_scout("A happened"), _make_scout("B happened"), _make_scout("C happened")]
    selected = [_make_selected("A happened; B happened; C happened")]
    result, count = demerge_selected_items(selected, scouts)
    assert count == 1
    assert len(result) == 3


def test_empty_scout_list():
    """Empty scout list — demerge is a no-op."""
    selected = [_make_selected("A; B")]
    result, count = demerge_selected_items(selected, [])
    assert count == 0
    assert len(result) == 1


def test_ids_cleared():
    """Demerged items should have IDs cleared for re-assignment."""
    scouts = [_make_scout("A"), _make_scout("B")]
    selected = [_make_selected("A; B")]
    selected[0]["id"] = "old-id"
    result, count = demerge_selected_items(selected, scouts)
    assert count == 1
    for item in result:
        assert "id" not in item, f"ID should be cleared, got {item.get('id')}"


def run_unit_tests():
    print(f"\n{_HR}")
    print("SUITE 1: Unit Tests")
    print(_HR)

    tests = [
        ("No semicolons → passthrough", test_no_semicolons_passthrough),
        ("Semicolon split into 2 items", test_semicolon_split),
        ("Scoring metadata inherited", test_scoring_inherited),
        ("Ranks renumbered after split", test_ranks_renumbered),
        ("No match → keep original", test_no_match_keeps_original),
        ("Mixed merged + non-merged", test_mixed_items),
        ("Three-way merge split", test_three_way_merge),
        ("Empty scout list → no-op", test_empty_scout_list),
        ("IDs cleared for re-assignment", test_ids_cleared),
    ]

    for name, fn in tests:
        try:
            fn()
            _report(name, True)
        except Exception as e:
            _report(name, False, str(e))


# ── SUITE 2: Historical Replay ───────────────────────────────────────────────

def run_historical_replay():
    print(f"\n{_HR}")
    print("SUITE 2: Historical Replay")
    print(_HR)

    output_dir = Path(_backend) / "output"

    # Find all dates that have both gatekeeper output and scout output
    gk_files = sorted(output_dir.glob("gatekeeper_output_*.json"))
    if not gk_files:
        print("  SKIP: No gatekeeper output files found")
        return

    for gk_file in gk_files:
        date = gk_file.stem.replace("gatekeeper_output_", "")
        # Prefer scout_output (post-filter) as it's closer to what the gatekeeper saw
        scout_file = output_dir / f"scout_output_{date}.json"
        if not scout_file.exists():
            scout_file = output_dir / f"scout_output_raw_{date}.json"
        if not scout_file.exists():
            continue

        with open(gk_file) as f:
            gk_data = json.load(f)
        with open(scout_file) as f:
            scout_items = json.load(f)

        selected = gk_data.get("selected", [])
        merged_count = sum(1 for s in selected if ";" in s.get("headline", ""))

        if merged_count == 0:
            print(f"\n  {date}: {len(selected)} selected, 0 merged — skip")
            continue

        result, demerge_count = demerge_selected_items(list(selected), scout_items)

        print(f"\n  {date}: {len(selected)} selected → {len(result)} after demerge "
              f"({demerge_count} merged items split)")

        _report(f"  {date}: demerge count matches merged count",
                demerge_count == merged_count,
                f"Expected {merged_count} demerges, got {demerge_count}")

        # Show what was split
        for item in selected:
            h = item.get("headline", "")
            if ";" in h:
                parts = [p.strip() for p in h.split(";")]
                matched_items = [r for r in result if r["headline"] != h and
                                 any(SequenceMatcher(None,
                                     _normalize_for_match(r["headline"]),
                                     _normalize_for_match(p)).ratio() >= 0.4
                                     for p in parts)]
                if matched_items:
                    print(f"    MERGED: {h[:80]}...")
                    for mi in matched_items:
                        src_match = mi["source_url"] != item.get("source_url", "")
                        print(f"      → {mi['headline'][:70]} "
                              f"(url={'matched' if src_match else 'inherited'})")

        # Verify ranks are sequential
        ranks = [r["rank"] for r in result]
        _report(f"  {date}: ranks sequential", ranks == list(range(1, len(result) + 1)),
                f"Ranks: {ranks}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    run_unit_tests()
    run_historical_replay()

    print(f"\n{_HR}")
    print(f"Results: {passed} passed, {failed} failed")
    print(_HR)
    sys.exit(1 if failed else 0)
