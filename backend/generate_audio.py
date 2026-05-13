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
        "hard_max_words": 1100,
        "hard_max_chars": 8500,
    },
    "fr": {
        "target_words": 950,
        "hard_max_words": 1250,
        "hard_max_chars": 9500,
    },
}
BREAK_TAG_PATTERN = r'<break\s+time="[^"]+"\s*/>'

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
EN_VOICE_ID = "Daniel"
FR_VOICE_ID_DEFAULT = "c365oriviHmAhyLhpuN6"
VOICE_SETTINGS = {
    "stability": 0.3,
    "similarity_boost": 0.75,
    "style": 0.4,
    "use_speaker_boost": True,
}
VOICE_SPEED_FR = 0.9
# EN speed capped at 1.2 (the `speed` ceiling on eleven_multilingual_v2).
# A true +10% from the previous 1.1 would be 1.21, but the API rejects values
# above 1.2 — this is the fastest the model will render.
VOICE_SPEED_EN = 1.2

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
            "voice_id": EN_VOICE_ID,
            "prompt_file": "podcast_script_prompt.md",
        },
        "fr": {
            "voice_id": os.getenv("FRENCH_VOICE_ID", FR_VOICE_ID_DEFAULT),
            "prompt_file": "podcast_script_prompt_fr.md",
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
    prompt_text = prompt_text.replace("{brief_json}", json.dumps(brief_json, indent=2, ensure_ascii=False))
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
    """Parse a JSON object even if the model wraps it in markdown fences."""
    stripped = text.strip()
    if not stripped:
        return None

    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None


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

    client = anthropic.Anthropic(api_key=api_key)
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

    client = anthropic.Anthropic(api_key=api_key)
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
    client = anthropic.Anthropic(api_key=api_key)
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
    """
    import base64
    import httpx
    import json as _json

    api_key = os.getenv("VOICE_API_KEY")
    if not api_key:
        log.error("VOICE_API_KEY not set")
        raise RuntimeError("VOICE_API_KEY not set")

    if voice_id is None:
        voice_id = _get_voice_config()["en"]["voice_id"]

    using_argent = "txt2sph.audarai.com" in VOICE_BASE_URL

    chunk_limit = VOICE_MAX_CHARS_ARGENT if using_argent else VOICE_MAX_CHARS
    chunks = _split_script_into_chunks(script, max_chars=chunk_limit)
    log.info(
        "Script is %d characters — split into %d chunk(s) (provider=%s)",
        len(script), len(chunks),
        "Argent" if using_argent else "ElevenLabs",
    )

    all_audio: list[bytes] = []

    for i, chunk in enumerate(chunks):
        if using_argent:
            url = f"{VOICE_BASE_URL}/v1/synthesize"
            payload = {"text": chunk, "speaker_id": voice_id}
            headers = {"Content-Type": "application/json"}
        else:
            url = f"{VOICE_BASE_URL}/v1/text-to-speech/{voice_id}"
            payload = {
                "text": chunk,
                "model_id": VOICE_MODEL_ID,
                "voice_settings": VOICE_SETTINGS,
            }
            if lang == "fr":
                payload["speed"] = VOICE_SPEED_FR
            elif lang == "en":
                payload["speed"] = VOICE_SPEED_EN
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            }

        # Add a short delay between chunks for Argent (server cooldown)
        if i > 0 and using_argent:
            import time as _time
            _time.sleep(3)

        log.info("Calling TTS chunk %d/%d (%d chars)...", i + 1, len(chunks), len(chunk))

        # Retry up to 3 times for transient errors (429, 502, 503, 504)
        import time as _time2
        response = None
        for attempt in range(3):
            response = httpx.post(url, json=payload, headers=headers, timeout=180.0)
            if response.status_code == 200:
                break
            if response.status_code in (404, 429, 502, 503, 504) and attempt < 2:
                log.warning("TTS transient error %d (attempt %d/3), retrying in %ds...",
                            response.status_code, attempt + 1, (attempt + 1) * 3)
                _time2.sleep((attempt + 1) * 3)
                continue
            break

        if response.status_code != 200:
            log.error("TTS API error %d: %s", response.status_code, response.text[:500])
            response.raise_for_status()

        if using_argent:
            result = _json.loads(response.text)
            audio_b64 = result.get("audio", "")
            if not audio_b64:
                log.error("No audio in TTS response")
                raise RuntimeError("Empty audio response from TTS API")
            chunk_audio = base64.b64decode(audio_b64)
            log.info("Chunk %d/%d: %.0f KB (Opus, %.1fs)",
                     i + 1, len(chunks),
                     len(chunk_audio) / 1024,
                     result.get("duration", 0))
        else:
            chunk_audio = response.content
            log.info("Chunk %d/%d: %.0f KB", i + 1, len(chunks), len(chunk_audio) / 1024)

        all_audio.append(chunk_audio)

    # Merge chunks into a single MP3
    if len(all_audio) == 1 and not using_argent:
        # Single chunk from ElevenLabs — already MP3
        audio_bytes = all_audio[0]
    else:
        from io import BytesIO
        from pydub import AudioSegment

        combined = AudioSegment.empty()
        for i, raw in enumerate(all_audio):
            buf = BytesIO(raw)
            if using_argent:
                # Argent returns Ogg Opus audio — let ffmpeg auto-detect format
                segment = AudioSegment.from_file(buf)
            else:
                segment = AudioSegment.from_mp3(buf)
            combined += segment
            log.info("Merged chunk %d/%d (%.1fs)", i + 1, len(all_audio), len(segment) / 1000)

        buf = BytesIO()
        combined.export(buf, format="mp3", bitrate="128k")
        audio_bytes = buf.getvalue()
        log.info("Total merged duration: %.1fs", len(combined) / 1000)

    size_mb = len(audio_bytes) / (1024 * 1024)
    log.info("Audio generated: %.1f MB total", size_mb)

    return audio_bytes


# ---------------------------------------------------------------------------
# Supabase Storage upload
# ---------------------------------------------------------------------------

def _upload_to_supabase(sb: Client, audio_bytes: bytes, target_date: str, lang: str = "en") -> str:
    """Upload MP3 to Supabase Storage, return public URL."""
    file_path = f"{target_date}/briefing_{lang}.mp3"

    log.info("Uploading to audio-briefs/%s...", file_path)
    sb.storage.from_("audio-briefs").upload(
        file_path,
        audio_bytes,
        file_options={"content-type": "audio/mpeg", "upsert": "true"},
    )

    public_url = sb.storage.from_("audio-briefs").get_public_url(file_path)
    log.info("Uploaded successfully: %s", public_url)
    return public_url


def _upload_item_audio(sb: Client, audio_bytes: bytes, target_date: str, item_id: str) -> str:
    """Upload a single item's MP3 to Supabase Storage, return public URL.

    Path: {target_date}/items/{item_id}.mp3
    """
    file_path = f"{target_date}/items/{item_id}.mp3"

    log.info("Uploading item audio to audio-briefs/%s...", file_path)
    sb.storage.from_("audio-briefs").upload(
        file_path,
        audio_bytes,
        file_options={"content-type": "audio/mpeg", "upsert": "true"},
    )

    public_url = sb.storage.from_("audio-briefs").get_public_url(file_path)
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
    }
    if audio_url is not None:
        update_data["audio_url"] = audio_url

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
) -> bool:
    """Full pipeline: read brief -> generate script -> generate per-item audio -> generate narrative audio -> upload -> update DB.

    Generates both English and French audio when French is enabled.
    Per-item audio files are generated from structured item data and stored
    in raw_json["items"][n].audio_url for card-level playback.
    Narrative audio is generated from the full script for the transcript player.
    When from_db=True, fetches the brief from the briefs table instead of a local file.
    Returns True on success, False on failure.
    """
    from concurrent.futures import ThreadPoolExecutor, Future

    do_french = _french_audio_enabled()

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

    # 2. Build one shared coverage outline, then generate each language natively from it.
    _update_audio_status(sb, target_date, "generating_script")
    script_en: str | None = None
    script_fr: str | None = None
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
        if do_french:
            try:
                script_fr = _generate_and_prepare_script(
                    brief_json,
                    shared_outline=shared_outline,
                    outline_items=outline_items,
                    lang="fr",
                )
                log.info(
                    "French native script prepared from shared outline: %d sections, %d words, %d characters",
                    len(_split_script_sections(script_fr)),
                    len(script_fr.split()),
                    len(script_fr),
                )
            except Exception as exc:
                log.warning("French script generation failed (non-fatal): %s", exc)
    except Exception as exc:
        log.error("English script generation failed for %s: %s", target_date, exc)
        _update_audio_status(sb, target_date, "failed")
        return False

    # Save scripts locally
    en_script_path = OUTPUT_DIR / f"audio_script_{target_date}_en.txt"
    en_script_path.write_text(script_en, encoding="utf-8")
    log.info("EN script saved to %s", en_script_path.name)

    if script_fr:
        fr_script_path = OUTPUT_DIR / f"audio_script_{target_date}_fr.txt"
        fr_script_path.write_text(script_fr, encoding="utf-8")
        log.info("FR script saved to %s", fr_script_path.name)

    if script_only:
        log.info("Script-only mode — skipping TTS and upload")
        try:
            _update_briefs_table(
                sb, target_date,
                audio_url=None, script=script_en,
                audio_url_fr=None, script_fr=script_fr,
            )
        except Exception as exc:
            log.warning("Failed to update DB with scripts: %s", exc)
        return True

    # 3. Generate per-item audio (before narrative audio)
    _update_audio_status(sb, target_date, "generating_item_audio")
    voice_config = _get_voice_config()
    en_voice = voice_config["en"]["voice_id"]
    items = brief_json.get("items", [])

    en_item_audio_count = 0
    active_items = [item for item in items if not item.get("is_placeholder") and item.get("id")]
    log.info(
        "Generating per-item audio for %d of %d items (EN)",
        len(active_items),
        len(items),
    )

    for item in active_items:
        item_id = item["id"]
        # Skip items that already have audio from a previous run
        if item.get("audio_url"):
            log.info("Item %s already has audio_url — skipping", item_id)
            en_item_audio_count += 1
            continue

        item_script = _build_item_script(item)
        if not item_script or len(item_script) < 15:
            log.warning("Skipping item %s: script too short (%d chars)", item_id, len(item_script))
            continue

        try:
            audio_bytes = _generate_audio(item_script, en_voice)
            url = _upload_item_audio(sb, audio_bytes, target_date, item_id)
            item["audio_url"] = url
            en_item_audio_count += 1
            log.info(
                "Item audio generated for %s (%d chars): %s",
                item_id,
                len(item_script),
                url,
            )
        except Exception as exc:
            log.warning("Item audio failed for %s: %s", item_id, exc)

    # Save updated raw_json with per-item audio URLs to DB
    if en_item_audio_count > 0:
        try:
            sb.table("briefs").update({"raw_json": brief_json}).eq(
                "brief_date", target_date
            ).execute()
            log.info(
                "Updated raw_json with %d per-item audio URLs",
                en_item_audio_count,
            )
        except Exception as exc:
            log.warning("Failed to update raw_json with item audio URLs: %s", exc)

    # 4. Generate narrative audio concurrently
    _update_audio_status(sb, target_date, "generating_audio")
    audio_en: bytes | None = None
    audio_fr: bytes | None = None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            voice_config = _get_voice_config()
            en_voice = voice_config["en"]["voice_id"]
            fut_en_audio: Future[bytes] = pool.submit(_generate_audio, script_en, en_voice)
            fut_fr_audio: Future[bytes] | None = None
            if script_fr:
                fr_voice = voice_config["fr"]["voice_id"]
                fut_fr_audio = pool.submit(_generate_audio, script_fr, fr_voice, "fr")

            audio_en = fut_en_audio.result()
            if fut_fr_audio is not None:
                try:
                    audio_fr = fut_fr_audio.result()
                except Exception as exc:
                    log.warning("French TTS failed (non-fatal): %s", exc)
    except Exception as exc:
        log.error("English audio generation failed for %s: %s", target_date, exc)
        _update_audio_status(sb, target_date, "failed")
        try:
            _update_briefs_table(
                sb, target_date,
                audio_url=None, script=script_en,
                script_fr=script_fr,
            )
            log.info("Scripts saved to DB despite TTS failure")
        except Exception as db_exc:
            log.warning("Failed to update DB with scripts: %s", db_exc)
        return False

    # Save MP3s locally
    en_audio_path = OUTPUT_DIR / f"brief_audio_{target_date}_en.mp3"
    en_audio_path.write_bytes(audio_en)
    log.info("EN audio saved locally to %s", en_audio_path.name)

    if audio_fr:
        fr_audio_path = OUTPUT_DIR / f"brief_audio_{target_date}_fr.mp3"
        fr_audio_path.write_bytes(audio_fr)
        log.info("FR audio saved locally to %s", fr_audio_path.name)

    # 5. Upload narrative audio to Supabase Storage
    _update_audio_status(sb, target_date, "uploading")
    audio_url_en = None
    audio_url_fr = None

    try:
        audio_url_en = _upload_to_supabase(sb, audio_en, target_date, lang="en")
    except Exception as exc:
        log.error("EN upload failed for %s: %s — retrying once...", target_date, exc)
        try:
            audio_url_en = _upload_to_supabase(sb, audio_en, target_date, lang="en")
        except Exception as exc2:
            log.error("EN retry failed: %s — audio saved locally only", exc2)

    if audio_fr:
        try:
            audio_url_fr = _upload_to_supabase(sb, audio_fr, target_date, lang="fr")
        except Exception as exc:
            log.warning("FR upload failed for %s: %s — retrying once...", target_date, exc)
            try:
                audio_url_fr = _upload_to_supabase(sb, audio_fr, target_date, lang="fr")
            except Exception as exc2:
                log.warning("FR retry failed: %s — audio saved locally only", exc2)

    # 6. Update database
    try:
        _update_briefs_table(
            sb, target_date,
            audio_url=audio_url_en, script=script_en,
            audio_url_fr=audio_url_fr, script_fr=script_fr,
        )
    except Exception as exc:
        log.error("Failed to update DB for %s: %s", target_date, exc)
        _update_audio_status(sb, target_date, "failed")
        return False

    # 7. Revalidate frontend cache so audio player appears immediately
    _revalidate_frontend(target_date)

    log.info("Audio brief complete for %s (EN=%s, FR=%s)",
             target_date,
             "ok" if audio_url_en else "failed",
             "ok" if audio_url_fr else ("skipped" if not do_french else "failed"))
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

        success_count = 0
        fail_count = 0

        for brief_path in brief_files:
            # Extract date from filename: brief_YYYY-MM-DD.json
            target_date = brief_path.stem.replace("brief_", "")
            try:
                date.fromisoformat(target_date)
            except ValueError:
                log.warning("Skipping non-date file: %s", brief_path.name)
                continue

            ok = generate_audio_brief(sb, target_date, script_only=args.script_only)
            if ok:
                success_count += 1
            else:
                fail_count += 1

        log.info("=" * 60)
        log.info(
            "Backfill complete: %d succeeded, %d failed, %d total",
            success_count,
            fail_count,
            success_count + fail_count,
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
        )
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
