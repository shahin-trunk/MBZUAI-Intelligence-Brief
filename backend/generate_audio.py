#!/usr/bin/env python3
"""
Generate audio briefing from daily brief JSON.

Transforms a structured brief into a spoken script (via Claude Sonnet),
synthesizes speech (via TTS), and uploads to Supabase Storage.

Usage:
    python3.11 generate_audio.py                     # Generate audio for today's brief
    python3.11 generate_audio.py --date 2026-03-04   # Generate for a specific date
    python3.11 generate_audio.py --script-only       # Generate script only, no TTS
    python3.11 generate_audio.py --backfill          # Generate for all briefs missing audio
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent            # backend/
PROJECT_ROOT = SCRIPT_DIR.parent                        # Intelligence Dashboard/
FRONTEND_DIR = PROJECT_ROOT / "frontend"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
PROMPTS_DIR = SCRIPT_DIR / "prompts"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ANTHROPIC_MODEL = "claude-sonnet-4-6"
SCRIPT_MAX_TOKENS = 4096
SCRIPT_VALIDATION_MAX_TOKENS = 700
SCRIPT_GENERATION_MAX_ATTEMPTS = 3
LANGUAGE_SCRIPT_BUDGETS = {
    "en": {
        "target_words": 850,
        "hard_max_words": 0,       # disabled — user prefers natural length
        "hard_max_chars": 15000,   # generous ceiling to prevent runaway
    },
    "fr": {
        "target_words": 950,
        "hard_max_words": 1250,
        "hard_max_chars": 9500,
    },
    "ar": {
        "target_words": 900,
        "hard_max_words": 1200,
        "hard_max_chars": 9500,
    },
}
BREAK_TAG_PATTERN = r'<break\s+time="[^"]+"\s*/>'

# English stop words for bilingual script validation — used to detect whether
# a script contains actual English narration vs pure target language.
ENGLISH_STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "could", "did", "do", "does", "doing",
    "done", "down", "during", "each", "few", "for", "from", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "let",
    "lets", "look", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "now", "of", "off", "on", "once", "only", "or", "other", "our", "ours",
    "ourselves", "out", "over", "own", "per", "quite", "rather", "said", "same",
    "see", "she", "should", "show", "shown", "shows", "so", "some", "such",
    "than", "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "upon",
    "us", "very", "was", "way", "we", "were", "what", "when", "where", "which",
    "while", "who", "why", "will", "with", "would", "you", "your",
})


def _is_bilingual_script(script: str, _lang: str = "") -> bool:
    """Check that a learning section script contains actual English narration.

    Pure target-language scripts (e.g. entirely French or Arabic) are rejected.
    A valid bilingual script must have at least 3 English stop words in the
    first ~20 words of text.

    Returns True if the script passes the bilingual check.
    """
    first_20_words = script[:120].lower().split()[:20]
    eng_count = sum(
        1 for w in first_20_words
        if w.strip(".,!?;:()\"'-«»") in ENGLISH_STOP_WORDS
    )
    return eng_count >= 3


# TTS base URL — defaults to Argent custom TTS; override for ElevenLabs
# compatibility endpoint (e.g. VOICE_BASE_URL=https://api.elevenlabs.io)
VOICE_BASE_URL = (
    os.getenv("VOICE_BASE_URL", "https://txt2sph.audarai.com").rstrip("/")
)
# Whether to insert SSML `<break>` markers into the spoken script.
# Default is OFF (Argent does not support SSML). Set to "true"/"yes"/"on"/"1"
# when using a TTS engine that supports SSML break tags.
ENABLE_SSML_BREAK_MARKERS = (
    os.getenv("ENABLE_SSML_BREAK_MARKERS", "false").strip().lower()
    not in {"0", "false", "no", "off"}
)

# TTS voice config
VOICE_MODEL_ID = "eleven_multilingual_v2"
EN_VOICE_ID = "Isabella"
VOICE_SETTINGS = {
    "stability": 0.3,
    "similarity_boost": 0.75,
    "style": 0.4,
    "use_speaker_boost": True,
}
VOICE_SPEED_EN = 1.2
VOICE_SPEED_FR = 0.9
VOICE_SPEED_AR = 0.95
FR_VOICE_ID_DEFAULT = "84fe56fcc955"  # Jean - French male, Paris
AR_VOICE_ID_DEFAULT = "Tariq"  # Tariq - Arabic male, Modern Standard Arabic

# ---------------------------------------------------------------------------
# TTS Circuit Breaker
# ---------------------------------------------------------------------------

class TTSCircuitBreaker:
    """Circuit breaker for TTS API to prevent thundering herd during outages.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service may be down, reject requests immediately
    - HALF_OPEN: Testing recovery, allow one probe request

    After failure_threshold consecutive failures, circuit opens.
    After timeout_seconds, circuit transitions to half-open.
    A successful request in half-open closes the circuit.
    """

    def __init__(self, failure_threshold: int = 10, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Record a TTS API failure."""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            log.warning(
                "[TTS_CIRCUIT_BREAKER] Circuit OPEN after %d failures",
                self.failure_count
            )

    def record_success(self):
        """Record a successful TTS API call."""
        self.failure_count = 0
        self.state = "CLOSED"

    def should_attempt(self) -> bool:
        """Check if a TTS request should be attempted."""
        import time
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.timeout_seconds:
                self.state = "HALF_OPEN"
                log.info("[TTS_CIRCUIT_BREAKER] Circuit HALF_OPEN, probing...")
                return True
            return False
        # HALF_OPEN: allow one probe request
        return True

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold,
        }

# Global circuit breaker instance (shared across threads in a worker)
_tts_circuit_breaker = TTSCircuitBreaker(failure_threshold=10, timeout_seconds=60)


# ---------------------------------------------------------------------------
# Anthropic/LLM Circuit Breaker
# ---------------------------------------------------------------------------

class LLMApiCircuitBreaker:
    """Circuit breaker for Anthropic/LLM API to prevent cascade failures.

    Mirrors TTSCircuitBreaker but tuned for LLM API characteristics:
    - Lower failure threshold (5 vs 10) since LLM calls are more expensive
    - Longer timeout (120s vs 60s) since LLM outages tend to last longer
    """

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 120):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Record an LLM API failure."""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            log.warning(
                "[LLM_CIRCUIT_BREAKER] Circuit OPEN after %d failures",
                self.failure_count
            )

    def record_success(self):
        """Record a successful LLM API call."""
        self.failure_count = 0
        self.state = "CLOSED"

    def should_attempt(self) -> bool:
        """Check if an LLM request should be attempted."""
        import time
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.timeout_seconds:
                self.state = "HALF_OPEN"
                log.info("[LLM_CIRCUIT_BREAKER] Circuit HALF_OPEN, probing...")
                return True
            return False
        # HALF_OPEN: allow one probe request
        return True

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold,
        }

# Global LLM circuit breaker
_llm_circuit_breaker = LLMApiCircuitBreaker(failure_threshold=5, timeout_seconds=120)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("generate_audio")
DUBAI_TZ = ZoneInfo("Asia/Dubai")

# ---------------------------------------------------------------------------
# Anthropic Client Pooling
# ---------------------------------------------------------------------------

_anthropic_client = None


def _get_anthropic_client():
    """Get or create a singleton Anthropic client.

    Reuses the same client instance across function calls to avoid
    repeated TCP handshakes and SSL negotiations (~100-200ms saved per call).

    Thread-safe: Each Celery worker process has its own instance.
    """
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
        log.info("Anthropic client initialized (pooled)")
    return _anthropic_client

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """Load environment variables.

    Priority:
      1. project-root .env    (has ANTHROPIC_API_KEY, VOICE_API_KEY)
      2. frontend/.env.local  (has NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    Uses override=True so .env file values take precedence over
    empty shell env vars (e.g. ANTHROPIC_API_KEY="" in the environment).
    """
    root_env = PROJECT_ROOT / ".env"
    frontend_env = FRONTEND_DIR / ".env.local"

    if root_env.exists():
        load_dotenv(root_env, override=True)
        log.info("Loaded env from %s", root_env)
    if frontend_env.exists():
        load_dotenv(frontend_env, override=False)
        log.info("Loaded env from %s", frontend_env)


def _today_in_dubai_iso() -> str:
    """Return today's date in Asia/Dubai to match pipeline output naming."""
    return datetime.now(DUBAI_TZ).date().isoformat()


def _require_python_310_plus() -> None:
    """Fail fast when the runtime is too old for the type syntax used below."""
    if sys.version_info < (3, 10):
        log.error("generate_audio.py requires Python 3.10+.")
        sys.exit(1)


def _get_site_url() -> str:
    """Resolve the frontend base URL after dotenv loading."""
    return (
        os.getenv("SITE_URL")
        or os.getenv("NEXT_PUBLIC_SITE_URL")
        or "https://mbzuai-intel.com"
    ).rstrip("/")


def _get_voice_config() -> dict[str, dict[str, str]]:
    """Resolve per-language voice config after dotenv loading."""
    return {
        "en": {
            "voice_id": os.getenv("ENGLISH_VOICE_ID", EN_VOICE_ID),
            "prompt_file": "podcast_script_prompt.md",
        },
        "fr": {
            "voice_id": os.getenv("FRENCH_VOICE_ID", FR_VOICE_ID_DEFAULT),
            "prompt_file": "podcast_script_prompt_fr.md",
        },
        "ar": {
            "voice_id": os.getenv("ARABIC_VOICE_ID", AR_VOICE_ID_DEFAULT),
            "prompt_file": "podcast_script_prompt_ar.md",
        },
    }


def _audio_brief_enabled() -> bool:
    """Return whether audio brief generation is enabled.

    Default is ON unless explicitly disabled via ENABLE_AUDIO_BRIEF.
    """
    raw = (os.getenv("ENABLE_AUDIO_BRIEF") or "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off"}


def _french_audio_enabled() -> bool:
    """Return whether French audio generation is enabled (default: False)."""
    raw = (os.getenv("ENABLE_FRENCH_AUDIO") or "").strip().lower()
    if not raw:
        return False
    return raw not in {"0", "false", "no", "off"}


def _arabic_audio_enabled() -> bool:
    """Return whether Arabic audio generation is enabled (default: False)."""
    raw = (os.getenv("ENABLE_ARABIC_AUDIO") or "").strip().lower()
    if not raw:
        return False
    return raw not in {"0", "false", "no", "off"}


def _learning_content_enabled() -> bool:
    """Return whether language learning content generation is enabled (default: True)."""
    raw = (os.getenv("ENABLE_LEARNING_CONTENT") or "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off"}


def _get_supabase_client() -> Client:
    """Create and return a Supabase client using the service role key."""
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        log.error(
            "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. "
            "Ensure they are set in frontend/.env.local or project-root .env"
        )
        sys.exit(1)

    return create_client(url, key)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _extract_prompt_from_md(md_text: str) -> str:
    """Extract the prompt text from between ``` code fences in a markdown file.

    Same logic as backend/prompts/loader.py extract_prompt_from_md().
    """
    matches = re.findall(r"```\n(.*?)```", md_text, re.DOTALL)
    if matches:
        return max(matches, key=len).strip()
    return md_text.strip()


def _get_script_budget(lang: str) -> dict[str, int]:
    """Return the per-language script budget."""
    return LANGUAGE_SCRIPT_BUDGETS.get(lang, LANGUAGE_SCRIPT_BUDGETS["en"])


def _clean_outline_text(value: str | None, *, max_chars: int | None = None) -> str:
    """Normalize brief text for outline and prompt injection."""
    text = str(value or "")
    text = re.sub(r"\[Source:[^\]]+\]", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" \n\t-")

    if max_chars is not None and len(text) > max_chars:
        shortened = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:")
        text = (shortened or text[:max_chars].rstrip(",;:")) + "..."

    return text.strip()


def _first_outline_sentence(value: str | None, *, max_chars: int = 240) -> str:
    """Return a single clean sentence for the shared outline."""
    cleaned = _clean_outline_text(value)
    if not cleaned:
        return ""

    match = re.search(r"[.!?…](?:[\"'”»)]*)?(?=\s|$)", cleaned)
    if match:
        cleaned = cleaned[:match.end()].strip()

    return _clean_outline_text(cleaned, max_chars=max_chars)


def _build_shared_outline(brief_json: dict) -> tuple[str, list[dict[str, str | int]]]:
    """Build a shared editorial outline used by both language versions."""
    brief_date = str(brief_json.get("brief_metadata", {}).get("date", "unknown"))
    outline_items: list[dict[str, str | int]] = []

    for item in brief_json.get("items", []):
        if item.get("is_placeholder"):
            continue

        number = len(outline_items) + 1
        section = _clean_outline_text(item.get("section") or "General", max_chars=80)
        headline = _clean_outline_text(item.get("headline") or "Untitled item", max_chars=180)
        core_fact = _first_outline_sentence(
            item.get("main_bullet") or item.get("context"),
            max_chars=260,
        )
        implication = _first_outline_sentence(
            item.get("implication") or item.get("context"),
            max_chars=220,
        )
        label = "LEAD ITEM" if number == 1 else "SECOND LEAD" if number == 2 else "ITEM"

        outline_items.append(
            {
                "number": number,
                "label": label,
                "section": section,
                "headline": headline,
                "core_fact": core_fact,
                "implication": implication,
            }
        )

    lines = [
        "SHARED COVERAGE OUTLINE",
        f"Date: {brief_date}",
        "Use this outline as the mandatory coverage spine in every language version.",
        "The first two entries are the leads. The remaining entries may be grouped more tightly, but none may be omitted.",
    ]

    for item in outline_items:
        segments = [
            f"{item['label']} {item['number']}",
            f"Section: {item['section']}",
            f"Headline: {item['headline']}",
        ]
        if item["core_fact"]:
            segments.append(f"Core fact: {item['core_fact']}")
        if item["implication"]:
            segments.append(f"Why it matters: {item['implication']}")
        lines.append(" | ".join(str(segment) for segment in segments if segment))

    return "\n".join(lines), outline_items


# ---------------------------------------------------------------------------
# Brief JSON sanitisation for TTS narration — strips AI-generated speculative
# fields that cause Claude to fabricate/hallucinate details in the spoken script.
# ---------------------------------------------------------------------------

# Fields we keep — all factual, from direct source reporting
_TTS_KEEP_FIELDS = frozenset({
    "id", "rank", "headline", "section", "category",
    "source_url", "source_name", "source_domain", "source_origin",
    "main_bullet", "key_bullets",
    "entities", "primary_entity", "primary_subject",
    "primary_entity_category", "primary_subject_type",
    "depth", "cluster", "composite_score", "significance_level",
    "is_placeholder",  # needed so the model knows which items to skip
    "continuity", "additional_sources", "exhibits",
    "badge_text", "badge_subject", "badge_subject_type", "badge_subject_category",
})

# Fields we strip — AI-generated analysis/synthesis prone to hallucination
_TTS_STRIP_FIELDS = {"analysis", "implication", "context"}

# Irrelevant to script generation
_TTS_STRIP_FIELDS.update({"audio_url", "learning_fr", "learning_ar"})


def _sanitize_brief_json_for_tts(brief_json: dict) -> dict:
    """Return a clean copy of brief_json with hallucination-prone fields removed."""
    # Shallow copy metadata and all non-items keys
    clean: dict = {
        k: v for k, v in brief_json.items() if k != "items"
    }
    clean_items: list[dict] = []
    for item in brief_json.get("items", []):
        sanitised: dict = {}
        for key, value in item.items():
            if key not in _TTS_STRIP_FIELDS:
                sanitised[key] = value
        clean_items.append(sanitised)
    clean["items"] = clean_items
    return clean


# ---------------------------------------------------------------------------
# Podcast script prompt loading
# ---------------------------------------------------------------------------


def _load_podcast_prompt(brief_json: dict, shared_outline: str, lang: str = "en") -> str:
    """Load the podcast script prompt for the given language and inject outline + brief JSON."""
    voice_config = _get_voice_config()
    config = voice_config.get(lang, voice_config["en"])
    prompt_path = PROMPTS_DIR / config["prompt_file"]

    if not prompt_path.exists():
        log.error("Podcast script prompt not found at %s", prompt_path)
        sys.exit(1)

    raw_md = prompt_path.read_text(encoding="utf-8")
    prompt_text = _extract_prompt_from_md(raw_md)

    brief_date = brief_json.get("brief_metadata", {}).get("date", "unknown")
    prompt_text = prompt_text.replace(
        "{brief_json}",
        json.dumps(_sanitize_brief_json_for_tts(brief_json), indent=2, ensure_ascii=False),
    )
    prompt_text = prompt_text.replace("{shared_outline}", shared_outline)
    prompt_text = prompt_text.replace("{date}", brief_date)

    items = brief_json.get("items", [])
    checklist_lines: list[str] = []
    for item in items:
        if item.get("is_placeholder"):
            continue
        headline = str(item.get("headline") or "").strip()
        section = str(item.get("section") or "").strip()
        if headline:
            checklist_lines.append(f"{len(checklist_lines) + 1}. [{section}] {headline}")

    if checklist_lines:
        prompt_text += (
            "\n\nMANDATORY COVERAGE CHECKLIST:\n"
            "Every non-placeholder item below must appear at least once in the spoken script. "
            "Lower-priority items may be grouped into shorter lines, but none may be omitted.\n"
            + "\n".join(checklist_lines)
        )

    # When SSML break markers are disabled, scrub all break-tag instructions
    # from the prompt so the model does not emit `<break>` tags.
    if not ENABLE_SSML_BREAK_MARKERS:
        prompt_text = re.sub(
            r'\n?\d+\.\s*BREAK TAGS ARE GRADUATED.*?(?=\n\d+\. |\n\n(?!\s*-)|\Z)',
            '',
            prompt_text,
            flags=re.DOTALL,
        )
        prompt_text = re.sub(r'\n?\d+\.\s*Les pauses.*?(?=\n\d+\. |\n\n(?!\s*-)|\Z)', '', prompt_text, flags=re.DOTALL)
        prompt_text = re.sub(r'\n?\d+\.\s*Les balises `?<break[^`]*`?.*?(?=\n\d+\. |\n\n(?!\s*-)|\Z)', '', prompt_text, flags=re.DOTALL)
        prompt_text = re.sub(r'- Only markup allowed:.*', '', prompt_text)
        prompt_text = re.sub(r'<break\s+time="[^"]+"\s*/\s*>', '', prompt_text)
        prompt_text = re.sub(r'`<break[^`]*>`', '', prompt_text)
        prompt_text = re.sub(r'\n{3,}', '\n\n', prompt_text)

    return prompt_text


# ---------------------------------------------------------------------------
# Script generation (Claude Sonnet)
# ---------------------------------------------------------------------------

def _extract_json_object(text: str) -> dict | None:
    """Parse a JSON object even if the model wraps it in markdown fences or surrounding text."""
    stripped = text.strip()
    if not stripped:
        return None

    # Strategy 1: Strip fences at start/end of entire response
    cleaned = re.sub(r"^```(?:json)?\s*", "", stripped)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract content from markdown code fence anywhere in response
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", stripped, re.DOTALL)
    if fence_match:
        fenced_content = fence_match.group(1).strip()
        try:
            parsed = json.loads(fenced_content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # Try fixing trailing commas in fenced content
            fixed = re.sub(r",\s*([}\]])", r"\1", fenced_content)
            try:
                parsed = json.loads(fixed)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

    # Strategy 3: Find outermost JSON object using brace matching
    start_idx = stripped.find("{")
    if start_idx == -1:
        return None

    # Find matching closing brace by counting depth
    depth = 0
    in_string = False
    escape_next = False
    end_idx = -1
    for i in range(start_idx, len(stripped)):
        ch = stripped[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_idx = i
                break

    if end_idx == -1:
        return None

    candidate = stripped[start_idx:end_idx + 1]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        # Try fixing trailing commas
        fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            parsed = json.loads(fixed)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def _audit_script_coverage(
    shared_outline: str,
    script: str,
    *,
    lang: str,
    accept_parse_failure: bool = True,
    fallback_missing_numbers: list[int] | None = None,
) -> dict[str, object]:
    """Use Claude to check whether a script covers every outline item."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = _get_anthropic_client()
    prompt = f"""
Audit whether this executive audio briefing script covers every numbered item in the shared outline.

Rules:
- Treat paraphrase as covered.
- An outline item counts as covered if the script conveys its core fact and why-it-matters signal, even with different wording.
- Grouped coverage is acceptable.
- Only mark an item missing if it is clearly absent or reduced to a stray name-drop.
- Return JSON only in this shape:
  {{"complete": true, "missing_item_numbers": [], "notes": ""}}

SCRIPT LANGUAGE: {"French" if lang == "fr" else "English"}

OUTLINE:
{shared_outline}

SCRIPT:
<<<SCRIPT>>>
{script}
<<<END SCRIPT>>>
""".strip()

    parsed = None
    for attempt in range(2):
        request_prompt = prompt
        if attempt > 0:
            request_prompt += (
                "\n\nIMPORTANT: Return a single JSON object only. "
                "Do not add any prose before or after the JSON."
            )

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=SCRIPT_VALIDATION_MAX_TOKENS,
            messages=[{"role": "user", "content": request_prompt}],
        )

        text_blocks = [block.text for block in response.content if block.type == "text"]
        raw = "\n".join(text_blocks).strip()
        parsed = _extract_json_object(raw)
        if parsed is not None:
            break

    if parsed is None:
        if accept_parse_failure:
            log.error("Coverage audit returned unparseable JSON; accepting current script (items at risk: all).")
            return {"complete": True, "missing_item_numbers": [], "notes": "validator_parse_failed"}

        fallback = list(fallback_missing_numbers or [])
        log.warning(
            "Coverage audit returned unparseable JSON; failing closed with fallback missing items %s.",
            fallback,
        )
        return {
            "complete": False,
            "missing_item_numbers": fallback,
            "notes": "validator_parse_failed",
        }

    missing_numbers: list[int] = []
    for value in parsed.get("missing_item_numbers", []):
        try:
            missing_numbers.append(int(value))
        except (TypeError, ValueError):
            continue

    missing_numbers = sorted(set(number for number in missing_numbers if number > 0))
    complete = bool(parsed.get("complete")) and not missing_numbers

    return {
        "complete": complete,
        "missing_item_numbers": missing_numbers,
        "notes": str(parsed.get("notes") or ""),
    }


def _build_coverage_repair_instruction(
    missing_numbers: list[int],
    outline_items: list[dict[str, str | int]],
    *,
    lang: str,
) -> str:
    """Build a targeted retry instruction for outline items the model skipped."""
    if not missing_numbers:
        return ""

    missing_lookup = {int(item["number"]): item for item in outline_items}
    lines: list[str] = []
    for number in missing_numbers:
        item = missing_lookup.get(number)
        if not item:
            continue
        summary = f"Item {number}: [{item['section']}] {item['headline']}"
        if item["implication"]:
            summary += f" | Why it matters: {item['implication']}"
        lines.append(f"- {summary}")

    if not lines:
        return ""

    if lang == "fr":
        intro = (
            "CORRECTION DE COUVERTURE OBLIGATOIRE : votre tentative precedente a laisse tomber "
            "les elements ci-dessous. Regenerez l'integralite du script en francais natif, "
            "couvrez clairement chaque element manquant et ne redigez pas comme une traduction de l'anglais."
        )
    else:
        intro = (
            "MANDATORY COVERAGE REPAIR: the previous attempt clearly missed the outline items below. "
            "Regenerate the full script and make sure each missing item is covered naturally."
        )

    return intro + "\n" + "\n".join(lines)


def _generate_script(
    brief_json: dict,
    shared_outline: str,
    outline_items: list[dict[str, str | int]],
    lang: str = "en",
) -> str:
    """Call Claude Sonnet to generate the podcast script.

    Returns the plain text script.
    """
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = _get_anthropic_client()
    prompt_text = _load_podcast_prompt(brief_json, shared_outline, lang=lang)

    lang_label = "French" if lang == "fr" else "English"
    log.info("Calling Claude Sonnet for %s script generation (%d chars prompt)...", lang_label, len(prompt_text))

    retry_instruction = {
        "en": (
            "IMPORTANT: The previous attempt needs revision. "
            "Regenerate the full script, stay within the stated length budget, "
            "and end with one short complete closing sentence."
        ),
        "fr": (
            "IMPORTANT : la tentative precedente doit etre corrigee. "
            "Regenerez l'integralite du script, respectez l'objectif de longueur indique, "
            "et terminez par une courte phrase de cloture complete."
        ),
    }

    last_script = ""
    last_stop_reason = None
    last_missing_numbers: list[int] = []
    expected_numbers = [int(item["number"]) for item in outline_items]

    for attempt in range(SCRIPT_GENERATION_MAX_ATTEMPTS):
        request_prompt = prompt_text
        max_tokens = SCRIPT_MAX_TOKENS

        if attempt > 0:
            repair_notes: list[str] = [retry_instruction.get(lang, retry_instruction["en"])]
            repair_instruction = _build_coverage_repair_instruction(
                last_missing_numbers,
                outline_items,
                lang=lang,
            )
            if repair_instruction:
                repair_notes.append(repair_instruction)
            request_prompt = f"{prompt_text}\n\n" + "\n\n".join(repair_notes)
            max_tokens = int(SCRIPT_MAX_TOKENS * 1.25)

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": request_prompt}],
        )

        text_blocks = [block.text for block in response.content if block.type == "text"]
        script = "\n".join(text_blocks).strip()
        stop_reason = getattr(response, "stop_reason", None)
        has_clean_ending = _script_has_clean_ending(script)

        last_script = script
        last_stop_reason = stop_reason

        word_count = len(script.split())
        log.info(
            "%s script generated: %d words, %d characters (stop_reason=%s, complete=%s, attempt=%d)",
            lang_label,
            word_count,
            len(script),
            stop_reason,
            has_clean_ending,
            attempt + 1,
        )

        if word_count < 200:
            log.warning("%s script is unusually short (%d words). Review output.", lang_label, word_count)

        missing_numbers: list[int] = []
        if stop_reason != "max_tokens" and has_clean_ending and outline_items:
            audit = _audit_script_coverage(
                shared_outline,
                script,
                lang=lang,
                accept_parse_failure=False,
                fallback_missing_numbers=expected_numbers,
            )
            missing_numbers = list(audit.get("missing_item_numbers", []))
            if missing_numbers:
                log.warning(
                    "%s script missed outline items %s on attempt %d",
                    lang_label,
                    missing_numbers,
                    attempt + 1,
                )

        last_missing_numbers = missing_numbers

        if stop_reason != "max_tokens" and has_clean_ending and not missing_numbers:
            return script

        if attempt < SCRIPT_GENERATION_MAX_ATTEMPTS - 1:
            log.warning(
                "%s script needs retry (stop_reason=%s, complete=%s, missing_items=%s).",
                lang_label,
                stop_reason,
                has_clean_ending,
                missing_numbers,
            )

    repaired = _trim_script_to_complete_sentences(last_script)
    if repaired != last_script:
        log.warning(
            "%s script still ended abruptly after retry (stop_reason=%s). Trimmed to the last complete sentence.",
            lang_label,
            last_stop_reason,
        )
    if last_missing_numbers:
        log.error(
            "%s script still appears to miss outline items after retries: %s",
            lang_label,
            last_missing_numbers,
        )
    return repaired


def _script_has_clean_ending(script: str) -> bool:
    """Return whether a script ends with terminal punctuation."""
    trimmed = re.sub(r"\s*" + BREAK_TAG_PATTERN + r"\s*$", "", script).strip()
    if not trimmed:
        return False
    return trimmed[-1] in {".", "!", "?", "…", "\"", "'", "»", "”"}


def _trim_script_to_complete_sentences(
    script: str,
    *,
    max_words: int | None = None,
    max_chars: int | None = None,
) -> str:
    """Trim to the last complete sentence so stored transcripts never end abruptly."""
    trimmed = re.sub(r"\n{3,}", "\n\n", script).strip()
    if not trimmed:
        return trimmed

    if max_chars is not None and len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars].rstrip()

    sentence_endings = list(
        re.finditer(r"[.!?…](?:[\"'”»)]*)?(?=\s|$)", trimmed)
    )
    if sentence_endings:
        trimmed = trimmed[:sentence_endings[-1].end()].rstrip()

    if max_words is not None and len(trimmed.split()) > max_words:
        shortened = " ".join(trimmed.split()[:max_words]).strip()
        sentence_endings = list(
            re.finditer(r"[.!?…](?:[\"'”»)]*)?(?=\s|$)", shortened)
        )
        if sentence_endings:
            shortened = shortened[:sentence_endings[-1].end()].rstrip()
        trimmed = shortened

    return trimmed.strip()


def _split_script_sections(script: str) -> list[str]:
    """Split a prepared script into section payloads around audio break markers."""
    return [
        part.strip()
        for part in re.split(r"\n\s*" + BREAK_TAG_PATTERN + r"\s*\n?", script)
        if part.strip()
    ]


def _compress_script(
    script: str,
    *,
    lang: str = "en",
    enforce_complete_ending: bool = False,
    coverage_repair_instruction: str = "",
) -> str:
    """Condense an overlong script to the language-specific audio budget."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    budget = _get_script_budget(lang)
    client = _get_anthropic_client()
    prompt = f"""
Condense the following spoken executive briefing script.

Requirements:
- Preserve the script language exactly as written.
- Keep the opening, the top two stories, grouped section coverage, and a short closing.
- Preserve the most decision-relevant facts and implications.
- Remove repetition, examples, and secondary detail before cutting essential facts.
- Do not delete entire topics or items. Every distinct topic already present in the script must still appear at least once.
- Output plain spoken text only.
- Do not use rhetorical questions.
- Keep or restore a few graduated break markers: `<break time="0.5s" />` between items within the same theme, `<break time="1.0s" />` between major topic shifts. Aim for 5–8 total, never two in a row.
- End with a complete final sentence. Never stop mid-sentence.
- Target {budget["target_words"]} words.
- Hard maximum {budget["hard_max_words"]} words.
- Hard maximum {budget["hard_max_chars"]} characters.

Script:
{script}
""".strip()

    if enforce_complete_ending:
        prompt += (
            "\n\nIMPORTANT: Your previous compression ended abruptly. "
            "Regenerate the compressed version and make sure the final line is a complete closing sentence."
        )
    if coverage_repair_instruction:
        prompt += "\n\n" + coverage_repair_instruction

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1400,
        messages=[{"role": "user", "content": prompt}],
    )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_blocks).strip()


def _enforce_script_budget(
    script: str,
    *,
    lang: str = "en",
    coverage_repair_instruction: str = "",
) -> str:
    """Shrink overlong scripts before sending to TTS."""
    normalized = re.sub(r"\n{3,}", "\n\n", script).strip()
    word_count = len(normalized.split())
    char_count = len(normalized)
    budget = _get_script_budget(lang)

    if budget["hard_max_words"] == 0:
        return normalized  # Budget enforcement disabled for this language
    if word_count <= budget["hard_max_words"] and char_count <= budget["hard_max_chars"]:
        return normalized

    log.warning(
        "%s script exceeds budget (%d words, %d chars). Compressing to target...",
        "French" if lang == "fr" else "English",
        word_count,
        char_count,
    )
    compressed = _compress_script(
        normalized,
        lang=lang,
        coverage_repair_instruction=coverage_repair_instruction,
    )
    compressed = re.sub(r"\n{3,}", "\n\n", compressed).strip()

    compressed_words = len(compressed.split())
    compressed_chars = len(compressed)
    log.info(
        "Compressed script: %d words, %d characters",
        compressed_words,
        compressed_chars,
    )

    if not _script_has_clean_ending(compressed):
        log.warning(
            "Compressed script ended abruptly. Retrying compression with explicit closing instruction."
        )
        compressed = _compress_script(
            normalized,
            lang=lang,
            enforce_complete_ending=True,
            coverage_repair_instruction=coverage_repair_instruction,
        )
        compressed = re.sub(r"\n{3,}", "\n\n", compressed).strip()
        log.info(
            "Recompressed script: %d words, %d characters (complete=%s)",
            len(compressed.split()),
            len(compressed),
            _script_has_clean_ending(compressed),
        )

    if (
        len(compressed.split()) > budget["hard_max_words"]
        or len(compressed) > budget["hard_max_chars"]
        or not _script_has_clean_ending(compressed)
    ):
        compressed = _trim_script_to_complete_sentences(
            compressed,
            max_words=budget["hard_max_words"],
            max_chars=budget["hard_max_chars"],
        )
        log.warning(
            "Compressed script required sentence-boundary repair. Final size: %d words, %d characters.",
            len(compressed.split()),
            len(compressed),
        )

    return compressed


def _apply_break_markers(script: str) -> str:
    """Normalize break-tag placement and spacing for TTS pacing.

    The podcast prompt tells the model to place graduated
    `<break time="0.5s" />` (within theme) and `<break time="1.0s" />`
    (between major sections) tags. This post-processor trusts the model's
    durations and placement. It only:

    1. Ensures each break tag sits on its own line, bracketed by blank lines,
       so it renders as a discrete pause rather than an inline token.
    2. Collapses any accidental run of consecutive break tags to a single
       tag, keeping the longest duration. This fixes the stacked-tag bug
       where a short model-emitted tag landed between two post-processor-
       inserted tags, confusing the TTS engine into producing vocal artifacts.
    """
    # Place every break tag on its own line, blank-line-padded.
    normalized = re.sub(
        r"\s*(" + BREAK_TAG_PATTERN + r")\s*",
        r"\n\n\1\n\n",
        script,
    )

    # Collapse consecutive break tags to the longest-duration one.
    def _collapse_breaks(match: re.Match) -> str:
        tags = re.findall(BREAK_TAG_PATTERN, match.group(0))
        if not tags:
            return match.group(0)

        def _duration(tag: str) -> float:
            m = re.search(r'time="([0-9.]+)s"', tag)
            return float(m.group(1)) if m else 0.0

        longest = max(tags, key=_duration)
        return f"\n\n{longest}\n\n"

    normalized = re.sub(
        r"(?:\s*" + BREAK_TAG_PATTERN + r"\s*){2,}",
        _collapse_breaks,
        normalized,
    )

    return re.sub(r"\n{3,}", "\n\n", normalized).strip()


# ---------------------------------------------------------------------------
# Item-level helpers
# ---------------------------------------------------------------------------


def _build_item_script(item: dict) -> str:
    """Build a short spoken script for a single brief item from its structured data.

    Uses a template-based composition (headline + main_bullet + context + implication).
    No Claude call — works from pipeline item fields directly.
    Returns a concise spoken paragraph (~150-400 chars).
    """
    headline = (item.get("headline") or "").strip().rstrip(".,;:!?")
    main_bullet = (item.get("main_bullet") or "").strip().rstrip(".,;:!?")
    context = (item.get("context") or "").strip().rstrip(".,;:!?")
    implication = (item.get("implication") or "").strip().rstrip(".,;:!?")

    parts: list[str] = []
    if headline:
        text = headline[0].upper() + headline[1:] if headline else headline
        parts.append(text + ".")
    if main_bullet:
        parts.append(main_bullet + ".")
    if context:
        parts.append(context + ".")
    if implication:
        parts.append(implication + ".")

    script = " ".join(parts)
    script = re.sub(r"\s+", " ", script).strip()
    return script


# ---------------------------------------------------------------------------
# Audio generation (TTS)
# ---------------------------------------------------------------------------

VOICE_MAX_CHARS = 9500  # Stay under 10,000 char API limit with margin (ElevenLabs)
VOICE_MAX_CHARS_ARGENT = 4800  # Stay under 5,000 char API limit with margin (Argent native API)


def _split_script_into_chunks(script: str, max_chars: int = VOICE_MAX_CHARS) -> list[str]:
    """Split script into chunks that fit within the TTS character limit.

    Splits on paragraph boundaries (double newlines) to preserve natural pauses.
    Falls back to sentence boundaries if a single paragraph exceeds the limit.
    """
    paragraphs = script.split("\n\n")
    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        candidate = (current_chunk + "\n\n" + para).strip() if current_chunk else para.strip()

        if len(candidate) <= max_chars:
            current_chunk = candidate
        else:
            # Current chunk is full — save it and start a new one
            if current_chunk:
                chunks.append(current_chunk)

            # If this single paragraph exceeds the limit, split by sentences
            if len(para.strip()) > max_chars:
                sentences = re.split(r"(?<=[.!?])\s+", para.strip())
                sub_chunk = ""
                for sentence in sentences:
                    sub_candidate = (sub_chunk + " " + sentence).strip() if sub_chunk else sentence.strip()
                    if len(sub_candidate) <= max_chars:
                        sub_chunk = sub_candidate
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = sentence.strip()
                current_chunk = sub_chunk
            else:
                current_chunk = para.strip()

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _generate_audio(script: str, voice_id: str | None = None, lang: str = "en") -> bytes:
    """Send script to TTS API, return MP3 bytes.

    Supports both ElevenLabs API format and the Argent TTS native API
    (auto-detected from VOICE_BASE_URL containing "txt2sph.audarai.com").

    If the script exceeds the API character limit, it is split into
    chunks at paragraph boundaries and the resulting audio segments
    are concatenated.

    Optimizations:
    - httpx connection pooling via persistent Client
    - Concurrent chunk processing with ThreadPoolExecutor (ElevenLabs only)
    - Reduced timeout (60s vs 180s) for faster fail-over
    - Circuit breaker to prevent thundering herd during outages
    """
    import base64
    import httpx
    import json as _json
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Check circuit breaker before attempting
    if not _tts_circuit_breaker.should_attempt():
        status = _tts_circuit_breaker.get_status()
        raise RuntimeError(
            f"TTS circuit breaker OPEN ({status['failure_count']}/{status['threshold']} failures). "
            "Service may be experiencing extended outage."
        )

    api_key = os.getenv("VOICE_API_KEY")
    using_argent = "txt2sph.audarai.com" in VOICE_BASE_URL

    # Argent native API doesn't require authentication; only ElevenLabs needs an API key
    if not api_key and not using_argent:
        log.error("VOICE_API_KEY not set")
        raise RuntimeError("VOICE_API_KEY not set")

    if voice_id is None:
        voice_id = _get_voice_config()["en"]["voice_id"]

    chunk_limit = VOICE_MAX_CHARS_ARGENT if using_argent else VOICE_MAX_CHARS
    chunks = _split_script_into_chunks(script, max_chars=chunk_limit)
    log.info(
        "Script is %d characters — split into %d chunk(s) (provider=%s)",
        len(script), len(chunks),
        "Argent" if using_argent else "ElevenLabs",
    )

    # Build request specs for each chunk
    request_specs = []
    for i, chunk in enumerate(chunks):
        if using_argent:
            url = f"{VOICE_BASE_URL}/v1/synthesize"
            payload = {"text": chunk, "speaker_id": voice_id, "lang": lang}
            headers = {"Content-Type": "application/json"}
        else:
            url = f"{VOICE_BASE_URL}/v1/text-to-speech/{voice_id}"
            payload = {
                "text": chunk,
                "model_id": VOICE_MODEL_ID,
                "voice_settings": VOICE_SETTINGS,
            }
            if lang == "en":
                payload["speed"] = VOICE_SPEED_EN
            elif lang == "fr":
                payload["speed"] = VOICE_SPEED_FR
            elif lang == "ar":
                payload["speed"] = VOICE_SPEED_AR
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            }
        request_specs.append((i, url, payload, headers))

    # Use connection-pooled httpx Client
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=60.0)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)

    def _synthesize_chunk(spec: tuple) -> tuple:
        """Synthesize a single chunk with retry logic and circuit breaker."""
        idx, url, payload, headers = spec
        client = httpx.Client(timeout=timeout, limits=limits)
        try:
            # Argent requires sequential calls with cooldown
            if using_argent:
                _time.sleep(3 * idx)  # stagger: 0s, 3s, 6s, etc.

            log.info("Calling TTS chunk %d/%d (%d chars)...", idx + 1, len(chunks), len(payload.get("text", "")))

            # Retry up to 3 times for transient errors
            response = None
            for attempt in range(3):
                response = client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    break
                if response.status_code in (404, 429, 502, 503, 504) and attempt < 2:
                    log.warning("TTS transient error %d (attempt %d/3), retrying in %ds...",
                                response.status_code, attempt + 1, (attempt + 1) * 3)
                    _time.sleep((attempt + 1) * 3)
                    continue
                break

            if response is None or response.status_code != 200:
                error_text = response.text[:500] if response else "No response"
                log.error("TTS API error %d: %s", response.status_code if response else 0, error_text)
                # Record failure in circuit breaker
                _tts_circuit_breaker.record_failure()
                if response:
                    response.raise_for_status()
                raise RuntimeError("TTS API failed")

            # Record success in circuit breaker
            _tts_circuit_breaker.record_success()

            if using_argent:
                result = _json.loads(response.text)
                audio_b64 = result.get("audio", "")
                if not audio_b64:
                    log.error("No audio in TTS response")
                    raise RuntimeError("Empty audio response from TTS API")
                chunk_audio = base64.b64decode(audio_b64)
                log.info("Chunk %d/%d: %.0f KB (Opus, %.1fs)",
                         idx + 1, len(chunks),
                         len(chunk_audio) / 1024,
                         result.get("duration", 0))
            else:
                chunk_audio = response.content
                log.info("Chunk %d/%d: %.0f KB", idx + 1, len(chunks), len(chunk_audio) / 1024)

            return (idx, chunk_audio)
        except Exception:
            # Record failure for any exception (network error, timeout, etc.)
            _tts_circuit_breaker.record_failure()
            raise
        finally:
            client.close()

    # Execute chunks: sequentially for Argent (server cooldown), concurrently for ElevenLabs
    all_audio: list[tuple[int, bytes]] = []
    if using_argent:
        # Sequential: Argent server needs cooldown between calls
        for spec in request_specs:
            all_audio.append(_synthesize_chunk(spec))
    else:
        # Concurrent: ElevenLabs can handle parallel requests
        with ThreadPoolExecutor(max_workers=min(len(chunks), 5)) as executor:
            futures = {executor.submit(_synthesize_chunk, spec): spec[0] for spec in request_specs}
            for future in as_completed(futures):
                all_audio.append(future.result())

    # Sort by original chunk index to maintain order
    all_audio.sort(key=lambda x: x[0])
    audio_segments = [audio for _, audio in all_audio]

    # Merge chunks into a single MP3
    if len(audio_segments) == 1 and not using_argent:
        # Single chunk from ElevenLabs — already MP3
        audio_bytes = audio_segments[0]
    else:
        from io import BytesIO
        from pydub import AudioSegment

        # Decode all segments
        segments = []
        for i, raw in enumerate(audio_segments):
            buf = BytesIO(raw)
            if using_argent:
                # Argent returns Ogg Opus audio — let ffmpeg auto-detect format
                segment = AudioSegment.from_file(buf)
            else:
                segment = AudioSegment.from_mp3(buf)
            segments.append(segment)
            log.info("Decoded chunk %d/%d (%.1fs, %.1f dBFS)",
                     i + 1, len(audio_segments),
                     len(segment) / 1000, segment.dBFS)

        # Normalize loudness across all segments to -20 dBFS (standard for speech)
        target_loudness = -20.0
        normalized_segments = []
        for i, segment in enumerate(segments):
            current_loudness = segment.dBFS
            # Skip normalization for silence (< -60 dBFS)
            if current_loudness > -60:
                gain_delta = target_loudness - current_loudness
                # Limit gain adjustment to +/- 6 dB to prevent distortion
                gain_delta = max(-6.0, min(6.0, gain_delta))
                normalized = segment.apply_gain(gain_delta)
                normalized_segments.append(normalized)
                if abs(gain_delta) > 0.5:
                    log.info("Normalized chunk %d: %.1f dB %s",
                             i + 1, abs(gain_delta),
                             "boost" if gain_delta > 0 else "cut")
            else:
                normalized_segments.append(segment)

        # Concatenate normalized segments
        combined = AudioSegment.empty()
        for i, segment in enumerate(normalized_segments):
            combined += segment
            log.info("Merged chunk %d/%d (%.1fs)", i + 1, len(normalized_segments), len(segment) / 1000)

        # Apply final limiter to prevent clipping (peak at -1 dBFS)
        peak = combined.max_dBFS
        if peak > -1.0:
            combined = combined.apply_gain(-1.0 - peak)
            log.info("Applied final limiter: %.1f dB gain", -1.0 - peak)

        buf = BytesIO()
        combined.export(buf, format="mp3", bitrate="128k")
        audio_bytes = buf.getvalue()
        log.info("Total merged duration: %.1fs (normalized to %.1f dBFS)",
                 len(combined) / 1000, combined.dBFS)

    size_mb = len(audio_bytes) / (1024 * 1024)
    log.info("Audio generated: %.1f MB total", size_mb)

    return audio_bytes


# ---------------------------------------------------------------------------
# Supabase Storage upload
# ---------------------------------------------------------------------------

def _upload_to_supabase(sb: Client, audio_bytes: bytes, target_date: str, lang: str = "en") -> str:
    """Upload MP3 to Supabase Storage, return public URL.

    Constructs the URL directly instead of calling get_public_url() to save
    a network round-trip per upload (~50-100ms saved).
    """
    file_path = f"{target_date}/briefing_{lang}.mp3"

    log.info("Uploading to audio-briefs/%s...", file_path)
    sb.storage.from_("audio-briefs").upload(
        file_path,
        audio_bytes,
        file_options={"content-type": "audio/mpeg", "upsert": "true"},
    )

    # Construct URL directly: Supabase public URLs are deterministic
    base_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/")
    public_url = f"{base_url}/storage/v1/object/public/audio-briefs/{file_path}"
    log.info("Uploaded successfully: %s", public_url)
    return public_url


def _upload_item_audio(sb: Client, audio_bytes: bytes, target_date: str, item_id: str) -> str:
    """Upload a single item's MP3 to Supabase Storage, return public URL.

    Path: {target_date}/items/{item_id}.mp3
    Constructs URL directly to avoid get_public_url() network call.
    """
    file_path = f"{target_date}/items/{item_id}.mp3"

    log.info("Uploading item audio to audio-briefs/%s...", file_path)
    sb.storage.from_("audio-briefs").upload(
        file_path,
        audio_bytes,
        file_options={"content-type": "audio/mpeg", "upsert": "true"},
    )

    # Construct URL directly
    base_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/")
    public_url = f"{base_url}/storage/v1/object/public/audio-briefs/{file_path}"
    log.info("Item audio uploaded: %s", public_url)
    return public_url


def _revalidate_frontend(target_date: str) -> None:
    """Trigger on-demand ISR revalidation so the cached page refreshes immediately.

    Calls POST /api/revalidate on the frontend for both /brief/today and
    /brief/<date> so visitors see the audio player without waiting for
    the hourly ISR cycle.
    """
    import httpx

    secret = os.getenv("REVALIDATION_SECRET")
    if not secret:
        log.warning("REVALIDATION_SECRET not set — skipping frontend cache revalidation")
        return

    headers = {"x-revalidate-secret": secret, "Content-Type": "application/json"}
    paths = ["/brief/today", f"/brief/{target_date}"]
    site_url = _get_site_url()

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            for path in paths:
                try:
                    resp = client.post(
                        f"{site_url}/api/revalidate",
                        json={"path": path},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        log.info("Revalidated %s via %s", path, str(resp.request.url))
                    else:
                        log.warning(
                            "Revalidation failed for %s: %d %s",
                            path,
                            resp.status_code,
                            resp.text[:200],
                        )
                except Exception as exc:
                    log.warning("Revalidation request failed for %s: %s", path, exc)
    except Exception as exc:
        log.warning("Failed to initialize revalidation client for %s: %s", site_url, exc)


# ---------------------------------------------------------------------------
# Database update
# ---------------------------------------------------------------------------

def _update_audio_status(sb: Client, target_date: str, status: str) -> None:
    """Update audio_status column for progress tracking."""
    try:
        sb.table("briefs").update({"audio_status": status}).eq(
            "brief_date", target_date
        ).execute()
        log.info("Audio status for %s: %s", target_date, status)
    except Exception as exc:
        log.warning("Failed to update audio_status for %s: %s", target_date, exc)


def _update_briefs_table(
    sb: Client,
    target_date: str,
    audio_url: str | None,
    script: str,
    audio_url_fr: str | None = None,
    script_fr: str | None = None,
) -> None:
    """Update the briefs row with audio data for one or both languages.

    Gracefully handles missing columns in the production schema (e.g.
    audio_generated_at, French audio columns). Writes what it can and
    logs warnings for columns that don't exist.
    """
    update_data: dict = {
        "audio_script": script,
        "audio_status": "ready",
        "audio_url": audio_url,  # always set, allowing None to clear the field
    }

    try:
        sb.table("briefs").update(update_data).eq("brief_date", target_date).execute()
    except Exception as exc:
        msg = str(exc).lower()
        if "could not find" in msg or "does not exist" in msg:
            log.warning("Some audio columns missing in production — skipping DB update: %s", exc)
        else:
            raise

    if script_fr is not None or audio_url_fr is not None:
        fr_data: dict = {}
        if script_fr is not None:
            fr_data["audio_script_fr"] = script_fr
        if audio_url_fr is not None:
            fr_data["audio_url_fr"] = audio_url_fr
        if fr_data:
            try:
                sb.table("briefs").update(fr_data).eq("brief_date", target_date).execute()
            except Exception as exc:
                log.warning("French audio columns missing in production — skipping FR update: %s", exc)

    log.info(
        "Updated briefs table for %s (en=%s, fr=%s)",
        target_date,
        "set" if audio_url else "null",
        "set" if audio_url_fr else "null",
    )


# ---------------------------------------------------------------------------
# Language learning content generation
# ---------------------------------------------------------------------------

LEARNING_SCRIPT_PROMPT_FILE = "language_learning_prompt.md"
LEARNING_OUTLINE_PROMPT_FILE = "language_learning_outline_prompt.md"
LEARNING_SECTIONS_PROMPT_FILE = "language_learning_sections_prompt.md"
LEARNING_SCRIPT_MAX_TOKENS = 4096
LEARNING_SECTIONS_MAX_TOKENS = 8192
LEARNING_SCRIPT_MAX_ATTEMPTS = 2
# Chars-per-second for audio duration estimation
CHARS_PER_SECOND_FR = 5.5
CHARS_PER_SECOND_AR = 4.5


def _load_learning_prompt(item: dict, lang: str) -> str:
    """Load the language learning prompt and inject item data."""
    prompt_path = PROMPTS_DIR / LEARNING_SCRIPT_PROMPT_FILE

    if not prompt_path.exists():
        log.warning("Learning prompt not found at %s — skipping learning content generation", prompt_path)
        return ""

    # Use the full markdown as the prompt (don't extract from code fences —
    # the learning prompt IS the full file, not wrapped in a single code block)
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()

    # Build item summary for the prompt
    item_summary = {
        "id": item.get("id", ""),
        "headline": item.get("headline", ""),
        "section": item.get("section", ""),
        "main_bullet": item.get("main_bullet", ""),
        "context": item.get("context", ""),
        "implication": item.get("implication", ""),
    }
    # v2 card fields (optional)
    if item.get("key_bullets"):
        item_summary["key_bullets"] = item.get("key_bullets")
    if item.get("analysis"):
        item_summary["analysis"] = item.get("analysis")
    if item.get("primary_entity"):
        item_summary["primary_entity"] = item.get("primary_entity")

    prompt_text = prompt_text.replace("{item_json}", json.dumps(item_summary, indent=2, ensure_ascii=False))
    prompt_text = prompt_text.replace("{target_language}", "French" if lang == "fr" else "Arabic")

    return prompt_text


def _generate_learning_content(item: dict, lang: str) -> dict | None:
    """Generate language learning content for a single brief item using Claude Sonnet.

    Returns a dict with {script, vocabulary: [{term, translation, definition, example_sentence, pos}], difficulty}
    or None on failure.
    """
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping learning content generation")
        return None

    prompt_text = _load_learning_prompt(item, lang)
    if not prompt_text:
        return None

    client = _get_anthropic_client()
    lang_label = "French" if lang == "fr" else "Arabic"

    for attempt in range(LEARNING_SCRIPT_MAX_ATTEMPTS):
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=LEARNING_SCRIPT_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt_text}],
            )

            text_blocks = [block.text for block in response.content if block.type == "text"]
            raw = "\n".join(text_blocks).strip()
            parsed = _extract_json_object(raw)

            if parsed and isinstance(parsed, dict):
                script = str(parsed.get("script", "")).strip()
                vocab = parsed.get("vocabulary", [])
                difficulty = str(parsed.get("difficulty", "intermediate")).strip()

                if script and len(script) > 30:
                    # Validate vocabulary entries
                    validated_vocab = []
                    for v in (vocab if isinstance(vocab, list) else []):
                        if isinstance(v, dict) and v.get("term") and v.get("translation"):
                            validated_vocab.append({
                                "term": str(v.get("term", "")).strip(),
                                "translation": str(v.get("translation", "")).strip(),
                                "definition": str(v.get("definition", "")).strip(),
                                "example_sentence": str(v.get("example_sentence", "")).strip(),
                                "part_of_speech": str(v.get("part_of_speech", "")).strip(),
                            })

                    return {
                        "script": script,
                        "vocabulary": validated_vocab[:10],  # Cap at 10 entries
                        "difficulty": difficulty,
                    }
                else:
                    log.warning("Learning script for %s item %s too short (%d chars) on attempt %d",
                                lang_label, item.get("id", "?"), len(script), attempt + 1)
            else:
                log.warning("Could not parse %s learning content JSON for item %s on attempt %d",
                            lang_label, item.get("id", "?"), attempt + 1)

        except Exception as exc:
            log.warning("Learning content generation failed for %s item %s on attempt %d: %s",
                        lang_label, item.get("id", "?"), attempt + 1, exc)

    return None


def _generate_item_learning_audio(
    sb: Client,
    script: str,
    voice_id: str,
    target_date: str,
    item_id: str,
    lang: str,
) -> str | None:
    """Generate TTS audio for a learning script and upload to Supabase Storage.

    Path: {target_date}/learning/{item_id}_{lang}.mp3
    Returns public URL on success, None on failure.
    """
    try:
        audio_bytes = _generate_audio(script, voice_id, lang=lang)
        file_path = f"{target_date}/learning/{item_id}_{lang}.mp3"
        log.info("Uploading learning audio to audio-briefs/%s...", file_path)
        sb.storage.from_("audio-briefs").upload(
            file_path,
            audio_bytes,
            file_options={"content-type": "audio/mpeg", "upsert": "true"},
        )
        public_url = sb.storage.from_("audio-briefs").get_public_url(file_path)
        log.info("Learning audio uploaded for %s item %s (%s): %s",
                 target_date, item_id, lang, public_url)
        return public_url
    except Exception as exc:
        log.warning("Learning audio generation failed for item %s (%s): %s", item_id, lang, exc)
        return None


def _has_v2_learning(item: dict, lang: str) -> bool:
    """Check if an item already has v2 (multi-section) learning content."""
    lc = item.get(f"learning_{lang}")
    if not lc or not isinstance(lc, dict):
        return False
    sections = lc.get("sections")
    return isinstance(sections, list) and len(sections) >= 2


def _build_rich_item_summary(item: dict, for_learning: bool = False) -> dict:
    """Build a comprehensive item summary with ALL available fields for maximum differentiation.

    When for_learning=True, strips verbose AI-generated fields (context, analysis,
    implication) that bias Claude toward pure target-language output.
    """
    summary: dict[str, Any] = {
        "id": item.get("id", ""),
        "headline": item.get("headline", ""),
        "section": item.get("section", ""),
        "main_bullet": item.get("main_bullet", ""),
    }
    if not for_learning:
        summary["context"] = item.get("context", "")
        summary["implication"] = item.get("implication", "")
        if item.get("analysis"):
            summary["analysis"] = item["analysis"]
    if item.get("key_bullets"):
        bullets = item["key_bullets"]
        summary["key_bullets"] = (
            " | ".join(bullets) if isinstance(bullets, list) else str(bullets)
        )
    if item.get("primary_entity"):
        summary["primary_entity"] = item["primary_entity"]
    if item.get("primary_subject"):
        summary["primary_subject"] = item["primary_subject"]
    if item.get("entities"):
        summary["entities"] = item["entities"][:8]
    return summary


def _load_learning_outline_prompt(item: dict, lang: str) -> str:
    """Load the outline prompt and inject item data."""
    prompt_path = PROMPTS_DIR / LEARNING_OUTLINE_PROMPT_FILE
    if not prompt_path.exists():
        log.warning("Learning outline prompt not found at %s", prompt_path)
        return ""
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()
    item_summary = _build_rich_item_summary(item, for_learning=True)
    lang_label = "French" if lang == "fr" else "Arabic"
    prompt_text = prompt_text.replace("{item_json}", json.dumps(item_summary, indent=2, ensure_ascii=False))
    prompt_text = prompt_text.replace("{target_language}", lang_label)
    prompt_text = prompt_text.replace("{item_id}", str(item.get("id", "")))
    prompt_text = prompt_text.replace("{item_headline}", str(item.get("headline", "")))
    return prompt_text


def _load_learning_sections_prompt(item: dict, outline: dict, lang: str) -> str:
    """Load the sections prompt and inject item data + outline."""
    prompt_path = PROMPTS_DIR / LEARNING_SECTIONS_PROMPT_FILE
    if not prompt_path.exists():
        log.warning("Learning sections prompt not found at %s", prompt_path)
        return ""
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()
    item_summary = _build_rich_item_summary(item, for_learning=True)
    lang_label = "French" if lang == "fr" else "Arabic"
    prompt_text = prompt_text.replace("{item_json}", json.dumps(item_summary, indent=2, ensure_ascii=False))
    prompt_text = prompt_text.replace("{outline_json}", json.dumps(outline, indent=2, ensure_ascii=False))
    prompt_text = prompt_text.replace("{target_language}", lang_label)
    prompt_text = prompt_text.replace("{item_id}", str(item.get("id", "")))
    prompt_text = prompt_text.replace("{item_headline}", str(item.get("headline", "")))
    return prompt_text


def _generate_learning_outline(item: dict, lang: str) -> dict | None:
    """Step 1: Generate a teaching outline for a news item."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping learning outline generation")
        return None

    prompt_text = _load_learning_outline_prompt(item, lang)
    if not prompt_text:
        return None

    client = _get_anthropic_client()
    lang_label = "French" if lang == "fr" else "Arabic"

    for attempt in range(LEARNING_SCRIPT_MAX_ATTEMPTS):
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=LEARNING_SCRIPT_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt_text}],
            )
            text_blocks = [block.text for block in response.content if block.type == "text"]
            raw = "\n".join(text_blocks).strip()
            parsed = _extract_json_object(raw)

            if parsed and isinstance(parsed, dict):
                sections = parsed.get("sections", [])
                if isinstance(sections, list) and len(sections) >= 3:
                    log.info("%s outline generated for item %s: %d sections",
                             lang_label, item.get("id", "?"), len(sections))
                    return parsed
                else:
                    log.warning("Outline for %s item %s has too few sections (%d) on attempt %d",
                                lang_label, item.get("id", "?"),
                                len(sections) if isinstance(sections, list) else 0, attempt + 1)
            else:
                log.warning("Could not parse %s outline JSON for item %s on attempt %d. "
                            "Response starts with: %.500s",
                            lang_label, item.get("id", "?"), attempt + 1, raw[:500] if raw else "<empty>")
        except Exception as exc:
            log.warning("Outline generation failed for %s item %s on attempt %d: %s",
                        lang_label, item.get("id", "?"), attempt + 1, exc)
    return None


def _generate_learning_sections(item: dict, outline: dict, lang: str) -> dict | None:
    """Step 2: Generate full section content given an outline."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping learning sections generation")
        return None

    prompt_text = _load_learning_sections_prompt(item, outline, lang)
    if not prompt_text:
        return None

    client = _get_anthropic_client()
    lang_label = "French" if lang == "fr" else "Arabic"

    bilingual_repair = (
        f"CRITICAL: The previous attempt generated scripts entirely in {lang_label} "
        f"with NO English narration. This is REJECTED. "
        f"Every single script MUST open with an English sentence. "
        f"Write teaching content in English with {lang_label} words embedded, "
        f"followed by their English translations."
    )

    for attempt in range(LEARNING_SCRIPT_MAX_ATTEMPTS):
        try:
            request_prompt = prompt_text
            max_tokens = LEARNING_SECTIONS_MAX_TOKENS
            if attempt > 0:
                request_prompt = f"{prompt_text}\n\n{bilingual_repair}"
                max_tokens = int(LEARNING_SECTIONS_MAX_TOKENS * 1.25)

            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": request_prompt}],
            )
            text_blocks = [block.text for block in response.content if block.type == "text"]
            raw = "\n".join(text_blocks).strip()
            parsed = _extract_json_object(raw)

            if not parsed or not isinstance(parsed, dict):
                log.warning("Could not parse %s sections JSON for item %s on attempt %d",
                            lang_label, item.get("id", "?"), attempt + 1)
                continue

            sections = parsed.get("sections", [])
            if not isinstance(sections, list) or len(sections) < 3:
                log.warning("Sections for %s item %s has too few entries (%d) on attempt %d",
                            lang_label, item.get("id", "?"),
                            len(sections) if isinstance(sections, list) else 0, attempt + 1)
                continue

            validated_sections = []
            for s in sections:
                if not isinstance(s, dict):
                    continue
                script = str(s.get("script", "")).strip()
                if len(script) < 30:
                    log.warning("Section %s script too short (%d chars) for %s item %s",
                                s.get("id", "?"), len(script), lang_label, item.get("id", "?"))
                    continue

                validated_phrases = []
                for p in (s.get("key_phrases") or []):
                    if isinstance(p, dict) and p.get("phrase") and p.get("translation"):
                        # Extract example_sentences array (cap at 4)
                        raw_examples = p.get("example_sentences") or []
                        example_sentences = [
                            str(e).strip()
                            for e in (raw_examples if isinstance(raw_examples, list) else [])
                            if e
                        ][:4]

                        validated_phrases.append({
                            "phrase": str(p.get("phrase", "")).strip(),
                            "translation": str(p.get("translation", "")).strip(),
                            "context_note": str(p.get("context_note", "")).strip(),
                            "example_sentence": str(p.get("example_sentence", "")).strip(),
                            "part_of_speech": str(p.get("part_of_speech", "")).strip(),
                            "grammar_note": str(p.get("grammar_note", "")).strip(),
                            "pronunciation_guide": str(p.get("pronunciation_guide", "")).strip(),
                            "example_sentences": example_sentences,
                            "word_root": str(p.get("word_root", "")).strip(),
                            "register": str(p.get("register", "")).strip(),
                            "conjugation": str(p.get("conjugation", "")).strip(),
                        })

                validated_sections.append({
                    "id": str(s.get("id", f"section_{len(validated_sections)}")),
                    "type": str(s.get("type", "narrative")),
                    "title": str(s.get("title", "")),
                    "title_en": str(s.get("title_en", "")),
                    "script": script,
                    "key_phrases": validated_phrases,
                })

            if len(validated_sections) < 3:
                log.warning("Only %d valid sections for %s item %s on attempt %d",
                            len(validated_sections), lang_label, item.get("id", "?"), attempt + 1)
                continue

            # Bilingual validation — every script MUST contain English narration
            all_bilingual = True
            for s in validated_sections:
                script = s["script"]
                if not _is_bilingual_script(script, lang):
                    all_bilingual = False
                    log.warning(
                        "Section %s failed bilingual check for %s item %s (attempt %d)",
                        s["id"], lang_label, item.get("id", "?"), attempt + 1,
                    )
                    break

            if not all_bilingual:
                log.warning(
                    "%s sections are pure target language — retrying with bilingual enforcement",
                    lang_label,
                )
                continue

            vocab = parsed.get("vocabulary", [])
            validated_vocab = []
            for v in (vocab if isinstance(vocab, list) else []):
                if isinstance(v, dict) and v.get("term") and v.get("translation"):
                    raw_examples = v.get("example_sentences") or []
                    example_sentences = [
                        str(e).strip()
                        for e in (raw_examples if isinstance(raw_examples, list) else [])
                        if e
                    ][:4]

                    validated_vocab.append({
                        "term": str(v.get("term", "")).strip(),
                        "translation": str(v.get("translation", "")).strip(),
                        "definition": str(v.get("definition", "")).strip(),
                        "example_sentence": str(v.get("example_sentence", "")).strip(),
                        "part_of_speech": str(v.get("part_of_speech", "")).strip(),
                        "grammar_note": str(v.get("grammar_note", "")).strip(),
                        "pronunciation_guide": str(v.get("pronunciation_guide", "")).strip(),
                        "example_sentences": example_sentences,
                    })

            difficulty = str(parsed.get("difficulty", "intermediate")).strip()
            log.info("%s sections generated for item %s: %d sections, %d vocab terms",
                     lang_label, item.get("id", "?"), len(validated_sections), len(validated_vocab))

            return {
                "sections": validated_sections,
                "vocabulary": validated_vocab[:10],
                "difficulty": difficulty,
            }

        except Exception as exc:
            log.warning("Sections generation failed for %s item %s on attempt %d: %s",
                        lang_label, item.get("id", "?"), attempt + 1, exc)
    return None


def _generate_section_audio(
    sb: Client,
    script: str,
    voice_id: str,
    target_date: str,
    item_id: str,
    lang: str,
    section_id: str,
) -> str | None:
    """Generate TTS audio for a single learning section and upload to Supabase Storage.

    Path: {target_date}/learning/{item_id}_{lang}_{section_id}.mp3
    """
    try:
        audio_bytes = _generate_audio(script, voice_id, lang=lang)
        file_path = f"{target_date}/learning/{item_id}_{lang}_{section_id}.mp3"
        log.info("Uploading section audio to audio-briefs/%s...", file_path)
        sb.storage.from_("audio-briefs").upload(
            file_path,
            audio_bytes,
            file_options={"content-type": "audio/mpeg", "upsert": "true"},
        )
        public_url = sb.storage.from_("audio-briefs").get_public_url(file_path)
        return public_url
    except Exception as exc:
        log.warning("Section audio failed for item %s section %s (%s): %s",
                    item_id, section_id, lang, exc)
        return None


def _estimate_duration_seconds(script: str, lang: str) -> float:
    """Estimate audio duration in seconds from script character count.

    Uses language-specific and script-type-aware character-per-second rates:
    - English-dominated bilingual (script1, script4): ~14 chars/sec
    - Pure target language (script3): varies by language
      - French: ~13 chars/sec (slightly slower due to liaison/elision)
      - Arabic: ~11 chars/sec (diacritics, longer phonetic units)
    - Short transitions (script2): ~15 chars/sec (clear, deliberate speech)

    Adds a small pause buffer (0.3s) for natural breathing between segments.
    """
    script_len = len(script)

    # Determine speech rate based on script content
    if script_len <= 45:
        # Short transitions: deliberate, clear speech
        cps = 15.0
    elif any(c in script for c in ("،", "؟", "ٱ", "ً", "ٍ", "ٌ", "َ", "ِ", "ُ")):
        # Arabic with diacritics or special punctuation: slower
        cps = 11.0
    elif lang == "ar":
        # Arabic without diacritics
        cps = 12.0
    elif lang == "fr":
        # French with liaisons
        cps = 13.0
    else:
        # Default: English-dominated bilingual
        cps = 14.0

    # Add natural pause buffer for segments over 50 chars
    pause_buffer = 0.3 if script_len > 50 else 0.1
    return (script_len / cps) + pause_buffer


def _generate_learning_content_v2(item: dict, lang: str) -> dict | None:
    """Generate multi-section language learning content (v2 pipeline).

    Step 1: Generate teaching outline
    Step 2: Generate section scripts, phrases, and vocabulary
    Returns dict {sections, vocabulary, difficulty, total_audio_duration_seconds} or None.
    """
    item_id = item.get("id", "?")
    lang_label = "French" if lang == "fr" else "Arabic"
    log.info("Generating v2 learning content for %s item %s: %s",
             lang_label, item_id, item.get("headline", "?")[:80])

    # Step 1: Generate outline
    outline = _generate_learning_outline(item, lang)
    if not outline:
        log.warning("Outline generation failed for %s item %s — skipping item", lang_label, item_id)
        return None

    # Step 2: Generate full section content
    content = _generate_learning_sections(item, outline, lang)
    if not content:
        log.warning("Sections generation failed for %s item %s — skipping item", lang_label, item_id)
        return None

    # Estimate total duration
    total_duration = sum(
        _estimate_duration_seconds(s["script"], lang)
        for s in content["sections"]
    )
    content["total_audio_duration_seconds"] = round(total_duration, 1)

    for s in content["sections"]:
        s["estimated_duration_seconds"] = round(
            _estimate_duration_seconds(s["script"], lang), 1
        )

    return content


# ---------------------------------------------------------------------------
# V3: Phrase-based learning content (simplified)
# ---------------------------------------------------------------------------

LEARNING_PHRASES_PROMPT_FILE = "language_learning_phrases_prompt.md"
LEARNING_PHRASES_MAX_TOKENS = 6144
DEFAULT_PHRASE_COUNT = 3


def _has_v3_learning(item: dict, lang: str) -> bool:
    """Check if an item already has v3 (phrase-based) learning content."""
    lc = item.get(f"learning_{lang}")
    if not lc or not isinstance(lc, dict):
        return False
    return lc.get("version") == 3 and isinstance(lc.get("phrases"), list) and len(lc["phrases"]) >= 1


def _load_learning_phrases_prompt(item: dict, lang: str, phrase_count: int = 3) -> str:
    """Load and inject template vars into the phrases prompt."""
    target_language = "French" if lang == "fr" else "Arabic"
    item_json = json.dumps(_build_rich_item_summary(item, for_learning=True), indent=2, ensure_ascii=False)
    item_id = item.get("id", "?")
    item_headline = item.get("headline", "?")

    prompt_path = PROMPTS_DIR / LEARNING_PHRASES_PROMPT_FILE
    if not prompt_path.exists():
        log.error("Phrases prompt not found: %s", prompt_path)
        return ""

    template = prompt_path.read_text(encoding="utf-8")
    return template.format(
        item_json=item_json,
        target_language=target_language,
        phrase_count=phrase_count,
        item_id=item_id,
        item_headline=item_headline,
    )


def _call_anthropic(prompt: str, max_tokens: int) -> str:
    """Call Anthropic Claude API with circuit breaker protection.

    Uses the pooled Anthropic client for connection reuse.
    Checks circuit breaker before making the call to prevent
    cascade failures during API outages.
    Returns the raw response text.
    Raises RuntimeError if circuit is open.
    """
    if not _llm_circuit_breaker.should_attempt():
        raise RuntimeError(
            f"LLM API circuit breaker is OPEN (state={_llm_circuit_breaker.state}). "
            "Skipping request to prevent cascade failures."
        )

    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [block.text for block in response.content if block.type == "text"]
        _llm_circuit_breaker.record_success()
        return "\n".join(text_blocks).strip()
    except Exception as exc:
        _llm_circuit_breaker.record_failure()
        raise


def _parse_json_response(text: str) -> dict | None:
    """Extract and parse JSON from an Anthropic response.

    Handles markdown code blocks and leading/trailing whitespace.
    Returns parsed dict or None on failure or empty input.
    """
    if not text:
        return None
    return _extract_json_object(text)


def _generate_learning_phrases(item: dict, lang: str, phrase_count: int = 3) -> dict | None:
    """Generate phrase-based learning content via a single Claude call (v3 pipeline).

    Returns dict {phrases, vocabulary, difficulty} or None on failure.
    """
    item_id = item.get("id", "?")
    lang_label = "French" if lang == "fr" else "Arabic"
    log.info("Generating v3 learning phrases for %s item %s: %s",
             lang_label, item_id, item.get("headline", "?")[:80])

    for attempt in range(LEARNING_SCRIPT_MAX_ATTEMPTS):
        prompt = _load_learning_phrases_prompt(item, lang, phrase_count)
        if not prompt:
            return None

        try:
            result = _call_anthropic(prompt, LEARNING_PHRASES_MAX_TOKENS)
            content = _parse_json_response(result)

            # Validate structure
            if not content or not isinstance(content, dict):
                log.warning("v3 phrases: invalid response format (attempt %d)", attempt + 1)
                continue

            phrases = content.get("phrases")
            if not phrases or not isinstance(phrases, list) or len(phrases) < 1:
                log.warning("v3 phrases: missing or empty phrases array (attempt %d)", attempt + 1)
                continue

            # Validate each phrase has required fields
            valid_phrases = []
            for p in phrases:
                if (
                    isinstance(p, dict)
                    and p.get("phrase_target")
                    and p.get("phrase_en")
                    and p.get("script1")
                    and p.get("script2")
                    and p.get("script3")
                    and p.get("script4")
                    and isinstance(p.get("grammar"), dict)
                ):
                    # Bilingual check on script1 and script4
                    if not _is_bilingual_script(p.get("script1", "")):
                        log.warning("v3 phrases: script1 failed bilingual check for '%s'", p["phrase_target"][:40])
                        continue
                    if not _is_bilingual_script(p.get("script4", "")):
                        log.warning("v3 phrases: script4 failed bilingual check for '%s'", p["phrase_target"][:40])
                        continue
                    valid_phrases.append(p)

            if len(valid_phrases) < 1:
                log.warning("v3 phrases: no valid phrases after validation (attempt %d)", attempt + 1)
                continue

            difficulty = content.get("difficulty", "intermediate")
            if difficulty not in ("beginner", "intermediate", "advanced"):
                difficulty = "intermediate"

            return {
                "phrases": valid_phrases,
                "difficulty": difficulty,
            }

        except Exception as exc:
            log.warning("v3 phrases: generation error (attempt %d): %s", attempt + 1, exc)

    log.warning("v3 phrases: all %d attempts failed for item %s", LEARNING_SCRIPT_MAX_ATTEMPTS, item_id)
    return None


def _generate_phrase_audio(
    sb: Client,
    script: str,
    voice_id: str,
    target_date: str,
    item_id: str,
    lang: str,
    phrase_idx: int,
    script_idx: int,
) -> str | None:
    """Generate TTS audio for a single phrase script and upload to Supabase.

    Path: {target_date}/learning/{item_id}_{lang}_p{phrase_idx}_s{script_idx}.mp3
    """
    try:
        audio_bytes = _generate_audio(script, voice_id, lang=lang)
        file_path = f"{target_date}/learning/{item_id}_{lang}_p{phrase_idx}_s{script_idx}.mp3"
        log.info("Uploading phrase audio to audio-briefs/%s...", file_path)
        sb.storage.from_("audio-briefs").upload(
            file_path,
            audio_bytes,
            file_options={"content-type": "audio/mpeg", "upsert": "true"},
        )
        public_url = sb.storage.from_("audio-briefs").get_public_url(file_path)
        return public_url
    except Exception as exc:
        log.warning("Phrase audio failed for item %s p%s_s%s (%s): %s",
                    item_id, phrase_idx, script_idx, lang, exc)
        return None


def _generate_learning_content_v3(
    item: dict,
    lang: str,
    phrase_count: int = DEFAULT_PHRASE_COUNT,
) -> dict | None:
    """Generate phrase-based language learning content (v3 pipeline).

    Single Claude call for phrase selection + scripts, then 4 TTS calls per phrase.
    Returns dict {version, phrases, difficulty, total_duration_seconds} or None.
    """
    item_id = item.get("id", "?")
    lang_label = "French" if lang == "fr" else "Arabic"
    log.info("Generating v3 learning content for %s item %s", lang_label, item_id)

    content = _generate_learning_phrases(item, lang, phrase_count)
    if not content:
        log.warning("v3 content: phrase generation failed for item %s — skipping", item_id)
        return None

    # Estimate durations per phrase (scripts 1-3 only; script4 is on-demand)
    for p in content["phrases"]:
        dur = sum(
            _estimate_duration_seconds(p.get(f"script{s}", ""), lang)
            for s in range(1, 4)
        )
        p["estimated_duration_seconds"] = round(dur, 1)

    total_duration = sum(p.get("estimated_duration_seconds", 0) for p in content["phrases"])

    return {
        "version": 3,
        "phrases": content["phrases"],
        "difficulty": content["difficulty"],
        "total_duration_seconds": round(total_duration, 1),
    }


def _generate_learning_content_sync(
    sb: Client,
    target_date: str,
    active_items: list[dict],
    languages: list[str],
    brief_json: dict,
    force: bool = False,
) -> None:
    """Generate v3 learning content synchronously (non-Celery mode)."""
    voice_config = _get_voice_config()

    for lang in languages:
        lang_display = "French" if lang == "fr" else "Arabic"
        learning_count = 0
        phrase_audio_count = 0

        pending_items = [
            item for item in active_items
            if force or not _has_v3_learning(item, lang)
        ]

        for item in pending_items:
            item_id = item.get("id", "?")
            try:
                learning = _generate_learning_content_v3(item, lang)
                if not learning:
                    continue

                item[f"learning_{lang}"] = learning
                learning_count += 1

                # Generate per-phrase audio: scripts 1,2,4 use EN voice; script3 uses target-lang voice
                en_voice = voice_config.get("en", {}).get("voice_id", "")
                target_voice = voice_config.get(lang, {}).get("voice_id", "")

                for p_idx, phrase in enumerate(learning.get("phrases", [])):
                    for s_idx in range(1, 5):
                        script_text = phrase.get(f"script{s_idx}", "")
                        if not script_text or len(script_text) < 10:
                            continue

                        # Script3 uses target language voice; others use EN voice
                        voice = target_voice if s_idx == 3 else en_voice
                        script_lang = lang if s_idx == 3 else "en"

                        audio_url = _generate_phrase_audio(
                            sb, script_text, voice, target_date,
                            item_id, lang, p_idx, s_idx,
                        )
                        if audio_url:
                            phrase[f"audio_url_{s_idx}"] = audio_url
                            phrase_audio_count += 1

            except Exception as exc:
                log.warning("%s v3 learning content failed for item %s: %s", lang_display, item_id, exc)

        log.info("%s v3 learning content: %d items, %d phrase audio files", lang_display, learning_count, phrase_audio_count)

    # Save updated raw_json
    if any(
        item.get(f"learning_{lang}")
        for item in active_items
        for lang in languages
    ):
        try:
            sb.table("briefs").update({"raw_json": brief_json}).eq(
                "brief_date", target_date
            ).execute()
            log.info("Updated raw_json with v3 learning content")
        except Exception as exc:
            log.warning("Failed to update raw_json with learning content: %s", exc)


def _submit_learning_tasks(
    target_date: str,
    active_items: list[dict],
    languages: list[str],
    brief_json: dict,
    sb: Client,
) -> None:
    """Submit Celery tasks for v3 learning content generation."""
    try:
        from tasks.learning_tasks import generate_learning_content

        task_ids = []
        for lang in languages:
            pending_items = [
                item for item in active_items
                if not _has_v3_learning(item, lang)
            ]
            for item in pending_items:
                item_id = item.get("id", "")
                if not item_id:
                    continue

                task = generate_learning_content.apply_async(
                    args=[target_date, item_id, lang, DEFAULT_PHRASE_COUNT],
                    queue="learning",
                )
                task_ids.append({
                    "item_id": item_id,
                    "lang": lang,
                    "task_id": task.id,
                })

        # Update generation status
        gen_status = brief_json.get("generation_status", {}) if isinstance(brief_json, dict) else {}
        for entry in task_ids:
            lang_key = f"learning_{entry['lang']}"
            gen_status[lang_key] = {
                "status": "running",
                "task_id": entry["task_id"],
                "item_id": entry["item_id"],
                "submitted_at": _now_iso(),
            }

        sb.table("briefs").update({"generation_status": gen_status}).eq(
            "brief_date", target_date
        ).execute()

        log.info("Submitted %d learning tasks for %s", len(task_ids), target_date)
    except ImportError:
        log.warning("Celery not available — falling back to sync generation")
        _generate_learning_content_sync(sb, target_date, active_items, languages, brief_json)
    except Exception as exc:
        log.warning("Celery task submission failed: %s — falling back to sync", exc)
        _generate_learning_content_sync(sb, target_date, active_items, languages, brief_json)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def _generate_and_prepare_script(
    brief_json: dict,
    *,
    shared_outline: str,
    outline_items: list[dict[str, str | int]],
    lang: str = "en",
) -> str:
    """Generate script, enforce budget, apply break markers for a given language."""
    expected_numbers = [int(item["number"]) for item in outline_items]
    raw_script = _generate_script(
        brief_json,
        shared_outline,
        outline_items,
        lang=lang,
    )
    script = _enforce_script_budget(raw_script, lang=lang)

    if outline_items and script != raw_script:
        audit = _audit_script_coverage(
            shared_outline,
            script,
            lang=lang,
            accept_parse_failure=False,
            fallback_missing_numbers=expected_numbers,
        )
        missing_numbers = list(audit.get("missing_item_numbers", []))
        if missing_numbers:
            log.warning(
                "%s script lost outline items during compression: %s. Retrying budget repair.",
                "French" if lang == "fr" else "English",
                missing_numbers,
            )
            repaired = _enforce_script_budget(
                raw_script,
                lang=lang,
                coverage_repair_instruction=_build_coverage_repair_instruction(
                    missing_numbers,
                    outline_items,
                    lang=lang,
                ),
            )
            repaired_audit = _audit_script_coverage(
                shared_outline,
                repaired,
                lang=lang,
                accept_parse_failure=False,
                fallback_missing_numbers=expected_numbers,
            )
            repaired_missing = list(repaired_audit.get("missing_item_numbers", []))

            if repaired_missing:
                log.warning(
                    "%s script still misses outline items after compression repair: %s. Using uncompressed script instead.",
                    "French" if lang == "fr" else "English",
                    repaired_missing,
                )
                script = raw_script
            else:
                script = repaired

    if outline_items:
        final_audit = _audit_script_coverage(
            shared_outline,
            script,
            lang=lang,
            accept_parse_failure=False,
            fallback_missing_numbers=expected_numbers,
        )
        final_missing = list(final_audit.get("missing_item_numbers", []))
        if final_missing and script != raw_script:
            log.warning(
                "%s final compressed script still misses outline items %s. Falling back to the uncompressed native script.",
                "French" if lang == "fr" else "English",
                final_missing,
            )
            script = raw_script

    if ENABLE_SSML_BREAK_MARKERS:
        script = _apply_break_markers(script)
    return script


def generate_audio_brief(
    sb: Client,
    target_date: str,
    script_only: bool = False,
    from_db: bool = False,
    force: bool = False,
    async_mode: bool = False,
) -> bool:
    """Full pipeline: read brief -> generate transcript script -> generate per-item audio -> upload -> update DB.

    Generates per-item audio files from structured item data, stored in
    raw_json["items"][n].audio_url for card-level playback.
    The Claude narrative script is generated for the transcript display only —
    no monolithic narrative TTS is produced.
    When from_db=True, fetches the brief from the briefs table instead of a local file.
    Returns True on success, False on failure.
    """
    from concurrent.futures import ThreadPoolExecutor, Future, as_completed
    import time as _retry_sleep

    # 1. Read brief JSON
    brief_json = None

    if from_db:
        try:
            result = (
                sb.table("briefs")
                .select("raw_json")
                .eq("brief_date", target_date)
                .single()
                .execute()
            )
            brief_json = result.data.get("raw_json") if result.data else None
            if not brief_json:
                log.error("No brief found in DB for %s", target_date)
                _update_audio_status(sb, target_date, "failed")
                return False
            log.info("Loaded brief from DB for %s", target_date)
        except Exception as exc:
            log.error("Failed to fetch brief from DB for %s: %s", target_date, exc)
            _update_audio_status(sb, target_date, "failed")
            return False
    else:
        brief_path = OUTPUT_DIR / f"brief_{target_date}.json"
        if not brief_path.exists():
            log.error("No brief JSON found for %s (expected %s)", target_date, brief_path)
            return False

        try:
            brief_json = json.loads(brief_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Failed to read %s: %s", brief_path, exc)
            return False

    # 2. Generate Claude narrative script for the transcript display
    _update_audio_status(sb, target_date, "generating_script")
    shared_outline, outline_items = _build_shared_outline(brief_json)

    log.info(
        "Shared audio outline prepared for %s: %d required items",
        target_date,
        len(outline_items),
    )

    try:
        script_en = _generate_and_prepare_script(
            brief_json,
            shared_outline=shared_outline,
            outline_items=outline_items,
            lang="en",
        )
    except Exception as exc:
        log.error("English script generation failed for %s: %s", target_date, exc)
        _update_audio_status(sb, target_date, "failed")
        return False

    # Save script locally
    en_script_path = OUTPUT_DIR / f"audio_script_{target_date}_en.txt"
    en_script_path.write_text(script_en, encoding="utf-8")
    log.info("EN script saved to %s", en_script_path.name)

    if script_only:
        log.info("Script-only mode — skipping TTS and upload")
        try:
            _update_briefs_table(
                sb, target_date,
                audio_url=None, script=script_en,
            )
        except Exception as exc:
            log.warning("Failed to update DB with scripts: %s", exc)
        return True

    # 3. Generate per-item audio concurrently with retries
    _update_audio_status(sb, target_date, "generating_item_audio")
    voice_config = _get_voice_config()
    en_voice = voice_config["en"]["voice_id"]
    items = brief_json.get("items", [])

    active_items = [item for item in items if not item.get("is_placeholder") and item.get("id")]
    # O(1) index for fast URL writeback
    items_by_id = {item["id"]: item for item in active_items}
    log.info(
        "Generating per-item audio for %d of %d items (EN)",
        len(active_items),
        len(items),
    )

    en_item_audio_count = 0
    pending_items: list[dict] = []

    for item in active_items:
        if item.get("audio_url") and not force:
            log.info("Item %s already has audio_url — skipping (use --force to regenerate)", item["id"])
            en_item_audio_count += 1
            continue
        pending_items.append(item)

    if pending_items:
        # Adaptive concurrency: scale up to 8 for larger batches, minimum 3
        MAX_CONCURRENT = min(len(pending_items), 8)
        MAX_RETRIES = 3

        def _process_item(item: dict) -> tuple[str, str, int] | None:
            """Generate and upload audio for a single item with retries."""
            item_id = item["id"]
            item_script = _build_item_script(item)
            if not item_script or len(item_script) < 15:
                log.warning("Skipping item %s: script too short (%d chars)", item_id, len(item_script))
                return None

            for attempt in range(MAX_RETRIES):
                try:
                    if attempt > 0:
                        delay = (attempt + 1) * 3
                        log.warning("Item %s: retrying in %ds (attempt %d/%d)...",
                                    item_id, delay, attempt + 1, MAX_RETRIES)
                        _retry_sleep.sleep(delay)

                    audio_bytes = _generate_audio(item_script, en_voice)
                    url = _upload_item_audio(sb, audio_bytes, target_date, item_id)
                    return (item_id, url, len(item_script))
                except Exception as exc:
                    if attempt < MAX_RETRIES - 1:
                        log.warning("Item %s attempt %d/%d failed: %s",
                                    item_id, attempt + 1, MAX_RETRIES, exc)
                    else:
                        log.warning("Item audio failed for %s after %d attempts: %s",
                                    item_id, MAX_RETRIES, exc)

            return None

        log.info(
            "Processing %d items with concurrency=%d, retries=%d",
            len(pending_items), MAX_CONCURRENT, MAX_RETRIES,
        )

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
            futures_map: dict[Future, dict] = {}
            for item in pending_items:
                future = pool.submit(_process_item, item)
                futures_map[future] = item

            for future in as_completed(futures_map):
                result = future.result()
                if result:
                    item_id, url, chars = result
                    # O(1) writeback via dictionary index
                    if item_id in items_by_id:
                        items_by_id[item_id]["audio_url"] = url
                    en_item_audio_count += 1
                    log.info("Item audio generated for %s (%d chars): %s",
                             item_id, chars, url)

    # 3b. Generate language learning content (FR + AR) — v3 phrase-based pipeline
    if _learning_content_enabled():
        _update_audio_status(sb, target_date, "generating_learning_content")
        LEARNING_LANGS = []
        if _french_audio_enabled():
            LEARNING_LANGS.append("fr")
        if _arabic_audio_enabled() and _get_voice_config().get("ar", {}).get("voice_id"):
            LEARNING_LANGS.append("ar")

        if LEARNING_LANGS:
            if async_mode:
                log.info(
                    "Submitting v3 learning content tasks for %s (languages: %s)",
                    target_date, ", ".join(LEARNING_LANGS),
                )
                _submit_learning_tasks(target_date, active_items, LEARNING_LANGS, brief_json, sb)
            else:
                log.info(
                    "Generating v3 language learning content for %s (languages: %s)",
                    target_date, ", ".join(LEARNING_LANGS),
                )
                _generate_learning_content_sync(sb, target_date, active_items, LEARNING_LANGS, brief_json, force)

    # Save updated raw_json with per-item audio URLs to DB
    if en_item_audio_count > 0:
        try:
            sb.table("briefs").update({"raw_json": brief_json}).eq(
                "brief_date", target_date
            ).execute()
            log.info("Updated raw_json with %d per-item audio URLs", en_item_audio_count)
        except Exception as exc:
            log.warning("Failed to update raw_json with item audio URLs: %s", exc)

    # 4. Save transcript script to DB and revalidate frontend
    _update_audio_status(sb, target_date, "ready")
    try:
        _update_briefs_table(
            sb, target_date,
            audio_url=None, script=script_en,
        )
    except Exception as exc:
        log.warning("Failed to update DB with script: %s", exc)

    _revalidate_frontend(target_date)

    log.info("Audio brief complete for %s (per-item=%d items)",
             target_date, en_item_audio_count)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    _require_python_310_plus()

    parser = argparse.ArgumentParser(
        description="Generate audio briefing from daily brief JSON."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Generate for a specific date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--script-only",
        action="store_true",
        help="Generate script text only, skip TTS audio generation.",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Generate audio for all briefs in the output directory.",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Read brief from Supabase briefs table instead of local file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of audio even for items that already have audio_url.",
    )
    parser.add_argument(
        "--async",
        dest="async_mode",
        action="store_true",
        help="Submit generation tasks to Celery workers instead of running synchronously.",
    )
    args = parser.parse_args()

    _load_env()

    if not args.script_only and not _audio_brief_enabled():
        log.info("ENABLE_AUDIO_BRIEF is disabled — skipping audio briefing generation.")
        return

    sb = _get_supabase_client()

    if args.backfill:
        # Find all brief files
        brief_files = sorted(OUTPUT_DIR.glob("brief_*.json"))
        if not brief_files:
            log.warning("No brief files found in %s", OUTPUT_DIR)
            sys.exit(0)

        log.info("Backfill mode: found %d brief files", len(brief_files))

        # Parallel backfill: process 3-5 briefs concurrently (I/O-bound)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        MAX_BACKFILL_WORKERS = min(len(brief_files), 5)

        def _process_backfill_item(bp: Path) -> tuple[str, bool]:
            """Process a single brief file for backfill."""
            target = bp.stem.replace("brief_", "")
            try:
                date.fromisoformat(target)
            except ValueError:
                log.warning("Skipping non-date file: %s", bp.name)
                return (bp.name, False)

            ok = generate_audio_brief(sb, target, script_only=args.script_only, force=args.force)
            return (target, ok)

        success_count = 0
        fail_count = 0
        skipped_count = 0

        log.info("Processing backfill with %d concurrent workers", MAX_BACKFILL_WORKERS)
        with ThreadPoolExecutor(max_workers=MAX_BACKFILL_WORKERS) as pool:
            futures = {pool.submit(_process_backfill_item, bp): bp for bp in brief_files}
            for future in as_completed(futures):
                bp = futures[future]
                try:
                    target, ok = future.result()
                    if ok:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as exc:
                    log.error("Backfill failed for %s: %s", bp.name, exc)
                    fail_count += 1

        log.info("=" * 60)
        log.info(
            "Backfill complete: %d succeeded, %d failed, %d skipped, %d total",
            success_count,
            fail_count,
            skipped_count,
            success_count + fail_count + skipped_count,
        )
        if fail_count > 0:
            sys.exit(1)
    else:
        # Single date
        if args.date:
            try:
                target = date.fromisoformat(args.date)
            except ValueError:
                log.error("Invalid date format: %s (expected YYYY-MM-DD)", args.date)
                sys.exit(1)
            target_date = target.isoformat()
        else:
            target_date = _today_in_dubai_iso()

        ok = generate_audio_brief(
            sb, target_date,
            script_only=args.script_only,
            from_db=args.from_db,
            force=args.force,
            async_mode=args.async_mode,
        )
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
