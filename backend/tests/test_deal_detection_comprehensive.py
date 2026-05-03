"""Comprehensive deal detection tests.

Covers:
  1. Historical replay across all local gatekeeper outputs (~122 items)
  2. Deal / model-release mutual exclusion
  3. Judge message formatting (is_deal flag presence)
  4. Deal query construction edge cases
  5. Newsletter-sourced deal items (the OpenAI Apr-2 failure scenario)
  6. Enricher flow assertions (thin threshold, query branch selection)
  7. Regex boundary & edge cases (false positives documented)
  8. Supabase historical items (known Cloud Run outputs)

All tests are deterministic — no API calls, no network required.
Python 3.9 compatible (functions copied from enricher.py to avoid
3.10+ syntax import errors).
"""

import glob
import json
import os
import re

import pytest

# ---------------------------------------------------------------------------
# Copied from enricher.py (Python 3.9 compat)
# ---------------------------------------------------------------------------

THIN_THRESHOLD = 80

DEAL_CUE_RE = re.compile(
    r"\b("
    r"funding round|fundraise[ds]?|series [a-z]|seed round|"
    r"raise[ds]? \$|raising \$|"
    r"acqui(?:res?|red?|sition|ring)|merger?|merg(?:e[ds]?|ing)|"
    r"(?:pre|post)[- ]money valuation|valued at|"
    r"ipo(?:\b|'d)|going public|"
    r"investment round|"
    r"(?:led|backed) by .{0,30}(?:capital|ventures?|partners?)"
    r")\b",
    re.IGNORECASE,
)


def _normalise_raw_content(raw_content):
    if isinstance(raw_content, (dict, list)):
        return json.dumps(raw_content, ensure_ascii=False)
    return str(raw_content) if raw_content else ""


def is_thin(item):
    text = _normalise_raw_content(item.get("raw_content", ""))
    return len(text.split()) < THIN_THRESHOLD


def is_probable_deal(item):
    if item.get("is_model_release"):
        return False
    text = f"{item.get('headline', '')} {_normalise_raw_content(item.get('raw_content', ''))}"
    return bool(DEAL_CUE_RE.search(text))


def _build_deal_queries(headline, entities=None):
    company = ""
    if entities:
        company = entities[0].replace("**", "").strip()
    else:
        company = headline.split()[0] if headline else ""
    queries = []
    if company:
        queries.append({
            "query": f"{company} funding round total amount valuation",
            "query_intent": "deal_terms",
        })
        queries.append({
            "query": f"{company} investors lead round Series",
            "query_intent": "deal_parties",
        })
    queries.append({
        "query": f"{headline} deal terms valuation",
        "query_intent": "deal_overview",
    })
    return queries


def _build_judge_message(headline, raw_content, extracts, is_model_release, is_deal):
    """Replicate the user message construction from evaluate_content()."""
    extracts_text = ""
    if extracts:
        for i, ext in enumerate(extracts, 1):
            extracts_text += (
                f"\n--- Supplementary Extract {i} "
                f"(from {ext.get('url', 'unknown')}) ---\n"
            )
            extracts_text += ext.get("extract", "")[:3000] + "\n"

    return (
        f"Today's date: 2026-04-02\n"
        f"headline: {headline}\n"
        f"raw_content: {raw_content}\n"
        f"supplementary_extracts: {extracts_text if extracts_text else '(none yet)'}\n"
        f"is_model_release: {is_model_release}\n"
        f"is_deal: {is_deal}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "output"
)


def _load_all_gatekeeper_items():
    """Load every selected item from all local gatekeeper outputs."""
    items = []
    pattern = os.path.join(OUTPUT_DIR, "gatekeeper_output_*.json")
    for path in sorted(glob.glob(pattern)):
        date = os.path.basename(path).replace("gatekeeper_output_", "").replace(".json", "")
        with open(path) as f:
            data = json.load(f)
        for item in data.get("selected", []):
            item["_test_date"] = date
            items.append(item)
    return items


# ═══════════════════════════════════════════════════════════════════════════
# 1. HISTORICAL REPLAY
# ═══════════════════════════════════════════════════════════════════════════

class TestHistoricalReplay:
    """Classify every item from local gatekeeper outputs."""

    @pytest.fixture(scope="class")
    def all_items(self):
        items = _load_all_gatekeeper_items()
        assert len(items) > 50, f"Expected 50+ items, got {len(items)}"
        return items

    # -- Known deals must be detected --

    KNOWN_DEAL_SUBSTRINGS = [
        "OpenAI finalises $100B+ funding round",
        "merges ADQ into L'IMAD",
        "Anthropic Acquires Computer-Use Agent Startup Vercept",
        "Nscale raises $2B at $14.6B valuation",
        "OpenAI acquires Promptfoo",
    ]

    def test_known_deals_detected(self, all_items):
        for substr in self.KNOWN_DEAL_SUBSTRINGS:
            matches = [i for i in all_items if substr in i.get("headline", "")]
            assert matches, f"No item found with substring: {substr}"
            for item in matches:
                assert is_probable_deal(item), (
                    f"Expected deal=True for: {item['headline'][:80]}"
                )

    # -- Known non-deals must NOT be detected --

    KNOWN_NON_DEAL_SUBSTRINGS = [
        "Iran strikes Amazon data centres",
        "Google DeepMind releases Gemini 3.1 Pro",
        "Trump signals",
        "FlashAttention-4",
        "METR time-horizon leaderboard",
        "ChatGPT GPT-5.3 Instant",
        "AI2 releases OLMo Hybrid",
        "UAE air defences currently responding",
        "Iran names Khamenei's son",
        "MBZUAI researchers publish Mobile-O",
    ]

    def test_known_non_deals_not_detected(self, all_items):
        for substr in self.KNOWN_NON_DEAL_SUBSTRINGS:
            matches = [i for i in all_items if substr in i.get("headline", "")]
            if not matches:
                continue  # Item may not exist in local data
            for item in matches:
                assert not is_probable_deal(item), (
                    f"Expected deal=False for: {item['headline'][:80]}"
                )

    # -- Model-release items must never be flagged as deals --

    def test_model_release_items_not_deals(self, all_items):
        for item in all_items:
            section = item.get("brief_section", "")
            if "Model Releases" in section or "Technical Developments" in section:
                item_with_flag = {**item, "is_model_release": True}
                assert not is_probable_deal(item_with_flag), (
                    f"Model release item flagged as deal: {item['headline'][:80]}"
                )

    # -- Summary stats --

    def test_deal_ratio_is_reasonable(self, all_items):
        """Deals should be a small fraction of all items."""
        deal_count = sum(1 for i in all_items if is_probable_deal(i))
        ratio = deal_count / len(all_items)
        # Expect < 15% of all items to be deals
        assert ratio < 0.15, (
            f"Deal ratio too high: {deal_count}/{len(all_items)} = {ratio:.1%}"
        )
        # But at least some deals should exist
        assert deal_count >= 3, f"Too few deals detected: {deal_count}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. DEAL / MODEL-RELEASE MUTUAL EXCLUSION
# ═══════════════════════════════════════════════════════════════════════════

class TestMutualExclusion:

    def test_deal_keywords_with_model_release_true(self):
        item = {"headline": "Anthropic raises $2B Series C", "is_model_release": True}
        assert is_probable_deal(item) is False

    def test_deal_keywords_with_model_release_false(self):
        item = {"headline": "Anthropic raises $2B Series C", "is_model_release": False}
        assert is_probable_deal(item) is True

    def test_deal_keywords_no_model_release_key(self):
        item = {"headline": "Anthropic raises $2B Series C"}
        assert is_probable_deal(item) is True

    def test_model_release_section_with_acquisition(self):
        item = {
            "headline": "Google acquires DeepMind spin-off for $500M",
            "is_model_release": True,
            "brief_section": "Model Releases & Technical Developments",
        }
        assert is_probable_deal(item) is False

    def test_hybrid_deal_and_launch(self):
        item = {
            "headline": "Anthropic raises $2B and launches Claude 5",
            "is_model_release": True,
        }
        assert is_probable_deal(item) is False

    def test_deal_without_model_release_flag_in_model_section(self):
        """Without explicit is_model_release=True, section name alone doesn't block."""
        item = {
            "headline": "Startup raises $50M seed round for AI chips",
            "brief_section": "Model Releases & Technical Developments",
        }
        assert is_probable_deal(item) is True


# ═══════════════════════════════════════════════════════════════════════════
# 3. JUDGE MESSAGE FORMATTING
# ═══════════════════════════════════════════════════════════════════════════

class TestJudgeMessageFormatting:

    def test_deal_flag_true_in_message(self):
        msg = _build_judge_message(
            "OpenAI fundraise closes",
            "OpenAI completed its fundraise",
            [],
            is_model_release=False,
            is_deal=True,
        )
        assert "is_deal: True" in msg

    def test_deal_flag_false_in_message(self):
        msg = _build_judge_message(
            "Iran strikes UAE",
            "Missiles hit Abu Dhabi",
            [],
            is_model_release=False,
            is_deal=False,
        )
        assert "is_deal: False" in msg

    def test_both_flags_present(self):
        msg = _build_judge_message(
            "Test headline", "content", [], is_model_release=True, is_deal=False
        )
        assert "is_model_release: True" in msg
        assert "is_deal: False" in msg

    def test_extracts_included(self):
        extracts = [{"url": "https://example.com", "extract": "Detailed article text here"}]
        msg = _build_judge_message(
            "OpenAI fundraise", "thin content", extracts,
            is_model_release=False, is_deal=True,
        )
        assert "Supplementary Extract 1" in msg
        assert "https://example.com" in msg
        assert "Detailed article text here" in msg
        assert "is_deal: True" in msg

    def test_no_extracts_shows_none_yet(self):
        msg = _build_judge_message(
            "headline", "content", [],
            is_model_release=False, is_deal=True,
        )
        assert "(none yet)" in msg


# ═══════════════════════════════════════════════════════════════════════════
# 4. DEAL QUERY CONSTRUCTION EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════

class TestDealQueryEdgeCases:

    def test_entities_with_markdown_bold(self):
        queries = _build_deal_queries("headline", ["**OpenAI**", "**SoftBank**"])
        assert "OpenAI" in queries[0]["query"]
        assert "**" not in queries[0]["query"]

    def test_empty_entities_list(self):
        queries = _build_deal_queries("Anthropic raises $500M Series B", [])
        # Falls back to headline first word
        assert any("Anthropic" in q["query"] for q in queries)

    def test_none_entities(self):
        queries = _build_deal_queries("xAI funding round", None)
        assert len(queries) >= 1
        assert any("xAI" in q["query"] for q in queries)

    def test_very_long_headline(self):
        headline = "Company X " * 50 + "raises $1B Series F"
        queries = _build_deal_queries(headline, ["**Company X**"])
        assert len(queries) == 3
        # The overview query will be long but that's OK for search

    def test_entities_with_special_chars(self):
        queries = _build_deal_queries("headline", ["**Run:ai**", "**AI21 Labs**"])
        assert "Run:ai" in queries[0]["query"]

    def test_all_three_intents_present(self):
        queries = _build_deal_queries("Test deal", ["**TestCo**"])
        intents = {q["query_intent"] for q in queries}
        assert intents == {"deal_terms", "deal_parties", "deal_overview"}

    def test_empty_headline_and_entities(self):
        queries = _build_deal_queries("", [])
        # Should still produce at least the overview query
        assert len(queries) >= 1
        assert queries[-1]["query_intent"] == "deal_overview"


# ═══════════════════════════════════════════════════════════════════════════
# 5. NEWSLETTER-SOURCED DEAL ITEMS (OpenAI Apr-2 scenario)
# ═══════════════════════════════════════════════════════════════════════════

class TestNewsletterDealScenario:
    """Reconstruct the exact failure that prompted this fix."""

    @pytest.fixture
    def openai_item(self):
        return {
            "headline": "OpenAI closes record fundraise with $24 billion in annual revenue",
            "source_name": "AINews (Latent Space)",
            "source_url": None,
            "source_origin": "newsletter",
            "raw_content": (
                "OpenAI closed its latest funding round, the largest in company "
                "history, drawing $3 billion from individual investors alongside "
                "inclusion in ARK Invest ETFs. $24B ARR growing 4x faster than "
                "Google or Meta. ChatGPT WAU has not crossed the 1B mark."
            ),
            "entities": ["**OpenAI**", "**ARK Invest**", "**Google**", "**Meta**"],
        }

    def test_detected_as_deal(self, openai_item):
        assert is_probable_deal(openai_item) is True

    def test_is_thin(self, openai_item):
        """Newsletter splitter caps body at ~300 chars, so this should be thin."""
        word_count = len(openai_item["raw_content"].split())
        assert word_count < THIN_THRESHOLD, (
            f"Expected <{THIN_THRESHOLD} words, got {word_count}"
        )
        assert is_thin(openai_item)

    def test_queries_use_primary_entity(self, openai_item):
        queries = _build_deal_queries(
            openai_item["headline"], openai_item["entities"]
        )
        assert "OpenAI" in queries[0]["query"]
        assert queries[0]["query_intent"] == "deal_terms"

    def test_judge_message_has_deal_flag(self, openai_item):
        msg = _build_judge_message(
            openai_item["headline"],
            openai_item["raw_content"],
            [],
            is_model_release=False,
            is_deal=True,
        )
        assert "is_deal: True" in msg
        # The raw_content should appear in the message
        assert "$3 billion" in msg
        assert "$24B ARR" in msg

    def test_null_source_url(self, openai_item):
        """source_url is null — enricher step 1 (URL fetch) will fail,
        forcing the flow into web search where deal queries kick in."""
        assert openai_item["source_url"] is None

    def test_missing_key_deal_facts(self, openai_item):
        """The raw content mentions one tranche ($3B) and revenue ($24B ARR)
        but NOT the total round size or valuation — exactly the gap the
        enrichment judge should now catch."""
        content = openai_item["raw_content"]
        assert "$3 billion" in content  # partial tranche
        assert "$24B ARR" in content  # revenue, not round size
        # These should NOT be present (the key missing facts):
        assert "valuation" not in content.lower()
        assert "$40" not in content  # total round size not mentioned


# ═══════════════════════════════════════════════════════════════════════════
# 6. ENRICHER FLOW ASSERTIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestEnricherFlowAssertions:

    def test_thin_deal_triggers_enrichment(self):
        """A deal item with <80 words should be thin → enrichment triggers."""
        item = {
            "headline": "Startup raises $100M Series A",
            "raw_content": "The company raised money from investors.",
        }
        assert is_thin(item) is True
        assert is_probable_deal(item) is True

    def test_thick_deal_skips_enrichment(self):
        """A deal item with >=80 words is not thin. The judge prompt change
        is irrelevant here since enrichment won't trigger. This documents
        a known limitation: thick-but-incomplete deal items bypass enrichment."""
        item = {
            "headline": "Startup raises $100M Series A",
            "raw_content": " ".join(["word"] * 100),
        }
        assert is_thin(item) is False
        assert is_probable_deal(item) is True

    def test_supplementary_query_branch_deal(self):
        """When is_deal=True and is_model_release=False, the enricher
        should use _build_deal_queries (not build_model_release_queries)."""
        item = {
            "headline": "OpenAI closes funding round",
            "raw_content": "Short content",
            "entities": ["**OpenAI**"],
        }
        is_model_release = False
        is_deal = is_probable_deal(item)
        assert is_deal is True

        # Simulate the branch: model release queries vs deal queries
        if is_model_release:
            supplementary = "model_release_queries"
        elif is_deal:
            supplementary = _build_deal_queries(
                item["headline"], item.get("entities")
            )
        else:
            supplementary = None

        assert isinstance(supplementary, list)
        assert supplementary[0]["query_intent"] == "deal_terms"

    def test_supplementary_query_branch_model_release(self):
        """Model release takes priority over deal for query selection."""
        item = {
            "headline": "Anthropic raises $2B and launches Claude 5",
            "is_model_release": True,
        }
        is_model_release = True
        is_deal = is_probable_deal(item)
        assert is_deal is False

        if is_model_release:
            supplementary = "model_release_queries"
        elif is_deal:
            supplementary = _build_deal_queries(item["headline"])
        else:
            supplementary = None

        assert supplementary == "model_release_queries"

    def test_supplementary_query_branch_neither(self):
        """General news items get no supplementary queries."""
        item = {"headline": "Iran launches missile strikes on UAE"}
        is_model_release = False
        is_deal = is_probable_deal(item)
        assert is_deal is False

        if is_model_release:
            supplementary = "model_release_queries"
        elif is_deal:
            supplementary = _build_deal_queries(item["headline"])
        else:
            supplementary = None

        assert supplementary is None


# ═══════════════════════════════════════════════════════════════════════════
# 7. REGEX BOUNDARY & EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════

class TestRegexBoundaries:
    """Test tricky patterns — some are known false positives, documented."""

    # -- True negatives (must NOT match) --

    def test_raises_awareness(self):
        assert not DEAL_CUE_RE.search("raises awareness about AI safety")

    def test_series_of_events(self):
        assert not DEAL_CUE_RE.search("a series of events led to the crisis")

    def test_led_by_industry_leaders(self):
        assert not DEAL_CUE_RE.search("led by industry leaders in healthcare")

    def test_backed_by_popular_demand(self):
        assert not DEAL_CUE_RE.search("backed by popular demand")

    def test_led_by_researchers(self):
        assert not DEAL_CUE_RE.search("led by a team of researchers at MIT")

    def test_backed_by_evidence(self):
        assert not DEAL_CUE_RE.search("backed by scientific evidence and data")

    # -- True positives --

    def test_raised_dollar(self):
        assert DEAL_CUE_RE.search("raised $500M in new funding")

    def test_merger_talks(self):
        assert DEAL_CUE_RE.search("merger talks between the two companies")

    def test_post_money_valuation_hyphen(self):
        assert DEAL_CUE_RE.search("post-money valuation of $10B")

    def test_post_money_valuation_space(self):
        assert DEAL_CUE_RE.search("post money valuation of $10B")

    def test_series_z(self):
        assert DEAL_CUE_RE.search("Series Z funding announced")

    def test_ipo_standalone(self):
        assert DEAL_CUE_RE.search("the company filed for IPO")

    def test_going_public(self):
        assert DEAL_CUE_RE.search("announced plans for going public")

    def test_acquires(self):
        assert DEAL_CUE_RE.search("Google acquires startup for $1B")

    def test_acquisition(self):
        assert DEAL_CUE_RE.search("the acquisition was completed yesterday")

    def test_merge(self):
        assert DEAL_CUE_RE.search("the boards voted to merge the companies")

    def test_merging(self):
        assert DEAL_CUE_RE.search("merging operations across three divisions")

    def test_investment_round(self):
        assert DEAL_CUE_RE.search("closed a $200M investment round")

    def test_led_by_sequoia_capital(self):
        assert DEAL_CUE_RE.search("led by Sequoia Capital")

    def test_backed_by_andreessen_ventures(self):
        assert DEAL_CUE_RE.search("backed by Andreessen Horowitz ventures")

    # -- Known false positives (documented, accepted) --

    def test_acquired_taste_false_positive(self):
        """'acquired' matches even in non-deal contexts. Accepted because
        deal-context headlines rarely use 'acquired taste'."""
        assert DEAL_CUE_RE.search("an acquired taste for most people")

    def test_ipo_pipeline_false_positive(self):
        """'IPO' matches even when used as adjective. Accepted because
        'IPO pipeline' is still deal-adjacent."""
        assert DEAL_CUE_RE.search("the IPO pipeline is drying up")

    def test_going_public_with_findings_false_positive(self):
        """'going public' matches even for 'going public with findings'.
        Accepted — this phrasing is rare in news headlines."""
        assert DEAL_CUE_RE.search("the researchers are going public with their findings")

    def test_emergency_merger_legislation_false_positive(self):
        """'merger' matches in legislative contexts. Accepted — legislation
        about mergers is deal-adjacent and the judge will evaluate substance."""
        assert DEAL_CUE_RE.search("emergency merger legislation proposed")


# ═══════════════════════════════════════════════════════════════════════════
# 8. SUPABASE HISTORICAL ITEMS (hardcoded known items)
# ═══════════════════════════════════════════════════════════════════════════

class TestSupabaseKnownItems:
    """Items from Cloud Run pipeline runs (not in local output files).
    Hardcoded from earlier Supabase queries."""

    def test_openai_apr2_fundraise(self):
        item = {
            "headline": "OpenAI closes record fundraise with $24 billion in annual revenue",
            "source_name": "AINews (Latent Space)",
            "raw_content": (
                "OpenAI closed its latest funding round — described as the largest "
                "in company history — drawing $3 billion from individual investors "
                "alongside inclusion in ARK Invest ETFs, while disclosing $24 billion "
                "in annual recurring revenue."
            ),
        }
        assert is_probable_deal(item) is True

    def test_qwen_lead_exits_not_deal(self):
        """Personnel change, not a deal."""
        item = {
            "headline": "Qwen lead exits Alibaba amid restructuring and compute access tensions",
        }
        assert is_probable_deal(item) is False

    def test_mistral_pivot_not_deal(self):
        item = {
            "headline": "Mistral pivots to consulting-first model, embedding engineers with European customers",
        }
        assert is_probable_deal(item) is False

    def test_google_deploys_gemini_not_deal(self):
        item = {
            "headline": "Google deploys Gemini AI agents to 3 million Pentagon personnel",
        }
        assert is_probable_deal(item) is False

    def test_hugging_face_transformers_not_deal(self):
        item = {
            "headline": "Hugging Face ships Transformers v5.0.0 after five years",
        }
        assert is_probable_deal(item) is False

    def test_us_commerce_chip_rule_not_deal(self):
        item = {
            "headline": "US Commerce Department quietly withdraws planned AI chip export rule",
        }
        assert is_probable_deal(item) is False

    def test_tech_billionaire_pac_not_deal(self):
        item = {
            "headline": "Tech billionaire-backed super PAC spends $125 million against AI regulation candidates",
        }
        # "backed" appears but not "backed by ... capital/ventures/partners"
        assert is_probable_deal(item) is False
