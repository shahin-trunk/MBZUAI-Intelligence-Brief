"""Deterministic fallback inference for entity categories.

Used when the LLM-based Entity Classifier returns no category for an item
or when the stage fails open. The goal is not perfect taxonomy; it is a
durable, high-signal fallback so downstream surfaces do not collapse to a
generic badge for otherwise classifiable items.
"""

from __future__ import annotations

import re
from typing import Optional

from models.schemas import EntityCategory

COUNTRY_NAMES = {
    "uae",
    "united arab emirates",
    "saudi arabia",
    "ksa",
    "qatar",
    "oman",
    "bahrain",
    "kuwait",
    "iran",
    "iraq",
    "israel",
    "lebanon",
    "syria",
    "jordan",
    "egypt",
    "turkey",
    "turkiye",
    "china",
    "united states",
    "united states of america",
    "us",
    "usa",
    "united kingdom",
    "uk",
    "great britain",
    "france",
    "germany",
    "italy",
    "spain",
    "india",
    "japan",
    "singapore",
    "south korea",
    "korea",
}

MODEL_TERMS = re.compile(
    r"\b(model|models|llm|foundation model|frontier model|reasoning model|"
    r"multimodal|weights|checkpoint|benchmark|inference)\b",
    re.I,
)
DEFENSE_TERMS = re.compile(
    r"\b(centcom|pentagon|ministry of defense|ministry of defence|"
    r"department of defense|department of defence|armed forces|military|navy|"
    r"army|air force|marines|brigade|fleet|command|missile|defense|defence)\b",
    re.I,
)
GOVERNMENT_TERMS = re.compile(
    r"\b(government|ministry|department|president|prime minister|crown prince|"
    r"sheikh|emir|royal court|parliament|congress|senate|cabinet|administration|"
    r"commission|municipality|authority|council|state department|treasury|"
    r"foreign office|mayor)\b",
    re.I,
)
UNIVERSITY_TERMS = re.compile(
    r"\b(university|college|school of|academy|polytechnic|campus|"
    r"institute of technology)\b",
    re.I,
)
ENERGY_TERMS = re.compile(
    r"\b(energy|oil|gas|lng|petroleum|power|renewable|solar|wind|nuclear|"
    r"electricity|utility|utilities|adnoc|aramco|opec)\b",
    re.I,
)
FINANCE_TERMS = re.compile(
    r"\b(bank|capital|finance|financial|fund|funds|investment|investments|"
    r"investor|investors|asset management|wealth|ventures|venture|private equity|"
    r"securities|exchange|holdings|mubadala|adia|blackrock|goldman|jpmorgan)\b",
    re.I,
)
ORG_TERMS = re.compile(
    r"\b(foundation|association|society|alliance|coalition|forum|initiative|"
    r"network|committee|ngo|nonprofit|non profit|charity|united nations|"
    r"unesco|oecd|who|world economic forum|brookings)\b",
    re.I,
)
COMPANY_TERMS = re.compile(
    r"\b(company|corp|corporation|inc|llc|ltd|plc|gmbh|ag|group|technologies|"
    r"technology|tech|systems|labs|lab|openai|anthropic|google|microsoft|meta|"
    r"amazon|apple|nvidia|alibaba|tesla)\b",
    re.I,
)


def _normalize(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.\-]+", " ", value.lower())).strip()


def _category_from_domain(domain: str) -> Optional[EntityCategory]:
    if not domain:
        return None
    if domain.endswith(".mil"):
        return "defense"
    if domain.endswith(".gov"):
        return "government"
    _ACADEMIC_SUFFIXES = (".edu", ".ac.ae", ".ac.uk", ".ac.jp", ".ac.nz", ".ac.in", ".ac.kr", ".ac.za", ".ac.at", ".ac.il")
    if domain.endswith(_ACADEMIC_SUFFIXES):
        return "university"
    if domain.endswith(".org"):
        return "org"
    return None


def infer_entity_category(item: dict) -> Optional[EntityCategory]:
    """Infer a plausible category from item metadata.

    Returns None when the heuristic does not have enough signal.

    Priority order (first match wins):
      domain → model_release flag → model terms → country name →
      defense → government → university → energy → finance → org →
      company → section fallback
    """

    existing = item.get("primary_entity_category")
    if isinstance(existing, str) and existing:
        return existing  # already resolved upstream

    if item.get("is_model_release") or item.get("model_release_data"):
        return "model"

    primary_entity = _normalize(item.get("primary_entity"))
    source_domain = _normalize(item.get("source_domain")).removeprefix("www.")
    combined = " ".join(
        part for part in [
            primary_entity,
            _normalize(item.get("headline")),
            _normalize(item.get("source_name")),
            source_domain,
            _normalize(item.get("section")),
            " ".join(_normalize(v) for v in (item.get("entities") or []) if v),
        ] if part
    )

    domain_category = _category_from_domain(source_domain)
    if domain_category:
        return domain_category

    if MODEL_TERMS.search(combined):
        return "model"
    if primary_entity and primary_entity in COUNTRY_NAMES:
        return "country"
    if DEFENSE_TERMS.search(combined):
        return "defense"
    if GOVERNMENT_TERMS.search(combined):
        return "government"
    if UNIVERSITY_TERMS.search(combined):
        return "university"
    if ENERGY_TERMS.search(combined):
        return "energy"
    if FINANCE_TERMS.search(combined):
        return "finance"
    if ORG_TERMS.search(combined):
        return "org"
    if COMPANY_TERMS.search(combined):
        return "company"
    if "model releases" in combined or "technical developments" in combined:
        return "model"

    # Keep the fallback conservative; the frontend still has a last-resort
    # presentation heuristic for weakly typed items.
    return None
