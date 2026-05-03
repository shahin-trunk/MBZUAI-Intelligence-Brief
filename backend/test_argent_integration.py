#!/usr/bin/env python3
"""
Integration test: Argent TTS compatibility endpoint.

Tests the elevenlabs_ compat endpoint on the live Argent TTS deployment
at https://txt2sph.audarai.com, then exercises _generate_audio from
generate_audio.py with VOICE_BASE_URL pointed at Argent.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ARGENT_BASE = os.getenv("VOICE_BASE_URL", "https://txt2sph.audarai.com/elevenlabs")
# Argent TTS has no API key configured — any value (or empty) works
ARGENT_API_KEY = os.getenv("VOICE_API_KEY", "test-key-not-required")
EN_VOICE_ID = "Fahco4VZzobUeiPqni1S"   # Callum (English)
FR_VOICE_ID = "c365oriviHmAhyLhpuN6"   # Hope    (French)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
INFO = "\033[94mINFO\033[0m"

test_count = 0
pass_count = 0
fail_count = 0


def _check(label: str, condition: bool, detail: str = "") -> None:
    global test_count, pass_count, fail_count
    test_count += 1
    if condition:
        pass_count += 1
        print(f"  {PASS}  {label}  {detail}")
    else:
        fail_count += 1
        print(f"  {FAIL}  {label}  {detail}")


def _info(msg: str) -> None:
    print(f"  {INFO}  {msg}")


# ---------------------------------------------------------------------------
# Test 1: Direct HTTP — English voice
# ---------------------------------------------------------------------------
def test_english_voice() -> None:
    print("\n--- Test 1: English voice (Callum) ---")
    url = f"{ARGENT_BASE}/v1/text-to-speech/{EN_VOICE_ID}"
    payload = {
        "text": "Good morning. This is a test of the Argent text to speech service. The system is working correctly and producing high quality audio output.",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.3, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": ARGENT_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=120.0)
    _check("HTTP 200", response.status_code == 200, f"status={response.status_code}")
    _check("Content-Type audio/mpeg", "audio/mpeg" in response.headers.get("content-type", ""))
    _check("Non-empty body", len(response.content) > 500, f"{len(response.content)} bytes")
    _check("MP3 header", response.content[:3] == b"\xff\xfb" or response.content[:2] == b"\xff\xf3" or b"ID3" in response.content[:3],
           f"first bytes: {response.content[:8].hex()}")

    # Save for listening
    path = Path("/tmp/argent_test_en.mp3")
    path.write_bytes(response.content)
    _info(f"Saved to {path} ({len(response.content)} bytes)")


# ---------------------------------------------------------------------------
# Test 2: Direct HTTP — French voice
# ---------------------------------------------------------------------------
def test_french_voice() -> None:
    print("\n--- Test 2: French voice (Hope) ---")
    url = f"{ARGENT_BASE}/v1/text-to-speech/{FR_VOICE_ID}"
    payload = {
        "text": "Bonjour. Ceci est un test du service de synthèse vocale Argent. Le système fonctionne correctement et produit un audio de haute qualité.",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.3, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": ARGENT_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=120.0)
    _check("HTTP 200", response.status_code == 200, f"status={response.status_code}")
    _check("Non-empty body", len(response.content) > 500, f"{len(response.content)} bytes")
    _check("MP3 header", response.content[:3] == b"\xff\xfb" or response.content[:2] == b"\xff\xf3" or b"ID3" in response.content[:3])

    path = Path("/tmp/argent_test_fr.mp3")
    path.write_bytes(response.content)
    _info(f"Saved to {path} ({len(response.content)} bytes)")


# ---------------------------------------------------------------------------
# Test 3: SSML stripping
# ---------------------------------------------------------------------------
def test_ssml_stripping() -> None:
    print("\n--- Test 3: SSML break-tag stripping (defense-in-depth) ---")
    url = f"{ARGENT_BASE}/v1/text-to-speech/{EN_VOICE_ID}"
    payload = {
        "text": 'First point.<break time="0.5s"/>Second point.<break time="1.0s"/>Third point.',
        "model_id": "eleven_multilingual_v2",
    }
    headers = {
        "xi-api-key": ARGENT_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=120.0)
    _check("HTTP 200 (SSML stripped, not rejected)", response.status_code == 200, f"status={response.status_code}")
    if response.status_code == 422:
        _info(f"Error detail: {response.text[:200]}")
    _check("Valid audio produced", len(response.content) > 500, f"{len(response.content)} bytes")

    path = Path("/tmp/argent_test_ssml.mp3")
    path.write_bytes(response.content)
    _info(f"Saved to {path} ({len(response.content)} bytes)")


# ---------------------------------------------------------------------------
# Test 4: Invalid voice_id — graceful rejection
# ---------------------------------------------------------------------------
def test_invalid_voice() -> None:
    print("\n--- Test 4: Invalid voice_id rejection ---")
    url = f"{ARGENT_BASE}/v1/text-to-speech/nonexistent123"
    payload = {"text": "Test."}
    headers = {
        "xi-api-key": ARGENT_API_KEY,
        "Content-Type": "application/json",
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
    _check("HTTP 422", response.status_code == 422, f"status={response.status_code}")
    try:
        import json as _json
        raw_text = response.text
        body = _json.loads(raw_text)
        # Accept both formats: ElevenLabs {"detail": {"status": ...}} and
        # the legacy wrapped format {"error": {"status": ...}}
        detail = body.get("detail") or body.get("error") or body
        _check("status=invalid_voice",
               isinstance(detail, dict) and detail.get("status") == "invalid_voice",
               f"body={body}")
    except Exception as exc:
        _check("JSON error body", False, f"raw={response.text[:100]} exc={exc}")


# ---------------------------------------------------------------------------
# Test 5: Longer podcast-style text (realistic workload)
# ---------------------------------------------------------------------------
def test_longer_text() -> None:
    print("\n--- Test 5: Podcast-style longer text ---")
    text = (
        "Welcome to the MBZUAI Intelligence Brief. "
        "Today's top story comes from the Middle East, where significant diplomatic "
        "developments are reshaping regional dynamics. "
        "In technology, a major breakthrough in quantum computing has implications "
        "for cryptography and national security. "
        "Turning to energy markets, oil prices remain volatile amid ongoing "
        "geopolitical tensions. "
        "And finally, in climate news, new satellite data reveals accelerating "
        "ice melt in the Arctic, raising concerns among scientists worldwide."
    )
    url = f"{ARGENT_BASE}/v1/text-to-speech/{EN_VOICE_ID}"
    payload = {"text": text, "model_id": "eleven_multilingual_v2"}
    headers = {
        "xi-api-key": ARGENT_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=180.0)
    _check("HTTP 200", response.status_code == 200, f"status={response.status_code}")
    _check("Large audio output", len(response.content) > 5000,
           f"{len(response.content)} bytes ({len(text)} chars input)")
    _check("MP3 header", b"ID3" in response.content[:3] or response.content[:2] == b"\xff\xf3")

    path = Path("/tmp/argent_test_long.mp3")
    path.write_bytes(response.content)
    _info(f"Saved to {path} ({len(response.content)} bytes)")


# ---------------------------------------------------------------------------
# Test 6: generate_audio.py _generate_audio function end-to-end
# ---------------------------------------------------------------------------
def test_generate_audio_function() -> None:
    print("\n--- Test 6: generate_audio.py _generate_audio() end-to-end ---")
    _info("Importing generate_audio module...")

    # Set env vars BEFORE importing (module reads at import time)
    os.environ["VOICE_BASE_URL"] = ARGENT_BASE
    os.environ["VOICE_API_KEY"] = ARGENT_API_KEY
    os.environ["ENABLE_SSML_BREAK_MARKERS"] = "false"

    # Import the module
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import generate_audio

    script = (
        "Welcome to today's intelligence briefing. "
        "We begin with developments in the Gulf region, where major economic "
        "initiatives are driving transformation across multiple sectors. "
        "In defense and security, new partnerships are strengthening regional "
        "cooperation frameworks. "
        "Our technology segment covers advances in artificial intelligence "
        "and their implications for governance and industry."
    )

    _info(f"Calling _generate_audio with {len(script)} chars of script...")

    try:
        audio_bytes = generate_audio._generate_audio(
            script=script,
            voice_id=EN_VOICE_ID,
            lang="en",
        )
        _check("Audio bytes returned", len(audio_bytes) > 1000, f"{len(audio_bytes)} bytes")
        _check("MP3 header valid", b"ID3" in audio_bytes[:3] or audio_bytes[:2] == b"\xff\xf3")
        _info(f"VOICE_BASE_URL used: {generate_audio.VOICE_BASE_URL}")
        _info(f"ENABLE_SSML_BREAK_MARKERS: {generate_audio.ENABLE_SSML_BREAK_MARKERS}")

        path = Path("/tmp/argent_test_generate_audio.mp3")
        path.write_bytes(audio_bytes)
        _info(f"Saved to {path} ({len(audio_bytes)} bytes)")
    except Exception as exc:
        _check("generate_audio succeeded", False, str(exc))


# ---------------------------------------------------------------------------
# Test 7: Verify SSML is disabled in prompts
# ---------------------------------------------------------------------------
def test_prompt_stripping() -> None:
    print("\n--- Test 7: Prompt SSML stripping verification ---")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import generate_audio

    # Check that the toggle is set
    _check("ENABLE_SSML_BREAK_MARKERS is False",
           generate_audio.ENABLE_SSML_BREAK_MARKERS is False,
           f"value={generate_audio.ENABLE_SSML_BREAK_MARKERS}")

    # Check that VOICE_BASE_URL points to Argent
    _check("VOICE_BASE_URL points to Argent",
           "txt2sph.audarai.com" in generate_audio.VOICE_BASE_URL or "8003" in generate_audio.VOICE_BASE_URL,
           f"value={generate_audio.VOICE_BASE_URL}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("  Argent TTS — Integration Test Suite")
    print(f"  VOICE_BASE_URL = {ARGENT_BASE}")
    print(f"  VOICE_API_KEY  = {'<set>' if ARGENT_API_KEY else '<empty>'}")
    print("=" * 70)

    # Quick availability check
    try:
        r = httpx.get(f"{ARGENT_BASE}/../health", timeout=10.0)
        _info(f"TTS health: {r.status_code} — {r.text[:100]}")
    except Exception as exc:
        _info(f"TTS health check failed: {exc}")

    test_english_voice()
    test_french_voice()
    test_ssml_stripping()
    test_invalid_voice()
    test_longer_text()
    test_generate_audio_function()
    test_prompt_stripping()

    # Summary
    print("\n" + "=" * 70)
    print(f"  Results: {pass_count}/{test_count} passed, {fail_count} failed")
    if fail_count == 0:
        print(f"  {PASS}  All tests passed!")
    else:
        print(f"  {FAIL}  {fail_count} test(s) failed")
    print("=" * 70)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
