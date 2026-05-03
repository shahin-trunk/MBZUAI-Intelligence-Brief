from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse


VARIANT_TERMS = (
    "mini",
    "nano",
    "pro",
    "flash",
    "haiku",
    "sonnet",
    "opus",
    "instant",
)

MODEL_ROOT_TOKENS = {
    "gpt",
    "claude",
    "gemini",
    "llama",
    "olmo",
    "mistral",
    "mixtral",
    "qwen",
    "phi",
    "grok",
    "deepseek",
    "command",
    "nova",
    "kimi",
    "ernie",
    "falcon",
    "yi",
    "granite",
    "nemotron",
    "starcoder",
    "dbrx",
    "jamba",
}

OFFICIAL_SOURCE_DOMAINS = {
    "openai.com",
    "anthropic.com",
    "docs.anthropic.com",
    "googleblog.com",
    "ai.google.dev",
    "deepmind.google",
    "mistral.ai",
    "meta.com",
    "ai.meta.com",
    "nvidia.com",
    "build.nvidia.com",
    "techcommunity.microsoft.com",
    "azure.microsoft.com",
    "huggingface.co",
}

BENCHMARK_ALIASES = {
    "swe-bench pro": "SWE-bench Pro",
    "swe bench pro": "SWE-bench Pro",
    "swe-bench verified": "SWE-bench Verified",
    "swe bench verified": "SWE-bench Verified",
    "osworld-verified": "OSWorld-Verified",
    "osworld verified": "OSWorld-Verified",
    "osworld": "OSWorld",
    "gpqa diamond": "GPQA Diamond",
    "gpqa": "GPQA",
    "mmlu": "MMLU",
    "humaneval": "HumanEval",
    "toolathlon": "Toolathlon",
    "arc-agi-2": "ARC-AGI-2",
    "arc agi 2": "ARC-AGI-2",
    "browsecomp": "BrowseComp",
    "terminal-bench 2.0": "Terminal-Bench 2.0",
    "terminal bench 2.0": "Terminal-Bench 2.0",
    "terminal-bench": "Terminal-Bench",
    "terminal bench": "Terminal-Bench",
    "livecodebench pro": "LiveCodeBench Pro",
    "livecodebench": "LiveCodeBench",
    "mcp atlas": "MCP Atlas",
    "apex-agents": "APEX-Agents",
    "apex agents": "APEX-Agents",
    "aa intelligence": "AA Intelligence",
    "gdpval": "GDPval",
    "mmmu": "MMMU",
    "aime": "AIME",
    "scicode": "SciCode",
    "pinchbench": "PinchBench",
    "humanity's last exam": "Humanity's Last Exam",
}

BENCHMARK_PRIORITY = [
    "SWE-bench Pro",
    "SWE-bench Verified",
    "OSWorld-Verified",
    "OSWorld",
    "HumanEval",
    "LiveCodeBench Pro",
    "MMLU",
    "GPQA Diamond",
    "GPQA",
    "ARC-AGI-2",
    "BrowseComp",
    "Toolathlon",
    "Terminal-Bench 2.0",
    "Terminal-Bench",
    "GDPval",
    "AA Intelligence",
    "Humanity's Last Exam",
]

BENCHMARK_KEYWORDS = tuple(BENCHMARK_ALIASES.keys())

KEY_NUMBER_KIND_ALIASES = {
    "pricing": "pricing",
    "context": "context",
    "speed": "speed",
    "latency": "speed",
    "throughput": "speed",
}

NOISY_MODEL_LABELS = {
    "it",
    "this",
    "that",
    "results",
    "result",
    "results show",
    "score",
    "scores",
    "higher",
    "lower",
    "versus",
    "versu",
    "vs",
    "approaching",
    "improves",
    "improved",
    "improve",
}

RELEASE_CUE_RE = re.compile(
    r"\b("
    r"release(?:d|s)?|launch(?:ed|es)?|unveil(?:ed|s)?|introduc(?:ed|es)?|"
    r"announce(?:d|s)?|debut(?:ed|s)?|ship(?:ped|s)?|roll(?:ed)? out|"
    r"made available|available via|available in|available on|"
    r"developer preview|general availability|model card"
    r")\b",
    re.IGNORECASE,
)

MODEL_ARTIFACT_CUE_RE = re.compile(
    r"\b("
    r"api|pricing|price|context window|input tokens|output tokens|"
    r"weights?|checkpoint|multimodal|reasoning model|open[- ]source model|"
    r"benchmark results?|availability|developer preview|general availability"
    r")\b",
    re.IGNORECASE,
)

RESEARCH_PUBLICATION_CUE_RE = re.compile(
    r"\b("
    r"paper|research paper|study|preprint|published|publication|journal|nature|"
    r"arxiv|evaluation|evaluating|benchmark released|leaderboard|peer review|"
    r"scientific work|scientific discovery|automated research system"
    r")\b",
    re.IGNORECASE,
)

PRODUCT_DEPLOYMENT_CUE_RE = re.compile(
    r"\b("
    r"api|sdk|docs?|documentation|playground|endpoint|console|platform|"
    r"model card|developer preview|general availability|chat interface|"
    r"available in the api|available via api|available on vertex|available on bedrock"
    r")\b",
    re.IGNORECASE,
)

OPEN_WEIGHT_RELEASE_CUE_RE = re.compile(
    r"\b("
    r"hugging ?face|github|open[- ]sourc(?:e|ed|ing)|open weights?|"
    r"weights? (?:released|available|published)|download(?:able)?|checkpoint"
    r")\b",
    re.IGNORECASE,
)

FUNDING_OR_BUILD_CUE_RE = re.compile(
    r"\b("
    r"raise(?:s|d)?|raising|funding|valuation|series [a-z]|seed round|"
    r"backed by (?:funding|investors?|capital|venture|seed)|"
    r"plans to build|aims to build|"
    r"develop(?:s|ed|ing)? (?:a |an |the |its |new |advanced |ai-ready |ai[- ]ready )*(?:data ?cent(?:er|re)|facility|campus|infrastructure)|"
    r"development of (?:a |an |the |its |new |advanced |ai-ready |ai[- ]ready )*(?:data ?cent(?:er|re)|facility|campus|infrastructure)|"
    r"building (?:a |an |the |its |new |next[ -]gen(?:eration)? )*(?:data ?center|chip|factory|fab|facility|campus|infrastructure)|"
    r"acquisition|acquire(?:d|s)?|merger|ipo"
    r")\b",
    re.IGNORECASE,
)

INFRASTRUCTURE_BUILD_CUE_RE = re.compile(
    r"\b("
    r"joint venture|partnership|signing ceremony|strategic milestone|"
    r"data ?cent(?:er|re)s?|ai[- ]ready data ?cent(?:er|re)s?|ai factory|"
    r"megawatts?|\bMW\b|square metres?|square meters?|committed power|"
    r"electrical systems|power distribution|digital infrastructure"
    r")\b",
    re.IGNORECASE,
)

MARKET_OR_RANKING_CUE_RE = re.compile(
    r"\b("
    r"token consumption|weekly rankings?|weekly usage|usage volume|market share|"
    r"dominat(?:e|es|ed) (?:the )?(?:market|usage|downloads?|traffic|adoption)|"
    r"surpass(?:es|ed)? (?:in )?(?:market share|usage|downloads?|adoption)|"
    r"overtake(?:s|n|d)? (?:in )?(?:market share|usage|downloads?|adoption)|"
    r"same period|week of|price advantage"
    r")\b",
    re.IGNORECASE,
)

SCIENTIFIC_DOMAIN_CUE_RE = re.compile(
    r"\b("
    r"fmri|brain activity|brain responses?|neuroscience|algonauts|"
    r"protein|proteins|genomic|genomics|molecular|structural biology|"
    r"drug discovery|materials science|subjects|voxels?"
    r")\b",
    re.IGNORECASE,
)


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def get_model_release_heuristic_signals(item: dict) -> dict[str, Any]:
    """Extract reusable classification signals for model-card eligibility."""
    headline = _normalise_text(item.get("headline", ""))
    summary = _normalise_text(item.get("summary", ""))
    raw_content = _normalise_text(item.get("raw_content", ""))
    category = _normalise_text(item.get("category", ""))
    story_type = _normalise_text(item.get("story_type", ""))
    section = _normalise_text(item.get("brief_section", ""))
    entities = " ".join(str(entity) for entity in (item.get("entities") or []))
    source_name = _normalise_text(item.get("source", "") or item.get("source_name", ""))

    text = " ".join(
        part
        for part in (
            headline,
            summary,
            raw_content,
            category,
            story_type,
            section,
            entities,
            source_name,
        )
        if part
    )
    text_lower = text.lower()

    variants = detect_model_release_variants(
        headline,
        entities=item.get("entities", []),
        raw_content=raw_content,
    )
    has_variant = bool(variants)
    has_model_root = any(
        re.search(rf"\b{re.escape(token)}(?:[-\s]?\d)?\b", text_lower)
        for token in MODEL_ROOT_TOKENS
    )
    has_release_cue = bool(RELEASE_CUE_RE.search(text))
    has_model_artifact_cue = bool(MODEL_ARTIFACT_CUE_RE.search(text))
    has_product_deployment_cue = bool(PRODUCT_DEPLOYMENT_CUE_RE.search(text))
    has_open_weight_release_cue = bool(OPEN_WEIGHT_RELEASE_CUE_RE.search(text))
    has_research_publication_cue = bool(RESEARCH_PUBLICATION_CUE_RE.search(text))
    has_funding_or_build_cue = bool(FUNDING_OR_BUILD_CUE_RE.search(text))
    has_infrastructure_build_cue = bool(INFRASTRUCTURE_BUILD_CUE_RE.search(text))
    has_market_or_ranking_cue = bool(MARKET_OR_RANKING_CUE_RE.search(text))
    has_scientific_domain_cue = bool(SCIENTIFIC_DOMAIN_CUE_RE.search(text))

    urls = [str(item.get("source_url") or "").strip()]
    for source in item.get("enriched_sources", []) or []:
        if isinstance(source, dict):
            urls.append(str(source.get("url") or "").strip())
            urls.append(str(source.get("title") or "").strip())
    has_official_source = any(
        _extract_domain(candidate) in OFFICIAL_SOURCE_DOMAINS or "model card" in candidate.lower()
        for candidate in urls
        if candidate
    )

    return {
        "headline": headline,
        "summary": summary,
        "raw_content": raw_content,
        "section": section,
        "text": text,
        "variants": variants,
        "has_variant": has_variant,
        "has_model_root": has_model_root,
        "has_release_cue": has_release_cue,
        "has_model_artifact_cue": has_model_artifact_cue,
        "has_product_deployment_cue": has_product_deployment_cue,
        "has_open_weight_release_cue": has_open_weight_release_cue,
        "has_research_publication_cue": has_research_publication_cue,
        "has_funding_or_build_cue": has_funding_or_build_cue,
        "has_infrastructure_build_cue": has_infrastructure_build_cue,
        "has_market_or_ranking_cue": has_market_or_ranking_cue,
        "has_scientific_domain_cue": has_scientific_domain_cue,
        "has_official_source": has_official_source,
        "urls": urls,
    }


def classify_model_release_heuristics(item: dict) -> tuple[bool | None, dict[str, Any]]:
    """Return deterministic decision for model-card eligibility.

    Returns:
      - True for obvious model-card launches
      - False for obvious non-card items
      - None for ambiguous middle cases that should be LLM-reviewed
    """
    signals = get_model_release_heuristic_signals(item)
    has_launch_signal = signals["has_release_cue"] and (
        signals["has_variant"]
        or signals["has_model_root"]
        or signals["has_official_source"]
        or signals["has_model_artifact_cue"]
    )

    if (
        signals["has_infrastructure_build_cue"]
        and not signals["has_variant"]
        and not signals["has_model_root"]
        and not signals["has_official_source"]
    ):
        return False, signals

    if signals["has_funding_or_build_cue"] or signals["has_market_or_ranking_cue"]:
        if has_launch_signal:
            return None, signals  # ambiguous — let Haiku decide
        return False, signals

    if (
        has_launch_signal
        and signals["has_open_weight_release_cue"]
        and not signals["has_product_deployment_cue"]
    ):
        return None, signals

    # Narrow scientific/research-domain releases can still be important items,
    # but the model-card treatment should be reserved for deployable AI model
    # launches rather than papers plus weights.
    if (
        signals["has_research_publication_cue"] or signals["has_scientific_domain_cue"]
    ) and not signals["has_product_deployment_cue"]:
        return False, signals

    if has_launch_signal and signals["has_product_deployment_cue"]:
        return True, signals

    if (
        signals["has_official_source"]
        and signals["has_product_deployment_cue"]
        and (signals["has_variant"] or signals["has_model_root"])
    ):
        return True, signals

    if has_launch_signal or (
        signals["has_official_source"]
        and (signals["has_variant"] or signals["has_model_root"] or signals["has_model_artifact_cue"])
    ):
        return None, signals

    return False, signals


def is_probable_model_release(item: dict) -> bool:
    """Return True when the item is deterministically card-worthy."""
    decision, _signals = classify_model_release_heuristics(item)
    return decision is True


def is_possible_model_release(item: dict) -> bool:
    """Return True when the item is either clearly or possibly card-worthy."""
    decision, _signals = classify_model_release_heuristics(item)
    return decision is not False


def _normalise_text(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")


def _dedupe_dicts(records: list[dict], keys: tuple[str, ...]) -> list[dict]:
    seen: set[tuple[str, ...]] = set()
    deduped: list[dict] = []
    for record in records:
        key = tuple(str(record.get(k, "")).strip().lower() for k in keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def canonicalise_benchmark_name(value: str) -> str:
    lower = re.sub(r"\s+", " ", value.strip().lower())
    return BENCHMARK_ALIASES.get(lower, value.strip())


def benchmark_priority_key(name: str) -> tuple[int, str]:
    canonical = canonicalise_benchmark_name(name)
    try:
        return (BENCHMARK_PRIORITY.index(canonical), canonical)
    except ValueError:
        return (len(BENCHMARK_PRIORITY), canonical)


def _prettify_model_label(label: str) -> str:
    label = re.sub(r"\s+", " ", label.strip())
    if not label:
        return ""
    pretty = label.title()
    pretty = re.sub(r"\bGpt\b", "GPT", pretty)
    pretty = re.sub(r"\bAi\b", "AI", pretty)
    return pretty


def _clean_variant_candidate(candidate: str) -> str:
    tokens = candidate.split()
    start_idx = 0
    for idx, token in enumerate(tokens):
        normalized = token.lower().strip(" .,:;()[]{}-")
        if normalized in MODEL_ROOT_TOKENS or re.search(r"\d", normalized):
            start_idx = idx
            break
    cleaned = " ".join(tokens[start_idx:]).strip()
    return cleaned or candidate.strip()


def detect_model_release_variants(
    headline: str,
    entities: list[str] | None = None,
    raw_content: str | None = None,
) -> list[str]:
    """Detect named model variants like GPT-5.4 mini / nano from available text."""
    candidates: list[str] = []
    texts = [headline, raw_content or ""]
    texts.extend(entities or [])

    pattern = re.compile(
        r"\b([A-Za-z0-9][A-Za-z0-9.\-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.\-]*){0,3}\s+"
        r"(?:mini|nano|pro|flash|haiku|sonnet|opus|instant)(?:\s+\d+(?:\.\d+)*)?)\b",
        re.IGNORECASE,
    )
    for text in texts:
        if not text:
            continue
        for match in pattern.finditer(text):
            value = _clean_variant_candidate(" ".join(match.group(1).split()))
            normalized_value = value.lower()
            if normalized_value.startswith("and "):
                continue
            if normalized_value in VARIANT_TERMS:
                continue
            candidates.append(value.replace("**", "").strip())

    cleaned: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(candidate)
    return cleaned


def infer_model_family_root(variants: list[str]) -> str | None:
    if not variants:
        return None
    tokens_by_variant = [variant.split()[:-1] for variant in variants if len(variant.split()) >= 2]
    if not tokens_by_variant:
        return None
    common = tokens_by_variant[0]
    for tokens in tokens_by_variant[1:]:
        upto = min(len(common), len(tokens))
        next_common: list[str] = []
        for idx in range(upto):
            if common[idx].lower() != tokens[idx].lower():
                break
            next_common.append(common[idx])
        common = next_common
        if not common:
            break
    return " ".join(common).strip() or None


def build_model_release_queries(
    headline: str,
    entities: list[str] | None = None,
) -> list[dict[str, str]]:
    """Build intent-tagged supplementary search queries for model releases."""
    variants = detect_model_release_variants(headline, entities=entities)
    short = headline[:88].rsplit(" ", 1)[0] if len(headline) > 88 else headline

    queries = [
        {"intent": "official", "query": f"{short} official announcement model card"},
        {"intent": "benchmark", "query": f"{short} benchmark results evaluation"},
        {"intent": "pricing", "query": f"{short} pricing availability API"},
    ]

    if len(variants) >= 2:
        joined = " vs ".join(variants[:2])
        queries.append(
            {"intent": "variant", "query": f"{joined} benchmark comparison"}
        )
    elif variants:
        queries.append(
            {
                "intent": "variant",
                "query": f"{variants[0]} predecessor benchmark comparison",
            }
        )
    else:
        queries.append(
            {"intent": "variant", "query": f"{short} variant benchmark comparison"}
        )

    return queries


def classify_model_release_result(url: str, title: str = "", snippet: str = "") -> set[str]:
    domain = _extract_domain(url)
    combined = " ".join(part for part in (url, title, snippet) if part).lower()
    intents: set[str] = set()

    if domain in OFFICIAL_SOURCE_DOMAINS or "model card" in combined or "release notes" in combined:
        intents.add("official")
    if any(keyword in combined for keyword in ("benchmark", "eval", "swe-bench", "osworld", "mmlu", "gpqa", "humaneval", "gdpval")):
        intents.add("benchmark")
    if any(keyword in combined for keyword in ("pricing", "price", "availability", "api", "chatgpt", "codex")):
        intents.add("pricing")
    if any(term in combined for term in VARIANT_TERMS):
        intents.add("variant")
    return intents


def reserve_model_release_search_results(
    candidates: list[dict[str, Any]],
    max_total: int = 7,
) -> list[dict[str, Any]]:
    """Reserve result slots by source intent before filling corroborating slots."""
    chosen: list[dict[str, Any]] = []
    seen_domains: set[str] = set()

    def _claim(candidate: dict[str, Any]) -> bool:
        domain = _extract_domain(candidate.get("link", ""))
        if not domain or domain in seen_domains:
            return False
        seen_domains.add(domain)
        chosen.append(candidate)
        return True

    for required_intent in ("official", "benchmark", "pricing"):
        for candidate in candidates:
            intents = set(candidate.get("classified_intents") or [])
            if required_intent in intents and _claim(candidate):
                break

    for candidate in candidates:
        if len(chosen) >= max_total:
            break
        _claim(candidate)

    return chosen[:max_total]


def collect_model_release_text_blobs(item: dict) -> list[dict[str, str]]:
    blobs: list[dict[str, str]] = []
    source_url = str(item.get("source_url") or "").strip()
    raw_content = _normalise_text(item.get("raw_content", ""))
    if raw_content:
        blobs.append(
            {
                "source_url": source_url,
                "title": item.get("headline", ""),
                "text": raw_content,
            }
        )

    for source in item.get("enriched_sources", []) or []:
        blobs.append(
            {
                "source_url": str(source.get("url") or "").strip(),
                "title": str(source.get("title") or "").strip(),
                "text": _normalise_text(source.get("extract", "")),
            }
        )

    enriched_facts = item.get("enriched_facts") or {}
    summary = _normalise_text(enriched_facts.get("summary", ""))
    if summary:
        blobs.append(
            {
                "source_url": "",
                "title": "enriched_facts.summary",
                "text": summary,
            }
        )
    for fact in enriched_facts.get("key_facts", []) or []:
        blobs.append(
            {
                "source_url": str(fact.get("source") or "").strip(),
                "title": "enriched_facts.key_fact",
                "text": _normalise_text(fact.get("fact", "")),
            }
        )
    return blobs


def extract_benchmark_mentions(text: str) -> list[str]:
    lower = text.lower()
    mentions = []
    for key, canonical in BENCHMARK_ALIASES.items():
        if key in lower:
            mentions.append(canonical)
    return sorted(set(mentions), key=benchmark_priority_key)


def _resolve_variant_alias(alias: str, variants: list[str], family_root: str | None) -> str:
    alias = re.sub(r"\s+", " ", alias.strip(" .,:;()[]{}-")).lower()
    alias = re.sub(r"\s+scores?$", "", alias)
    alias = re.sub(
        r"^(?:results?\s+show|higher\s+than|lower\s+than|approaching|nearly\s+matching|"
        r"almost\s+matching|matching|versus|vs\.?|for)\s+",
        "",
        alias,
    )
    if not alias or alias in NOISY_MODEL_LABELS:
        return ""
    if alias in {"flagship", "full", "full gpt-5.4", "gpt-5.4", "flagship model"} and family_root:
        return f"{family_root} (flagship)"
    if alias in {"predecessor", "previous model"} and family_root:
        return f"{family_root} predecessor"
    for variant in variants:
        variant_lower = variant.lower()
        variant_term = next(
            (
                term
                for term in VARIANT_TERMS
                if re.search(rf"\b{re.escape(term)}\b", variant_lower)
            ),
            variant_lower.split()[-1],
        )
        variant_without_version = re.sub(r"\b\d+(?:\.\d+)*\b", "", variant_lower)
        variant_without_version = re.sub(r"\s+", " ", variant_without_version).strip()
        if (
            alias == variant_lower
            or alias == variant_term
            or alias == variant_without_version
            or (
                family_root
                and alias.startswith(family_root.lower())
                and (
                    alias.endswith(f" {variant_term}")
                    or alias == variant_without_version
                )
            )
            or variant_lower in alias
        ):
            return variant
    if family_root and re.search(rf"\b(full\s+)?{re.escape(family_root.lower())}\b", alias):
        if "full" in alias or "flagship" in alias:
            return f"{family_root} (flagship)"
        return family_root
    if not any(term in alias for term in VARIANT_TERMS) and "gpt" not in alias and "flagship" not in alias:
        return ""
    return _prettify_model_label(alias)


def _model_suffix_for_label(label: str) -> str:
    lower = label.lower()
    for term in VARIANT_TERMS:
        match = re.search(rf"\b{re.escape(term)}(?:\s+(\d+(?:\.\d+)*))?\b", lower)
        if match:
            version = match.group(1)
            return f" ({term}{f' {version}' if version else ''})"
    return ""


def _default_model_from_blob(blob: dict[str, str], variants: list[str], family_root: str | None) -> str:
    combined = " ".join(
        part for part in (blob.get("title", ""), blob.get("text", "")[:300]) if part
    ).lower()
    for variant in variants:
        if variant.lower() in combined:
            return variant
    if family_root and ("flagship" in combined or f"full {family_root.lower()}" in combined):
        return f"{family_root} (flagship)"
    return ""


def _score_present(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and text not in {"—", "-", "n/a", "N/A", "NA"}


def _normalise_benchmark_label(value: str) -> str:
    label = str(value or "").strip()
    label = label.replace("\u00b2", "").replace("\u00b9", "")
    label = re.sub(r"\s+—\s+lower is better.*$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s*\([^)]*\)\s*$", "", label).strip()
    return canonicalise_benchmark_name(label)


def _looks_like_benchmark_label(value: str) -> bool:
    label = str(value or "").strip()
    if not label:
        return False
    canonical = _normalise_benchmark_label(label)
    if not canonical:
        return False
    if extract_benchmark_mentions(label):
        return True
    if re.search(r"(bench|athlon|arena|world|diamond|atlas|exam|eval|agi|mmmu|mmlu|gpqa|aime)", canonical, re.IGNORECASE):
        return True
    return False


def _normalise_table_model_header(
    value: str,
    variants: list[str],
    family_root: str | None,
) -> str:
    label = str(value or "").strip()
    label = label.replace("\u00b2", "").replace("\u00b9", "")
    label = re.sub(
        r"\((?:xhigh|high|medium|low|none|[^)]*reasoning[^)]*)\)",
        "",
        label,
        flags=re.IGNORECASE,
    )
    label = re.sub(r"\s+", " ", label).strip()
    return _resolve_variant_alias(label, variants, family_root)


def _split_markdown_row(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    while cells and not cells[-1]:
        cells.pop()
    return cells


def _is_markdown_separator(line: str) -> bool:
    cells = _split_markdown_row(line)
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def _looks_like_table_score_cell(cell: str) -> bool:
    value = str(cell or "").strip()
    if not value:
        return False
    if value in {"—", "-", "n/a", "N/A", "NA"}:
        return True
    if re.search(r"\d", value):
        return True
    return bool(re.search(r"(pass@|accuracy|score|pts|tokens|x\b)", value, flags=re.IGNORECASE))


def _iter_inline_markdown_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if "|---" not in compact:
        return []

    raw_tokens = [token.strip() for token in compact.split("|")]
    tables: list[tuple[list[str], list[list[str]]]] = []
    idx = 0
    while idx < len(raw_tokens):
        if not re.fullmatch(r":?-{3,}:?", raw_tokens[idx] or ""):
            idx += 1
            continue

        separator_cells: list[str] = []
        while idx < len(raw_tokens) and re.fullmatch(r":?-{3,}:?", raw_tokens[idx] or ""):
            separator_cells.append(raw_tokens[idx])
            idx += 1

        column_count = len(separator_cells)
        if column_count < 3:
            continue

        header_candidates: list[str] = []
        back_idx = idx - column_count - 1
        while back_idx >= 0 and len(header_candidates) < column_count - 1:
            candidate = raw_tokens[back_idx].strip()
            if candidate:
                header_candidates.append(candidate)
            back_idx -= 1
        if len(header_candidates) != column_count - 1:
            continue

        header_cells = [""] + list(reversed(header_candidates))
        rows: list[list[str]] = []
        current_row: list[str] = []

        while idx < len(raw_tokens):
            token = raw_tokens[idx].strip()
            idx += 1

            if not token:
                continue
            if re.fullmatch(r":?-{3,}:?", token or ""):
                idx -= 1
                break

            current_row.append(token)
            if len(current_row) < column_count:
                continue

            benchmark_label = _normalise_benchmark_label(current_row[0])
            score_cells = current_row[1:]
            if (
                not benchmark_label
                or not _looks_like_benchmark_label(current_row[0])
                or not all(_looks_like_table_score_cell(cell) for cell in score_cells)
            ):
                current_row = []
                break

            rows.append(current_row)
            current_row = []

        if rows:
            tables.append((header_cells, rows))

    return tables


def _iter_markdown_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = [line.rstrip() for line in str(text or "").splitlines()]
    tables: list[tuple[list[str], list[list[str]]]] = []
    idx = 0
    while idx + 1 < len(lines):
        header_line = lines[idx].strip()
        separator_line = lines[idx + 1].strip()
        if not header_line.startswith("|") or not _is_markdown_separator(separator_line):
            idx += 1
            continue

        header_cells = _split_markdown_row(header_line)
        idx += 2
        rows: list[list[str]] = []
        while idx < len(lines):
            row_line = lines[idx].strip()
            if not row_line.startswith("|") or _is_markdown_separator(row_line):
                break
            row_cells = _split_markdown_row(row_line)
            if row_cells:
                rows.append(row_cells)
            idx += 1

        if header_cells and rows:
            tables.append((header_cells, rows))

    seen: set[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = set()
    combined: list[tuple[list[str], list[list[str]]]] = []
    for header_cells, rows in tables + _iter_inline_markdown_tables(text):
        key = (tuple(header_cells), tuple(tuple(row) for row in rows))
        if key in seen:
            continue
        seen.add(key)
        combined.append((header_cells, rows))
    return combined


def extract_benchmark_table_facts(item: dict) -> list[dict[str, str]]:
    variants = detect_model_release_variants(
        item.get("headline", ""),
        entities=item.get("entities", []),
        raw_content=_normalise_text(item.get("raw_content", "")),
    )
    family_root = infer_model_family_root(variants)
    facts: list[dict[str, str]] = []

    for blob in collect_model_release_text_blobs(item):
        text = blob.get("text", "")
        if "|" not in text:
            continue
        url = blob.get("source_url", "")
        for header_cells, rows in _iter_markdown_tables(text):
            model_headers = [
                _normalise_table_model_header(cell, variants, family_root)
                for cell in header_cells
            ]
            model_headers = [header for header in model_headers if header]
            if not model_headers:
                continue

            for row in rows:
                if len(row) != len(model_headers) + 1:
                    if len(row) >= 2 and len(row) == len(header_cells):
                        # Covers tables where a blank top-left header cell was preserved.
                        trimmed_headers = [
                            _normalise_table_model_header(cell, variants, family_root)
                            for cell in header_cells[1:]
                        ]
                        trimmed_headers = [header for header in trimmed_headers if header]
                        if trimmed_headers and len(row[1:]) == len(trimmed_headers):
                            model_headers_for_row = trimmed_headers
                            benchmark_label = _normalise_benchmark_label(row[0])
                            scores = row[1:]
                        else:
                            continue
                    else:
                        continue
                else:
                    model_headers_for_row = model_headers
                    benchmark_label = _normalise_benchmark_label(row[0])
                    scores = row[1:]

                if not benchmark_label or not _looks_like_benchmark_label(row[0]):
                    continue

                for model, score in zip(model_headers_for_row, scores):
                    cleaned_score = str(score or "").strip()
                    if not model or not _score_present(cleaned_score):
                        continue
                    facts.append(
                        {
                            "benchmark": benchmark_label,
                            "model": model,
                            "score": cleaned_score,
                            "source_url": url,
                        }
                    )

    facts = _dedupe_dicts(facts, ("benchmark", "model", "score", "source_url"))
    facts.sort(key=lambda fact: (benchmark_priority_key(fact["benchmark"]), fact["model"].lower()))
    return facts


def _model_for_match(
    sentence: str,
    match_start: int,
    variants: list[str],
    family_root: str | None,
    blob_default_model: str,
) -> str:
    before_lower = sentence[:match_start].lower()
    best_variant = ""
    best_idx = -1
    for variant in variants:
        variant_lower = variant.lower()
        idx = before_lower.rfind(variant_lower)
        if idx > best_idx:
            best_variant = variant
            best_idx = idx
        short_variant = variant_lower.split()[-1]
        short_idx = before_lower.rfind(f" {short_variant}")
        if short_idx > best_idx:
            best_variant = variant
            best_idx = short_idx
    if best_variant:
        return best_variant

    window_start = max(0, match_start - 160)
    before = sentence[window_start:match_start]
    mentions = _extract_model_mentions(before, variants, family_root)
    if mentions:
        return mentions[-1]
    return blob_default_model


def _extract_model_mentions(sentence: str, variants: list[str], family_root: str | None) -> list[str]:
    mentions: list[tuple[int, str]] = []
    lower = sentence.lower()
    for variant in variants:
        idx = lower.find(variant.lower())
        if idx >= 0:
            mentions.append((idx, variant))

    explicit_pattern = re.compile(
        r"\b(?:full\s+)?([A-Za-z0-9.\-]+(?:\s+[A-Za-z0-9.\-]+){0,2})\b"
    )
    for match in explicit_pattern.finditer(sentence):
        alias = match.group(1)
        canonical = _resolve_variant_alias(alias, variants, family_root)
        if not canonical:
            continue
        if canonical.endswith("%"):
            continue
        if canonical.lower() in {"on swe-bench", "on osworld", "the flagship"}:
            continue
        if any(term in canonical.lower() for term in VARIANT_TERMS) or "flagship" in canonical.lower():
            mentions.append((match.start(), canonical))

    if "flagship" in lower and family_root:
        mentions.append((lower.find("flagship"), f"{family_root} (flagship)"))
    if "full gpt" in lower and family_root:
        mentions.append((lower.find("full gpt"), f"{family_root} (flagship)"))

    ordered: list[str] = []
    seen: set[str] = set()
    for _, mention in sorted(mentions, key=lambda item: item[0]):
        if mention.lower() in seen:
            continue
        seen.add(mention.lower())
        ordered.append(mention)
    return ordered


def extract_benchmark_facts(item: dict) -> list[dict[str, str]]:
    variants = detect_model_release_variants(
        item.get("headline", ""),
        entities=item.get("entities", []),
        raw_content=_normalise_text(item.get("raw_content", "")),
    )
    family_root = infer_model_family_root(variants)
    facts: list[dict[str, str]] = extract_benchmark_table_facts(item)

    for blob in collect_model_release_text_blobs(item):
        text = blob.get("text", "")
        if not text:
            continue
        blob_default_model = _default_model_from_blob(blob, variants, family_root)
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        for sentence in sentences:
            benchmarks = extract_benchmark_mentions(sentence)
            if not benchmarks:
                continue
            scores = re.findall(r"\b\d+(?:\.\d+)?%", sentence)
            if not scores:
                continue

            benchmark = benchmarks[0]
            models = _extract_model_mentions(sentence, variants, family_root)
            url = blob.get("source_url", "")

            direct = re.finditer(
                r"(?P<model>[A-Za-z0-9.\-]+(?:\s+[A-Za-z0-9.\-]+){0,3})\s+"
                r"(?:scores?|scored|at)\s+(?P<score>\d+(?:\.\d+)?)%",
                sentence,
                re.IGNORECASE,
            )
            for match in direct:
                model = _resolve_variant_alias(match.group("model"), variants, family_root)
                if not model:
                    continue
                facts.append(
                    {
                        "benchmark": benchmark,
                        "model": model,
                        "score": f"{match.group('score')}%",
                        "source_url": url,
                    }
                )

            possessive = re.finditer(
                r"(?P<model>[A-Za-z0-9.\-]+(?:\s+[A-Za-z0-9.\-]+){0,3})'?s\s+"
                r"(?P<score>\d+(?:\.\d+)?)%",
                sentence,
                re.IGNORECASE,
            )
            for match in possessive:
                model = _resolve_variant_alias(match.group("model"), variants, family_root)
                if not model:
                    continue
                facts.append(
                    {
                        "benchmark": benchmark,
                        "model": model,
                        "score": f"{match.group('score')}%",
                        "source_url": url,
                    }
                )

            if not models:
                models = [blob_default_model] if blob_default_model else variants[:1]
            if models and not any(f["benchmark"] == benchmark and f["source_url"] == url for f in facts):
                if len(scores) == len(models):
                    pairs = zip(models, scores)
                elif len(scores) == 1:
                    pairs = [(models[0], scores[0])]
                elif len(scores) >= 2 and len(models) == 1 and "vs" in sentence.lower() and family_root:
                    baseline = f"{family_root} predecessor"
                    pairs = [(models[0], scores[0]), (baseline, scores[1])]
                else:
                    pairs = [(models[0], scores[0])]
                for model, score in pairs:
                    facts.append(
                        {
                            "benchmark": benchmark,
                            "model": model,
                            "score": score,
                            "source_url": url,
                        }
                    )

    facts = _dedupe_dicts(facts, ("benchmark", "model", "score", "source_url"))
    facts.sort(key=lambda fact: (benchmark_priority_key(fact["benchmark"]), fact["model"].lower()))
    return facts


def extract_key_number_facts(item: dict) -> list[dict[str, str]]:
    variants = detect_model_release_variants(
        item.get("headline", ""),
        entities=item.get("entities", []),
        raw_content=_normalise_text(item.get("raw_content", "")),
    )
    family_root = infer_model_family_root(variants)
    facts: list[dict[str, str]] = []

    for blob in collect_model_release_text_blobs(item):
        text = blob.get("text", "")
        if not text:
            continue
        blob_default_model = _default_model_from_blob(blob, variants, family_root)
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        for sentence in sentences:
            lower = sentence.lower()
            url = blob.get("source_url", "")
            models = _extract_model_mentions(sentence, variants, family_root)
            first_model = models[0] if models else blob_default_model
            model_suffix = _model_suffix_for_label(first_model) if first_model else ""

            direct_price = re.finditer(
                r"\$(\d+(?:\.\d+)?)\s*/\s*\$(\d+(?:\.\d+)?)",
                sentence,
                re.IGNORECASE,
            )
            for match in direct_price:
                matched_model = _model_for_match(
                    sentence,
                    match.start(),
                    variants,
                    family_root,
                    blob_default_model,
                )
                matched_suffix = _model_suffix_for_label(matched_model) if matched_model else model_suffix
                facts.append(
                    {
                        "label": f"Pricing{matched_suffix}",
                        "value": f"${match.group(1)}/${match.group(2)}",
                        "qualifier": "per 1M in/out tokens",
                        "source_url": url,
                        "kind": "pricing",
                    }
                )

            compact_price = re.finditer(
                r"(?:price\s*)?\$(\d+(?:\.\d+)?)\s*[•·/]\s*\$(\d+(?:\.\d+)?)"
                r"(?:\s*(?:input|in)\s*[•·/]\s*(?:output|out))?",
                sentence,
                re.IGNORECASE,
            )
            for match in compact_price:
                matched_model = _model_for_match(
                    sentence,
                    match.start(),
                    variants,
                    family_root,
                    blob_default_model,
                )
                matched_suffix = _model_suffix_for_label(matched_model) if matched_model else model_suffix
                facts.append(
                    {
                        "label": f"Pricing{matched_suffix}",
                        "value": f"${match.group(1)}/${match.group(2)}",
                        "qualifier": "per 1M in/out tokens",
                        "source_url": url,
                        "kind": "pricing",
                    }
                )

            long_price = re.finditer(
                r"\$(\d+(?:\.\d+)?)\s+per\s+(?:1m|one\s+million|million)\s+input\s+tokens?"
                r".{0,80}?\$(\d+(?:\.\d+)?)\s+per\s+(?:1m|one\s+million|million)\s+output\s+tokens?",
                sentence,
                re.IGNORECASE,
            )
            for match in long_price:
                matched_model = _model_for_match(
                    sentence,
                    match.start(),
                    variants,
                    family_root,
                    blob_default_model,
                )
                matched_suffix = _model_suffix_for_label(matched_model) if matched_model else model_suffix
                facts.append(
                    {
                        "label": f"Pricing{matched_suffix}",
                        "value": f"${match.group(1)}/${match.group(2)}",
                        "qualifier": "per 1M in/out tokens",
                        "source_url": url,
                        "kind": "pricing",
                    }
                )

            context = (
                re.search(
                    r"(\d[\d,]*(?:\.\d+)?)\s*(k|m)?(?:-|\s)?tokens?\s+of\s+context",
                    sentence,
                    re.IGNORECASE,
                )
                or re.search(
                    r"(\d[\d,]*(?:\.\d+)?)\s*(k|m)?(?:-|\s)?tokens?\s+context\s+window",
                    sentence,
                    re.IGNORECASE,
                )
                or re.search(
                    r"(\d[\d,]*(?:\.\d+)?)\s*(k|m)?\s+context\s+window",
                    sentence,
                    re.IGNORECASE,
                )
                or re.search(
                    r"(\d[\d,]*(?:\.\d+)?)\s*(k|m)?(?:-|\s)?token\s+context",
                    sentence,
                    re.IGNORECASE,
                )
            )
            if context:
                number = context.group(1).replace(",", "")
                suffix = (context.group(2) or "").upper()
                value = f"{number}{suffix}" if suffix else number
                matched_model = _model_for_match(
                    sentence,
                    context.start(),
                    variants,
                    family_root,
                    blob_default_model,
                )
                matched_suffix = _model_suffix_for_label(matched_model) if matched_model else model_suffix
                facts.append(
                    {
                        "label": f"Context{matched_suffix}",
                        "value": value,
                        "qualifier": "tokens",
                        "source_url": url,
                        "kind": "context",
                    }
                )

            speed = re.search(r"(\d+(?:\.\d+)?)\s*x\s+faster", sentence, re.IGNORECASE)
            if speed:
                qualifier = "faster than predecessor"
                if "gpt-5 mini" in lower:
                    qualifier = "faster than GPT-5 mini"
                facts.append(
                    {
                        "label": f"Speed{model_suffix}",
                        "value": f"~{speed.group(1)}x",
                        "qualifier": qualifier,
                        "source_url": url,
                        "kind": "speed",
                    }
                )

    facts = _dedupe_dicts(facts, ("label", "value", "qualifier", "source_url"))
    return facts


def extract_coverage_notes(item: dict) -> list[str]:
    notes: list[str] = []
    combined = " ".join(blob.get("text", "") for blob in collect_model_release_text_blobs(item)).lower()

    if "not disclosed" in combined:
        if "pricing" in combined:
            notes.append("Pricing not disclosed in available source material.")
        if "parameter" in combined or "model size" in combined:
            notes.append("Parameter count not disclosed in available source material.")
        if "training" in combined:
            notes.append("Specific training methodology not disclosed.")
    if "not yet announced" in combined:
        if "availability" in combined:
            notes.append("Availability not yet announced.")
        if "benchmark" in combined:
            notes.append("Benchmarks not yet available in source material.")
    if "api-only" in combined:
        notes.append("Some release variants are API-only.")

    return list(dict.fromkeys(notes))


def build_model_release_packet(item: dict) -> dict[str, Any]:
    benchmark_facts = extract_benchmark_facts(item)
    key_number_facts = extract_key_number_facts(item)
    coverage_notes = extract_coverage_notes(item)

    existing_benchmark_facts = [
        fact for fact in (item.get("benchmark_facts") or []) if isinstance(fact, dict)
    ]
    if existing_benchmark_facts:
        benchmark_facts = _dedupe_dicts(
            [*benchmark_facts, *existing_benchmark_facts],
            ("benchmark", "model", "score", "source_url"),
        )

    existing_key_number_facts = [
        fact for fact in (item.get("key_number_facts") or []) if isinstance(fact, dict)
    ]
    if existing_key_number_facts:
        key_number_facts = _dedupe_dicts(
            [*key_number_facts, *existing_key_number_facts],
            ("label", "value", "qualifier", "source_url"),
        )

    existing_coverage_notes = [str(note) for note in (item.get("coverage_notes") or []) if note]
    if existing_coverage_notes:
        coverage_notes = list(dict.fromkeys([*coverage_notes, *existing_coverage_notes]))
    text_blobs = collect_model_release_text_blobs(item)
    benchmark_mentions = Counter()
    for blob in text_blobs:
        for name in extract_benchmark_mentions(blob.get("text", "")):
            benchmark_mentions[name] += 1

    benchmark_families = sorted(
        {fact["benchmark"] for fact in benchmark_facts},
        key=benchmark_priority_key,
    )
    variants = detect_model_release_variants(
        item.get("headline", ""),
        entities=item.get("entities", []),
        raw_content=_normalise_text(item.get("raw_content", "")),
    )
    source_blobs = [
        {
            "url": blob.get("source_url", ""),
            "title": blob.get("title", ""),
            "snippet": blob.get("text", "")[:400],
        }
        for blob in text_blobs
        if blob.get("source_url")
    ]
    official_source_found = any(
        "official" in classify_model_release_result(src["url"], src["title"], src["snippet"])
        for src in source_blobs
    )
    pricing_found = any(fact.get("kind") == "pricing" for fact in key_number_facts) or any(
        "pricing not disclosed" in note.lower() for note in coverage_notes
    )
    availability_found = bool(
        re.search(
            r"\b(api|chatgpt|codex|vertex ai|azure ai foundry|bedrock|hugging face|available today|roll(?:ing)? out)\b",
            " ".join(blob.get("text", "") for blob in text_blobs),
            re.IGNORECASE,
        )
    ) or any("availability not yet announced" in note.lower() for note in coverage_notes)

    return {
        "benchmark_facts": benchmark_facts,
        "key_number_facts": key_number_facts,
        "coverage_notes": coverage_notes,
        "benchmark_families_found": benchmark_families,
        "benchmark_mentions": sorted(benchmark_mentions.keys(), key=benchmark_priority_key),
        "official_source_found": official_source_found,
        "pricing_found": pricing_found,
        "availability_found": availability_found,
        "dual_model_release": len(variants) >= 2,
        "variants": variants,
    }


def packet_needs_limited_benchmark_note(packet: dict[str, Any]) -> bool:
    return (
        len(packet.get("benchmark_families_found", [])) < 3
        and bool(packet.get("benchmark_mentions"))
        and not any("limited benchmark" in note.lower() for note in packet.get("coverage_notes", []))
    )


def summarise_model_release_completeness(
    packet: dict[str, Any],
    search_exhausted: bool = False,
) -> dict[str, Any]:
    notes = list(packet.get("coverage_notes", []))
    benchmark_families = list(packet.get("benchmark_families_found", []))
    if search_exhausted and packet_needs_limited_benchmark_note(packet):
        notes.append(
            f"Available source material publishes only {len(benchmark_families)} benchmark "
            "families with numeric scores."
        )

    benchmark_requirement_met = len(benchmark_families) >= 3
    missing: list[str] = []
    if not packet.get("official_source_found"):
        missing.append("official/model-card source")
    if not packet.get("pricing_found"):
        missing.append("pricing")
    if not packet.get("availability_found"):
        missing.append("availability")
    if not benchmark_requirement_met:
        missing.append("3 benchmark families")

    return {
        "complete": not missing,
        "missing": missing,
        "coverage_notes": notes,
        "benchmark_families_found": benchmark_families,
        "official_source_found": bool(packet.get("official_source_found")),
        "pricing_found": bool(packet.get("pricing_found")),
        "availability_found": bool(packet.get("availability_found")),
        "dual_model_release": bool(packet.get("dual_model_release")),
    }


def attach_model_release_packet(item: dict, search_exhausted: bool = False) -> dict:
    packet = build_model_release_packet(item)
    completeness = summarise_model_release_completeness(packet, search_exhausted=search_exhausted)

    item["benchmark_facts"] = packet["benchmark_facts"]
    item["key_number_facts"] = packet["key_number_facts"]
    item["coverage_notes"] = completeness["coverage_notes"]

    enrichment = item.get("_enrichment")
    if isinstance(enrichment, dict):
        enrichment["benchmark_families_found"] = completeness["benchmark_families_found"]
        enrichment["official_source_found"] = completeness["official_source_found"]
        enrichment["pricing_found"] = completeness["pricing_found"]
        enrichment["availability_found"] = completeness["availability_found"]
        enrichment["dual_model_release"] = completeness["dual_model_release"]

    return item


def validate_model_release_output(source_item: dict, output_item: dict) -> list[str]:
    """Compare structured extraction coverage to Ghostwriter output."""
    issues: list[str] = []
    source_benchmarks = {
        canonicalise_benchmark_name(fact.get("benchmark", ""))
        for fact in source_item.get("benchmark_facts", []) or []
        if fact.get("benchmark")
    }
    output_data = output_item.get("model_release_data") or {}
    output_rows = (
        ((output_data.get("benchmarks") or {}).get("rows") or [])
        if isinstance(output_data, dict)
        else []
    )
    output_benchmarks = {
        canonicalise_benchmark_name(str(row.get("benchmark", "")))
        for row in output_rows
        if isinstance(row, dict) and row.get("benchmark")
    }
    expected_rows = len(source_benchmarks)
    if expected_rows and len(output_rows) < expected_rows:
        issues.append(
            f"Source packet has {len(source_benchmarks)} benchmark families but output only has {len(output_rows)} rows"
        )
    missing_benchmarks = sorted(source_benchmarks - output_benchmarks, key=benchmark_priority_key)
    if missing_benchmarks:
        issues.append(
            f"Output dropped benchmark families present in source packet: {missing_benchmarks}"
        )

    source_models_by_benchmark: dict[str, set[str]] = {}
    for fact in source_item.get("benchmark_facts", []) or []:
        benchmark = canonicalise_benchmark_name(fact.get("benchmark", ""))
        model = str(fact.get("model", "")).strip()
        score = str(fact.get("score", "")).strip()
        if not benchmark or not model or not _score_present(score):
            continue
        source_models_by_benchmark.setdefault(benchmark, set()).add(model)

    for row in output_rows:
        if not isinstance(row, dict):
            continue
        benchmark = canonicalise_benchmark_name(str(row.get("benchmark", "")))
        source_model_count = len(source_models_by_benchmark.get(benchmark, set()))
        if source_model_count < 2:
            continue
        output_score_count = sum(
            1 for score in (row.get("scores") or []) if _score_present(str(score))
        )
        if output_score_count < source_model_count:
            issues.append(
                f"Output row for {benchmark} has {output_score_count} populated scores but source packet supports {source_model_count}"
            )

    required_kinds = {
        KEY_NUMBER_KIND_ALIASES.get(str(fact.get("kind", "")).lower())
        for fact in source_item.get("key_number_facts", []) or []
        if KEY_NUMBER_KIND_ALIASES.get(str(fact.get("kind", "")).lower()) in {"pricing", "context", "speed"}
    }
    key_numbers = output_data.get("key_numbers") or [] if isinstance(output_data, dict) else []
    rendered_labels = " ".join(
        str(number.get("label", "")).lower() for number in key_numbers if isinstance(number, dict)
    )
    for kind in sorted(required_kinds):
        if kind and kind not in rendered_labels:
            issues.append(f"Output dropped extracted {kind} key number")

    return issues
