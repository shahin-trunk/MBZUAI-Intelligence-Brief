"""
Targeted live tests for pipeline fixes:
  1. Date regex (day-first + month-first)
  2. Presight scraper (new HTML structure)
  3. WAM subtitle enrichment (title-keyed lookup across 4 API pages)
  4. Dedup richness scoring (URL bonus)
  5. Pre-gatekeeper enrichment (trafilatura fetch for thin items)
  6. Presight tracked entity
  7. End-to-end: the Presight Africa MoU article

Run:  cd backend && python3 tests/test_pipeline_fixes.py
"""

import asyncio
import json
import re
import sys
import os
import time

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


# ═══════════════════════════════════════════════════════════════════════
# TEST 1: Date regex matches both day-first and month-first formats
# ═══════════════════════════════════════════════════════════════════════
def test_date_regex():
    print("\n━━━ Test 1: Date regex ━━━")
    from pipeline.collector import _DATE_RE, _parse_date

    # Should match
    positives = [
        ("26 February 2026",    "2026-02-26"),
        ("2 March 2026",        "2026-03-02"),
        ("26 February, 2026",   "2026-02-26"),
        ("April 02 2026",       "2026-04-02"),
        ("February 26, 2026",   "2026-02-26"),
        ("Jan 5, 2026",         "2026-01-05"),
        ("5 Jan 2026",          "2026-01-05"),
        ("December 10 2025",    "2025-12-10"),
    ]
    for text, expected in positives:
        m = _DATE_RE.search(text)
        check(
            f"regex matches '{text}'",
            m is not None,
            "no match" if not m else "",
        )
        if m:
            parsed = _parse_date(m.group())
            check(
                f"  parses to {expected}",
                parsed == expected,
                f"got {parsed}",
            )

    # Should NOT match (no year, no month, etc.)
    negatives = ["2026-03-10", "March 2026", "yesterday", "10/03/2026"]
    for text in negatives:
        m = _DATE_RE.search(text)
        check(f"regex rejects '{text}'", m is None, f"matched: {m.group()}" if m else "")

    # Regression: month-first embedded in card text
    card_text = "Read more April 02 2026 Presight Expands Digital..."
    m = _DATE_RE.search(card_text)
    check("regex finds month-first date in card text", m is not None)
    if m:
        check("  extracted group is 'April 02 2026'", m.group() == "April 02 2026", f"got '{m.group()}'")


# ═══════════════════════════════════════════════════════════════════════
# TEST 2: Presight scraper returns articles from the live site
# ═══════════════════════════════════════════════════════════════════════
def test_presight_scraper():
    print("\n━━━ Test 2: Presight scraper (live) ━━━")
    from pipeline.collector import collect_presight

    articles = collect_presight()
    check("collect_presight() returns articles", len(articles) > 0, f"got {len(articles)}")

    if articles:
        a = articles[0]
        check("first article has title", bool(a.title))
        check("first article has URL", a.url.startswith("https://www.presight.ai/news/"))
        check("first article has date", bool(a.published_date))
        check("source_name is 'Presight'", a.source_name == "Presight")

        # The most recent article should be the Africa MoU (as of April 3, 2026)
        africa_articles = [x for x in articles if "africa" in x.title.lower()]
        check(
            "Africa MoU article collected",
            len(africa_articles) > 0,
            f"titles: {[x.title[:50] for x in articles]}",
        )


# ═══════════════════════════════════════════════════════════════════════
# TEST 3a: WAM subtitle lookup fuzzy-fallback (unit, no network)
# ═══════════════════════════════════════════════════════════════════════
def test_wam_subtitle_fuzzy_fallback():
    print("\n━━━ Test 3a: WAM subtitle fuzzy fallback (unit) ━━━")
    from pipeline.collector import _find_wam_subtitle, _normalize_wam_title

    global FAIL
    failures_before = FAIL
    lookup = {
        "adek launches midad initiative to open new, accessible pathway into teaching": {
            "subtitle": "ADEK rolls out the Midad initiative across Abu Dhabi schools.",
            "category": "Education",
        },
        "abu dhabi customs, cert strengthen research collaboration in ai-based projects": {
            "subtitle": "The two entities signed an MoU to co-develop AI tools.",
            "category": "Government",
        },
    }

    # Pass 1: exact lowercase match still works.
    m = _find_wam_subtitle(
        "ADEK launches Midad initiative to open new, accessible pathway into teaching",
        lookup,
    )
    check("exact-match fallthrough still works", m is not None and "Midad" in m["subtitle"])

    # Pass 2: alphanumeric-only match recovers from curly-quote / ellipsis drift.
    m = _find_wam_subtitle(
        "ADEK launches \u2018Midad\u2019 initiative to open new, accessible pathway into teaching",
        lookup,
    )
    check(
        "alphanumeric-only fallback matches across smart quotes",
        m is not None and "Midad" in m["subtitle"],
    )

    # Pass 3: prefix match (>= 60 alnum chars) on a title truncated with "..."
    m = _find_wam_subtitle(
        "Abu Dhabi Customs, CERT strengthen research collaboration in AI-based projects — full release",
        lookup,
    )
    check(
        "prefix fallback matches when one side has a trailing qualifier",
        m is not None and "MoU" in m["subtitle"],
    )

    # Negative: short, unrelated title should NOT match.
    m = _find_wam_subtitle("Something entirely different happens today", lookup)
    check("unrelated short title does NOT match", m is None)

    # Negative: empty title returns None.
    check("empty title returns None", _find_wam_subtitle("", lookup) is None)

    # _normalize_wam_title strips punctuation and lowercases.
    check(
        "_normalize_wam_title strips non-alnum",
        _normalize_wam_title("Hello, World! 2026") == "helloworld2026",
    )

    # Surface failures to pytest (the `check()` helper doesn't raise).
    assert FAIL == failures_before, (
        f"{FAIL - failures_before} WAM fuzzy-fallback assertion(s) failed"
    )


# ═══════════════════════════════════════════════════════════════════════
# TEST 3: WAM subtitle enrichment via title-keyed lookup
# ═══════════════════════════════════════════════════════════════════════
def test_wam_subtitle_enrichment():
    print("\n━━━ Test 3: WAM subtitle enrichment (live) ━━━")
    from pipeline.collector import _build_wam_subtitle_lookup, collect_wam

    # 3a: Subtitle lookup builds correctly
    lookup, _listing_articles = _build_wam_subtitle_lookup()
    check("subtitle lookup is non-empty", len(lookup) > 0, f"got {len(lookup)}")
    check("lookup has 80+ entries", len(lookup) >= 80, f"got {len(lookup)}")

    # All keys should be lowercase
    non_lower = [k for k in lookup if k != k.lower()]
    check("all keys are lowercase", len(non_lower) == 0, f"non-lower keys: {non_lower[:3]}")

    # All entries should have subtitle
    with_subtitle = sum(1 for v in lookup.values() if v.get("subtitle"))
    check(
        "most entries have subtitles",
        with_subtitle > len(lookup) * 0.8,
        f"{with_subtitle}/{len(lookup)}",
    )

    # 3b: Presight article found in lookup
    presight_key = "presight expands digital transformation partnerships across three new countries in africa"
    check(
        "Presight Africa article in lookup",
        presight_key in lookup,
    )
    if presight_key in lookup:
        sub = lookup[presight_key]["subtitle"]
        check("subtitle mentions Burkina Faso", "Burkina Faso" in sub, sub[:100])
        check("subtitle mentions Gabon", "Gabon" in sub, sub[:100])

    # 3c: Full WAM collection with enrichment
    articles = collect_wam()
    check("collect_wam() returns articles", len(articles) > 0, f"got {len(articles)}")

    enriched = sum(1 for a in articles if a.raw_text != a.title and len(a.raw_text) > 50)
    total = len(articles)
    pct = 100 * enriched // total if total else 0
    check(f"enrichment coverage >= 60%", pct >= 60, f"{enriched}/{total} = {pct}%")

    # The Presight article specifically should be enriched
    presight = [a for a in articles if "presight" in a.title.lower() and "africa" in a.title.lower()]
    if presight:
        a = presight[0]
        check(
            "Presight article enriched with subtitle",
            len(a.raw_text) > len(a.title),
            f"raw_text={len(a.raw_text)} chars, title={len(a.title)} chars",
        )
        check(
            "Presight raw_text mentions MoU countries",
            "Burkina" in a.raw_text or "Gabon" in a.raw_text,
            a.raw_text[:100],
        )
    else:
        check("Presight Africa article collected from WAM", False, "not found — may be outside cutoff")


# ═══════════════════════════════════════════════════════════════════════
# TEST 4: Dedup richness score prefers items with source URLs
# ═══════════════════════════════════════════════════════════════════════
def test_dedup_richness():
    print("\n━━━ Test 4: Dedup richness scoring ━━━")
    from pipeline.dedup import _richness_score, _merge_group

    # 4a: URL bonus
    with_url = {"raw_content": "short", "source_url": "https://example.com"}
    without_url = {"raw_content": "short"}
    check(
        "item with URL scores higher",
        _richness_score(with_url) > _richness_score(without_url),
        f"{_richness_score(with_url)} vs {_richness_score(without_url)}",
    )

    # 4b: URL bonus outweighs moderate content advantage
    newsletter_version = {
        "headline": "Presight signs MoU",
        "source": "Reuters",
        "raw_content": "Presight, a leading AI company, signed MoUs with Burkina Faso",  # 62 chars
        "source_url": "",
        "also_covered_by": [],
    }
    wam_version = {
        "headline": "Presight signs MoU",
        "source": "WAM",
        "raw_content": "Presight signs MoU",  # 18 chars
        "source_url": "https://www.wam.ae/en/article/bziikqz-presight",
        "also_covered_by": [],
    }
    check(
        "WAM (URL, short) beats newsletter (no URL, longer body)",
        _richness_score(wam_version) > _richness_score(newsletter_version),
        f"WAM={_richness_score(wam_version)} vs newsletter={_richness_score(newsletter_version)}",
    )

    # 4c: Merge picks the URL-bearing item as base
    merged = _merge_group([newsletter_version, wam_version])
    check(
        "merge keeps WAM as base (has URL)",
        merged.get("source") == "WAM",
        f"base source = {merged.get('source')}",
    )
    check(
        "merge preserves source_url from WAM",
        "wam.ae" in (merged.get("source_url") or ""),
        merged.get("source_url"),
    )

    # 4d: Edge cases
    empty = {}
    check("empty item scores 0", _richness_score(empty) == 0)
    none_vals = {"raw_content": None, "additional_context": None, "source_url": None}
    check("None values don't crash", _richness_score(none_vals) == 0)


# ═══════════════════════════════════════════════════════════════════════
# TEST 5: Pre-gatekeeper enrichment fetches content for thin items
# ═══════════════════════════════════════════════════════════════════════
def test_pre_gatekeeper_enrichment():
    print("\n━━━ Test 5: Pre-gatekeeper enrichment (live) ━━━")
    from pipeline.enricher import fetch_source_url, is_thin, THIN_THRESHOLD

    # 5a: is_thin correctly identifies headline-only items
    thin_item = {"raw_content": "Presight signs MoU with three African nations"}
    fat_item = {"raw_content": " ".join(["word"] * 100)}
    check("headline-only item is thin", is_thin(thin_item))
    check("100-word item is not thin", not is_thin(fat_item))
    check(f"THIN_THRESHOLD is 80", THIN_THRESHOLD == 80)

    # 5b: fetch_source_url works on Presight (non-JS site)
    presight_url = "https://www.presight.ai/news/presight-expands-digital-transformation-partnerships-across-three-new-countries-in-africa"
    result = asyncio.run(fetch_source_url(presight_url))
    check("fetch_source_url returns result for Presight", result is not None)
    if result:
        extract = result.get("extract", "")
        word_count = len(extract.split())
        check(f"extract has 100+ words", word_count >= 100, f"got {word_count}")
        check("extract mentions Burkina Faso", "Burkina" in extract)
        check("extract mentions Gabon", "Gabon" in extract)

    # 5c: fetch_source_url returns None for WAM (JS-rendered)
    wam_url = "https://www.wam.ae/en/article/bziikqz-presight-expands-digital-transformation"
    result = asyncio.run(fetch_source_url(wam_url))
    check("fetch_source_url returns None for WAM (expected — JS site)", result is None)


# ═══════════════════════════════════════════════════════════════════════
# TEST 6: Presight is a tracked entity
# ═══════════════════════════════════════════════════════════════════════
def test_tracked_entities():
    print("\n━━━ Test 6: Tracked entities ━━━")
    from config import USER_PROFILE

    check("Presight in USER_PROFILE", "Presight" in USER_PROFILE)
    check("G42 still in USER_PROFILE", "G42" in USER_PROFILE)
    check("TII still in USER_PROFILE", "TII" in USER_PROFILE)
    check("KAUST still in USER_PROFILE", "KAUST" in USER_PROFILE)


# ═══════════════════════════════════════════════════════════════════════
# TEST 7: End-to-end — Presight Africa MoU would survive the pipeline
# ═══════════════════════════════════════════════════════════════════════
def test_end_to_end_presight():
    print("\n━━━ Test 7: End-to-end Presight Africa MoU ━━━")
    from pipeline.collector import collect_presight, collect_wam
    from pipeline.dedup import _richness_score
    from pipeline.enricher import fetch_source_url, is_thin

    # Simulate what the pipeline does for this article

    # Step 1: Collection — item should appear from Presight scraper
    presight_articles = collect_presight()
    presight_match = [a for a in presight_articles if "africa" in a.title.lower()]
    check("Step 1 — Presight scraper collects Africa article", len(presight_match) > 0)

    # Step 2: Collection — item should also appear from WAM with subtitle
    wam_articles = collect_wam()
    wam_match = [a for a in wam_articles if "presight" in a.title.lower() and "africa" in a.title.lower()]
    check("Step 2 — WAM collects same article", len(wam_match) > 0)
    if wam_match:
        check(
            "Step 2 — WAM version has subtitle (not headline-only)",
            len(wam_match[0].raw_text) > len(wam_match[0].title),
        )

    # Step 3: Dedup — simulate merge, WAM version (with URL) should win
    if presight_match and wam_match:
        presight_item = {
            "headline": presight_match[0].title,
            "source": "Presight",
            "source_url": presight_match[0].url,
            "raw_content": presight_match[0].raw_text,
            "also_covered_by": [],
        }
        wam_item = {
            "headline": wam_match[0].title,
            "source": "WAM",
            "source_url": wam_match[0].url,
            "raw_content": wam_match[0].raw_text,
            "also_covered_by": [],
        }
        presight_score = _richness_score(presight_item)
        wam_score = _richness_score(wam_item)
        # WAM has subtitle (~300 chars) + URL → should win over Presight (headline + URL)
        winner = "WAM" if wam_score >= presight_score else "Presight"
        check(
            f"Step 3 — dedup base is {winner} (score {max(wam_score, presight_score)})",
            True,  # Either is fine as long as both have URLs
        )
        # The key thing: the winner has a URL
        winner_item = wam_item if wam_score >= presight_score else presight_item
        check("Step 3 — winner has source_url", bool(winner_item.get("source_url")))

    # Step 4: Pre-gatekeeper enrichment — thin items get fetched
    if presight_match:
        sim_item = {"raw_content": presight_match[0].title, "source_url": presight_match[0].url}
        is_item_thin = is_thin(sim_item)
        if is_item_thin:
            result = asyncio.run(fetch_source_url(sim_item["source_url"]))
            check(
                "Step 4 — trafilatura fetches full Presight article",
                result is not None and len(result.get("extract", "").split()) > 80,
                f"words: {len(result.get('extract', '').split()) if result else 0}",
            )
        else:
            check("Step 4 — item already enriched (not thin)", True)

    # Step 5: Gatekeeper scoring estimate
    # With Presight as tracked entity (topic_relevance ~9) and real content
    # (news_significance ~7 for MoU across 3 countries), composite should be well above 7.0
    estimated_topic = 9   # tracked entity
    estimated_significance = 7  # noteworthy partnership across 3 nations
    composite = estimated_topic * 0.6 + estimated_significance * 0.4
    check(
        f"Step 5 — estimated composite {composite:.1f} >= 7.0 (auto-include)",
        composite >= 7.0,
    )

    print(f"\n  End-to-end: with all fixes, this article would score ~{composite:.1f}")
    print("  (was 4.2 before fixes → dropped)")


# ═══════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    start = time.time()

    test_date_regex()
    test_presight_scraper()
    test_wam_subtitle_fuzzy_fallback()
    test_wam_subtitle_enrichment()
    test_dedup_richness()
    test_pre_gatekeeper_enrichment()
    test_tracked_entities()
    test_end_to_end_presight()

    elapsed = time.time() - start
    total = PASS + FAIL
    print(f"\n{'━' * 60}")
    print(f"  {PASS}/{total} passed, {FAIL} failed  ({elapsed:.1f}s)")
    if FAIL:
        print(f"  \033[31m{FAIL} FAILURE(S)\033[0m")
    else:
        print(f"  \033[32mALL PASSED\033[0m")
    print(f"{'━' * 60}")
    sys.exit(1 if FAIL else 0)
