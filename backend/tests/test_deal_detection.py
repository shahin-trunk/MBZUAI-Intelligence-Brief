"""Tests for deal/fundraise/M&A detection heuristic in enricher.

Note: enricher.py uses Python 3.10+ syntax (dict | None) so we cannot import
directly on 3.9. Instead we copy the detection functions here.
"""

import re


# ---------------------------------------------------------------------------
# Copied from enricher.py — deal detection logic
# ---------------------------------------------------------------------------

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
    import json
    if isinstance(raw_content, (dict, list)):
        return json.dumps(raw_content, ensure_ascii=False)
    return str(raw_content) if raw_content else ""


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


# ---------------------------------------------------------------------------
# is_probable_deal — True cases
# ---------------------------------------------------------------------------

class TestDealDetectionPositive:
    """Items that should be detected as deals."""

    def test_openai_fundraise(self):
        item = {"headline": "OpenAI closes record fundraise with $24 billion in annual revenue"}
        assert is_probable_deal(item) is True

    def test_series_b(self):
        item = {"headline": "Anthropic raises $500M Series B at $10B valuation"}
        assert is_probable_deal(item) is True

    def test_acquisition(self):
        item = {"headline": "NVIDIA acquires Run:ai for $700M"}
        assert is_probable_deal(item) is True

    def test_merger(self):
        item = {"headline": "Unilever to merge food business with McCormick"}
        assert is_probable_deal(item) is True

    def test_ipo(self):
        item = {"headline": "Cerebras files for IPO amid AI chip boom"}
        assert is_probable_deal(item) is True

    def test_valuation(self):
        item = {"headline": "Databricks valued at $62B in new funding round"}
        assert is_probable_deal(item) is True

    def test_raised_dollar_amount(self):
        item = {"headline": "xAI raised $6 billion to expand compute infrastructure"}
        assert is_probable_deal(item) is True

    def test_investment_round(self):
        item = {"headline": "Mistral closes $600M investment round led by Andreessen Horowitz"}
        assert is_probable_deal(item) is True

    def test_seed_round(self):
        item = {"headline": "AI startup closes seed round for autonomous agents"}
        assert is_probable_deal(item) is True

    def test_backed_by_capital(self):
        item = {"headline": "New AI lab backed by Sequoia Capital and a16z"}
        assert is_probable_deal(item) is True

    def test_deal_in_raw_content_not_headline(self):
        item = {
            "headline": "OpenAI latest news",
            "raw_content": "OpenAI has completed its fundraise, the largest in history",
        }
        assert is_probable_deal(item) is True

    def test_going_public(self):
        item = {"headline": "CoreWeave considering going public after $23B valuation"}
        assert is_probable_deal(item) is True


# ---------------------------------------------------------------------------
# is_probable_deal — False cases
# ---------------------------------------------------------------------------

class TestDealDetectionNegative:
    """Items that should NOT be detected as deals."""

    def test_model_release(self):
        item = {"headline": "Qwen3.5-Omni beats Gemini on benchmarks", "is_model_release": True}
        assert is_probable_deal(item) is False

    def test_model_release_flag_overrides(self):
        """Model release flag takes priority even if deal keywords present."""
        item = {
            "headline": "Anthropic raises Series B and launches Claude 4",
            "is_model_release": True,
        }
        assert is_probable_deal(item) is False

    def test_government_news(self):
        item = {"headline": "UAE Cabinet approves national space strategy"}
        assert is_probable_deal(item) is False

    def test_military_conflict(self):
        item = {"headline": "Iran launches missile strikes on UAE air defenses"}
        assert is_probable_deal(item) is False

    def test_research_paper(self):
        item = {"headline": "DeepMind publishes breakthrough on protein folding"}
        assert is_probable_deal(item) is False

    def test_product_launch(self):
        item = {"headline": "Google launches Gemini 2.5 Pro with native audio"}
        assert is_probable_deal(item) is False

    def test_policy_news(self):
        item = {"headline": "EU passes landmark AI Act amendments"}
        assert is_probable_deal(item) is False

    def test_general_tech(self):
        item = {"headline": "Apple reports record quarterly revenue of $130B"}
        assert is_probable_deal(item) is False

    def test_benchmark_comparison(self):
        item = {"headline": "Claude 4 surpasses GPT-5 on MMLU and HumanEval"}
        assert is_probable_deal(item) is False


# ---------------------------------------------------------------------------
# _build_deal_queries
# ---------------------------------------------------------------------------

class TestBuildDealQueries:
    """Verify deal-specific search queries are constructed correctly."""

    def test_with_entities(self):
        queries = _build_deal_queries("OpenAI closes record fundraise", ["**OpenAI**", "ARK Invest"])
        assert len(queries) >= 2
        assert "OpenAI" in queries[0]["query"]
        assert queries[0]["query_intent"] == "deal_terms"

    def test_without_entities(self):
        queries = _build_deal_queries("Anthropic raises $500M Series B")
        assert len(queries) >= 1
        assert any("deal_overview" == q["query_intent"] for q in queries)

    def test_query_intents(self):
        queries = _build_deal_queries("xAI funding round", ["**xAI**"])
        intents = {q["query_intent"] for q in queries}
        assert "deal_terms" in intents
        assert "deal_parties" in intents
        assert "deal_overview" in intents


# ---------------------------------------------------------------------------
# DEAL_CUE_RE edge cases
# ---------------------------------------------------------------------------

class TestDealCueRegex:
    """Verify regex matches and non-matches at the pattern level."""

    def test_series_a_through_f(self):
        for letter in "abcdef":
            assert DEAL_CUE_RE.search(f"Series {letter.upper()} round")

    def test_raised_with_dollar(self):
        assert DEAL_CUE_RE.search("raised $500M")
        assert DEAL_CUE_RE.search("raises $2 billion")

    def test_pre_money_valuation(self):
        assert DEAL_CUE_RE.search("pre-money valuation of $10B")
        assert DEAL_CUE_RE.search("post money valuation")

    def test_led_by_ventures(self):
        assert DEAL_CUE_RE.search("led by Sequoia Capital")
        assert DEAL_CUE_RE.search("backed by Andreessen Horowitz ventures")

    def test_no_match_plain_raise(self):
        """'raise' without dollar sign should not match."""
        assert not DEAL_CUE_RE.search("raise awareness about AI safety")

    def test_no_match_build(self):
        """Building/construction language should not match."""
        assert not DEAL_CUE_RE.search("building a new data center in Abu Dhabi")


# ---------------------------------------------------------------------------
# Historical brief items — regression tests
# ---------------------------------------------------------------------------

class TestHistoricalItems:
    """Items from actual briefs to verify correct classification."""

    def test_openai_100b_fundraise(self):
        """From 2026-02-23 brief."""
        item = {
            "headline": "OpenAI finalises $100B+ funding round at up to $850B valuation",
            "raw_content": "OpenAI is close to finalising the first phase of a funding round exceeding $100 billion",
        }
        assert is_probable_deal(item) is True

    def test_nvidia_marvell_investment(self):
        """From newsletter 2026-03-31."""
        item = {
            "headline": "Nvidia bets $2 billion on Marvell as rising AI adoption fuels competition",
            "raw_content": "Nvidia has invested $2 billion in Marvell Technology",
        }
        # "invested" is not in the regex, but this is about an investment
        # The raw_content doesn't match our regex — that's OK, this is more
        # of a strategic investment than a fundraise/deal
        # If we want to catch this, we'd need to add "invested" — but it's
        # too broad (would match "invested time in research")
        pass  # Intentionally not asserting — documenting the edge case

    def test_unilever_mccormick_merger(self):
        """From newsletter 2026-04-01."""
        item = {
            "headline": "Unilever, McCormick strike deal to create $65 billion food giant",
        }
        # "merger" is not in headline but "deal" is not in regex (too broad)
        # However the raw_content from the newsletter would contain "merge"
        item["raw_content"] = "Unilever will merge its food business with spice maker McCormick"
        assert is_probable_deal(item) is True

    def test_runway_fund_launch(self):
        """Fund launch, not a fundraise for the company itself."""
        item = {
            "headline": "Exclusive: Runway launches $10M fund, Builders program to support early stage AI startups",
        }
        # This is a fund launch, not a fundraise — should NOT match
        assert is_probable_deal(item) is False
