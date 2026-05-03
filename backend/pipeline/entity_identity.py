"""Resolve story identity fields for display.

Separates the narrative subject (`primary_entity`) from the best visual badge
subject (`badge_subject`). This lets UI surfaces show a stable, legible badge
even when the most specific actor is an organ of state, military command, or
senior official rather than the country most readers would recognize.
"""

from __future__ import annotations

import re
from typing import Optional

from models.schemas import EntityCategory, SubjectType
from pipeline.entity_category import infer_entity_category

COUNTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "United Arab Emirates": (
        "uae",
        "united arab emirates",
        "abu dhabi",
        "dubai",
        "sharjah",
        "ajman",
        "fujairah",
        "ras al khaimah",
        "umm al quwain",
        "al ain",
    ),
    "United States": (
        "united states",
        "united states of america",
        "us",
        "usa",
        "american",
        "washington",
        "white house",
    ),
    "United Kingdom": ("united kingdom", "uk", "britain", "great britain"),
    "Saudi Arabia": ("saudi arabia", "ksa", "kingdom of saudi arabia"),
    "Qatar": ("qatar",),
    "Oman": ("oman",),
    "Bahrain": ("bahrain",),
    "Kuwait": ("kuwait",),
    "Iran": ("iran", "iranian"),
    "Iraq": ("iraq", "iraqi"),
    "Israel": ("israel", "israeli"),
    "Lebanon": ("lebanon", "lebanese"),
    "Syria": ("syria", "syrian"),
    "Jordan": ("jordan", "jordanian"),
    "Egypt": ("egypt", "egyptian"),
    "Turkey": ("turkey", "turkiye", "turkish"),
    "China": ("china", "chinese", "beijing"),
    "France": ("france", "french"),
    "Germany": ("germany", "german"),
    "Italy": ("italy", "italian"),
    "Spain": ("spain", "spanish"),
    "India": ("india", "indian"),
    "Japan": ("japan", "japanese"),
    "Singapore": ("singapore",),
    "South Korea": ("south korea", "korea", "korean"),
}

COUNTRY_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "United Arab Emirates": ("united arab emirates", "uae"),
    "United States": ("united states", "united states of america", "us", "usa"),
    "United Kingdom": ("united kingdom", "uk", "britain", "great britain"),
    "Saudi Arabia": ("saudi arabia", "ksa", "kingdom of saudi arabia"),
    "Qatar": ("qatar",),
    "Oman": ("oman",),
    "Bahrain": ("bahrain",),
    "Kuwait": ("kuwait",),
    "Iran": ("iran",),
    "Iraq": ("iraq",),
    "Israel": ("israel",),
    "Lebanon": ("lebanon",),
    "Syria": ("syria",),
    "Jordan": ("jordan",),
    "Egypt": ("egypt",),
    "Turkey": ("turkey", "turkiye"),
    "China": ("china",),
    "France": ("france",),
    "Germany": ("germany",),
    "Italy": ("italy",),
    "Spain": ("spain",),
    "India": ("india",),
    "Japan": ("japan",),
    "Singapore": ("singapore",),
    "South Korea": ("south korea",),
}

ORG_PARENT_COUNTRY_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(centcom|u\.?s\.? central command|pentagon|white house|congress|senate)\b", re.I), "United States"),
    (re.compile(r"\b(cia|fbi|nasa|treasury|state department|department of defense|department of state)\b", re.I), "United States"),
    (re.compile(r"\b(cbu(?:ae)?|central bank of the united arab emirates|uae government|adcmc|adnoc|etihad rail)\b", re.I), "United Arab Emirates"),
    (re.compile(r"\b(ministry of defence|mod)\b.*\b(uae|emirates)\b", re.I), "United Arab Emirates"),
)

TITLED_PERSON_TERMS = re.compile(
    r"\b(president|prime minister|crown prince|sheikh|emir|king|queen|"
    r"foreign minister|defense minister|minister|secretary of state|"
    r"ruler|deputy ruler)\b",
    re.I,
)

ORG_LABEL_TERMS = re.compile(
    r"\b(university|college|institute|ministry|department|agency|command|"
    r"capital|bank|fund|authority|commission|council|group|labs?|lab|"
    r"technologies|technology|systems|rail|holdings|foundation|association|"
    r"alliance|committee|airways|government|office)\b",
    re.I,
)

PLACE_TERMS = re.compile(
    r"\b(city|state|province|county|region|emirate|island|port|strait|gulf)\b",
    re.I,
)

PLACE_NAMES = {
    "abu dhabi",
    "dubai",
    "sharjah",
    "ajman",
    "fujairah",
    "ras al khaimah",
    "umm al quwain",
    "al ain",
    "maine",
}

ASSET_TERMS = re.compile(
    r"\b(brent|wti|crude|oil|gas|lng|index|yield|bond|treasury|bitcoin|"
    r"ethereum|gold|silver|nasdaq|dow|s&p|nikkei|euro stoxx)\b",
    re.I,
)

PERSON_PARTICLES = {"bin", "bint", "ibn", "abu"}

COUNTRY_TOKENS = {
    "us", "usa", "america", "american",
    "uk", "britain", "british",
    "uae", "emirates", "emirati",
    "saudi", "ksa", "arabia",
    "iran", "iranian",
    "iraq", "iraqi",
    "israel", "israeli",
    "lebanon", "lebanese",
    "syria", "syrian",
    "jordan", "jordanian",
    "egypt", "egyptian",
    "turkey", "turkiye", "turkish",
    "china", "chinese",
    "france", "french",
    "germany", "german",
    "italy", "italian",
    "spain", "spanish",
    "india", "indian",
    "japan", "japanese",
    "korea", "korean",
    "russia", "russian",
    "qatar", "qatari",
    "oman", "omani",
    "bahrain", "bahraini",
    "kuwait", "kuwaiti",
    "singapore",
}

REGIONAL_DESCRIPTORS = {"mena", "gcc", "apac", "emea", "latam", "eu", "asean"}

SECTOR_NOUNS = {
    "startup", "startups", "funding", "market", "markets", "region",
    "sector", "sectors", "economy", "economies", "trade", "tech",
    "business", "banking", "finance", "investment", "investments",
    "industry", "industries",
}

NOISY_UPPERCASE_TOKENS = {"TEST", "TODO", "PLACEHOLDER", "FIXME", "XXX"}

_COMPOUND_AND_PATTERN = re.compile(r"\s+(?:and|&)\s+", re.I)


def _looks_proper(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    return stripped[:1].isupper()


def _is_noisy_entity_label(label: Optional[str]) -> bool:
    """Return True when the label isn't a single coherent actor.

    Catches compound phrases ("ASML and TSMC"), hyphen-joined country
    pairs ("US-Iran"), sector descriptors ("MENA Startup"), and test
    leaks ("supply TEST") so downstream UI falls back to a category
    icon instead of rendering a misleading logo lookup or alt-text.
    """
    if not isinstance(label, str):
        return False
    text = re.sub(r"\*\*|[_`]+", "", label)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return False

    for token in text.split():
        if token.strip(".,;:!?") in NOISY_UPPERCASE_TOKENS:
            return True

    if _COMPOUND_AND_PATTERN.search(text):
        parts = [p.strip() for p in _COMPOUND_AND_PATTERN.split(text) if p.strip()]
        if len(parts) >= 2 and all(_looks_proper(p) for p in parts):
            return True

    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) >= 2 and all(_looks_proper(p) for p in parts):
            return True

    for piece in text.split():
        if piece.count("-") == 1:
            left, right = piece.split("-", 1)
            if (
                left
                and right
                and left.lower() in COUNTRY_TOKENS
                and right.lower() in COUNTRY_TOKENS
                and left[:1].isupper()
                and right[:1].isupper()
            ):
                return True

    tokens = text.lower().split()
    if (
        len(tokens) >= 2
        and tokens[0] in REGIONAL_DESCRIPTORS
        and tokens[1] in SECTOR_NOUNS
    ):
        return True

    return False


def _normalize(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.\-]+", " ", value)).strip()


def _first_nonempty(*values: object) -> Optional[str]:
    for value in values:
        text = _normalize(value)
        if text:
            return text
    return None


def _extract_country(text: str) -> Optional[str]:
    if not text:
        return None
    haystack = f" {text.lower()} "
    for country, aliases in COUNTRY_ALIASES.items():
        for alias in aliases:
            if f" {alias.lower()} " in haystack:
                return country
    return None


def _country_from_label(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    normalized = _normalize(label).lower()
    if not normalized:
        return None
    for country, aliases in COUNTRY_LABEL_ALIASES.items():
        if normalized in aliases:
            return country
    return None


def _country_from_org(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    for pattern, country in ORG_PARENT_COUNTRY_RULES:
        if pattern.search(label):
            return country
    return None


def _is_informative_label(label: Optional[str]) -> bool:
    if not label:
        return False
    compact = label.replace(".", "").strip()
    if len(compact) >= 3:
        return True
    return len(compact.split()) >= 2


def _looks_like_person(label: Optional[str]) -> bool:
    if not label:
        return False
    if TITLED_PERSON_TERMS.search(label):
        return True
    normalized = _normalize(label).lower()
    if not normalized or ORG_LABEL_TERMS.search(normalized):
        return False
    tokens = [token for token in normalized.split() if token]
    if not 2 <= len(tokens) <= 5:
        return False
    if any(token in PERSON_PARTICLES for token in tokens):
        return True
    return all(token.replace(".", "").isalpha() for token in tokens)


def _looks_like_place(label: Optional[str]) -> bool:
    if not label:
        return False
    normalized = _normalize(label).lower()
    if normalized in PLACE_NAMES:
        return True
    return bool(PLACE_TERMS.search(normalized))


def _looks_like_asset(label: Optional[str]) -> bool:
    if not label:
        return False
    return bool(ASSET_TERMS.search(label))


def _resolve_subject_type(
    label: Optional[str],
    category: Optional[EntityCategory],
    item: dict,
) -> Optional[SubjectType]:
    if not label:
        return None

    model_release = item.get("model_release_data")
    model_name = None
    if isinstance(model_release, dict):
        model_name = _first_nonempty(model_release.get("model_name"))

    normalized_label = _normalize(label).lower()
    normalized_model_name = _normalize(model_name).lower() if model_name else ""

    if normalized_model_name and normalized_label == normalized_model_name:
        return "model"
    if category == "model" and (item.get("is_model_release") or model_release):
        return "model"
    if _country_from_label(label):
        return "country"
    if _looks_like_person(label):
        return "person"
    if _looks_like_place(label):
        return "place"
    if _looks_like_asset(label):
        return "asset"
    if category in {"company", "university", "government", "energy", "finance", "defense", "org"}:
        return "organization"
    if category == "country":
        return "country"
    return "other"


def resolve_story_identity(
    item: dict,
    primary_entity_category: Optional[EntityCategory] = None,
) -> dict[str, Optional[str]]:
    """Return explicit story identity fields for UI and downstream storage."""

    raw_primary_entity = item.get("primary_entity")
    effective_primary_entity = (
        None
        if isinstance(raw_primary_entity, str)
        and _is_noisy_entity_label(raw_primary_entity)
        else raw_primary_entity
    )
    primary_subject_candidate = _first_nonempty(
        effective_primary_entity,
        (item.get("model_release_data") or {}).get("developer")
        if isinstance(item.get("model_release_data"), dict) else None,
        (item.get("model_release_data") or {}).get("model_name")
        if isinstance(item.get("model_release_data"), dict) else None,
    )
    category = primary_entity_category or infer_entity_category(item)
    primary_subject_type = _resolve_subject_type(primary_subject_candidate, category, item)
    primary_subject = (
        primary_subject_candidate
        if primary_subject_candidate
        and (
            _is_informative_label(primary_subject_candidate)
            or primary_subject_type not in {None, "other"}
        )
        else None
    )
    if primary_subject is None:
        primary_subject_type = None

    combined_text = " ".join(
        part for part in (
            primary_subject_candidate,
            _normalize(item.get("headline")),
            _normalize(item.get("section")),
            _normalize(item.get("source_name")),
            _normalize(item.get("source_domain")),
            " ".join(_normalize(v) for v in (item.get("entities") or []) if v),
        )
        if part
    )

    mentioned_country = _extract_country(primary_subject_candidate or "") or _extract_country(combined_text)
    badge_subject: Optional[str] = None
    badge_category: Optional[EntityCategory] = None

    if item.get("is_model_release") or item.get("model_release_data"):
        developer = None
        if isinstance(item.get("model_release_data"), dict):
            developer = _first_nonempty(item["model_release_data"].get("developer"))
        if developer:
            badge_subject, badge_category = developer, "company"
        elif primary_subject:
            badge_subject, badge_category = primary_subject, category

    if badge_subject is None and category == "country" and primary_subject:
        badge_subject, badge_category = mentioned_country or primary_subject, "country"

    if badge_subject is None and category in {"government", "defense"}:
        parent_country = _country_from_org(primary_subject) or mentioned_country
        if parent_country:
            badge_subject, badge_category = parent_country, "country"
        elif primary_subject:
            badge_subject, badge_category = primary_subject, category

    if badge_subject is None and primary_subject and TITLED_PERSON_TERMS.search(primary_subject):
        if mentioned_country:
            badge_subject, badge_category = mentioned_country, "country"

    if badge_subject is None and primary_subject and category is not None:
        badge_subject, badge_category = primary_subject, category

    if badge_subject is None and _is_informative_label(primary_subject):
        badge_subject, badge_category = primary_subject, None

    if badge_subject is None and mentioned_country:
        badge_subject, badge_category = mentioned_country, "country"

    badge_subject_type = _resolve_subject_type(badge_subject, badge_category or category, item)
    return {
        "primary_subject": primary_subject,
        "primary_subject_type": primary_subject_type,
        "badge_subject": badge_subject,
        "badge_subject_type": badge_subject_type,
        "badge_subject_category": badge_category,
    }


def resolve_badge_identity(
    item: dict,
    primary_entity_category: Optional[EntityCategory] = None,
) -> tuple[Optional[str], Optional[EntityCategory]]:
    identity = resolve_story_identity(item, primary_entity_category)
    return identity["badge_subject"], identity["badge_subject_category"]  # type: ignore[return-value]
