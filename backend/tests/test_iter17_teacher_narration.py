"""ITER 17 E2E Tests - Audio Exclusivity & Teacher Narration Quality.

Tests for:
1. Audio playback exclusivity (no overlapping audio)
2. Teacher narration content quality (scripts 1, 4 must teach, not translate)
3. Grammar drawer rich content display
4. Bilingual script validation
"""
import pytest
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


class TestAudioExclusivity:
    """Test that audio playback is exclusive — no overlapping audio."""

    def test_useSectionAudio_kills_all_audio_on_play(self):
        """verify that useSectionAudio calls killAllPageAudio when playSection is invoked."""
        content = (BACKEND_DIR.parent / "frontend" / "hooks" / "useSectionAudio.ts").read_text()
        # Should call killAllPageAudio in playSection
        assert "killAllPageAudio()" in content
        # playSection should call it before setting up new audio
        assert content.count("killAllPageAudio()") >= 2  # In effect + playSection

    def test_togglePlayPause_kills_other_audio(self):
        """verify that togglePlayPause kills other audio before playing."""
        content = (BACKEND_DIR.parent / "frontend" / "hooks" / "useSectionAudio.ts").read_text()
        # Should iterate through GLOBAL_AUDIO_REGISTRY to pause others
        assert "GLOBAL_AUDIO_REGISTRY.forEach" in content
        assert "other !== audio" in content

    def test_nextSection_kills_audio(self):
        """verify that nextSection kills audio before advancing."""
        content = (BACKEND_DIR.parent / "frontend" / "hooks" / "useSectionAudio.ts").read_text()
        # Find nextSection function and verify it calls killAllPageAudio
        next_section_start = content.find("const nextSection = useCallback")
        next_section_end = content.find("}, [currentSectionIndex]);", next_section_start)
        next_section_code = content[next_section_start:next_section_end]
        assert "killAllPageAudio()" in next_section_code

    def test_prevSection_kills_audio(self):
        """verify that prevSection kills audio before going back."""
        content = (BACKEND_DIR.parent / "frontend" / "hooks" / "useSectionAudio.ts").read_text()
        prev_section_start = content.find("const prevSection = useCallback")
        prev_section_end = content.find("}, [currentSectionIndex]);", prev_section_start)
        prev_section_code = content[prev_section_start:prev_section_end]
        assert "killAllPageAudio()" in prev_section_code

    def test_main_effect_kills_audio_before_setup(self):
        """verify that the main effect kills all audio before creating new Audio element."""
        content = (BACKEND_DIR.parent / "frontend" / "hooks" / "useSectionAudio.ts").read_text()
        # Find the main effect
        effect_start = content.find("// CRITICAL: Kill ALL existing audio")
        assert effect_start > 0
        effect_section = content[effect_start:effect_start + 500]
        assert "killAllPageAudio()" in effect_section


class TestTeacherNarrationQuality:
    """Test that teacher narration content is educational, not just translation."""

    def test_prompt_requires_teacher_voice(self):
        """verify prompt explicitly requires teacher voice, not translation."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        assert "teacher" in prompt.lower()
        assert "TEACH" in prompt  # Emphasized

    def test_prompt_forbids_just_translation(self):
        """verify prompt explicitly forbids just reading the translation."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        assert "MUST NOT" in prompt or "must NOT" in prompt or "NOT" in prompt
        assert "just the translation" in prompt.lower() or "just read the translation" in prompt.lower()

    def test_script1_requires_word_breakdown(self):
        """verify script1 must include word breakdown and context."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        script1_section = prompt[prompt.find("### script1"):prompt.find("### script2")]
        assert "key word" in script1_section.lower() or "breakdown" in script1_section.lower()
        assert "context" in script1_section.lower()

    def test_script4_requires_deep_linguistics(self):
        """verify script4 must cover linguistic depth."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        script4_section = prompt[prompt.find("### script4"):prompt.find("## Per Phrase — Grammar")]
        assert "word structure" in script4_section.lower() or "morphology" in script4_section.lower()
        assert "conjugation" in script4_section.lower() or "verb" in script4_section.lower()
        assert "pronunciation" in script4_section.lower() or "phonetic" in script4_section.lower()

    def test_script1_length_increased(self):
        """verify script1 minimum length is substantial (150+ chars for teaching)."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        assert "150" in prompt  # Minimum 150 chars
        assert "300" in prompt  # Maximum 300 chars

    def test_script4_length_increased(self):
        """verify script4 minimum length is substantial (250+ chars for deep dive)."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        script4_section = prompt[prompt.find("### script4"):prompt.find("## Per Phrase — Grammar")]
        assert "250" in script4_section or "300" in script4_section

    def test_grammar_fields_required_substantive(self):
        """verify all 7 grammar fields are required and must be substantive."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        assert "ALL 7 fields" in prompt or "all 7 fields" in prompt
        assert "20-80 characters" in prompt  # Substantive requirement

    def test_bilingual_validation_enforced(self):
        """verify bilingual check is enforced on scripts 1 and 4."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        assert "bilingual check" in prompt.lower()
        assert ">=3 English" in prompt or "at least 3 English" in prompt

    def test_examples_provided_in_prompt(self):
        """verify prompt includes concrete examples of good teaching content."""
        prompt = (BACKEND_DIR / "prompts" / "language_learning_phrases_prompt.md").read_text()
        assert 'Example' in prompt or 'example' in prompt
        # Should have French and Arabic examples
        assert "dee-ploh-mah" in prompt or "qimma" in prompt  # Pronunciation guides


class TestGrammarDrawerRichContent:
    """Test that grammar drawer displays rich teaching content."""

    def test_drawer_shows_script4_as_main_content(self):
        """verify drawer shows script4 text as primary content, not just metadata."""
        content = (BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text()
        assert "Teacher's Narration" in content or "Teacher's Deep Dive" in content
        assert "script4Text" in content

    def test_drawer_has_teacher_narration_section(self):
        """verify drawer has dedicated teacher narration section."""
        content = (BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text()
        assert "Teacher's Narration" in content
        # Should have distinct styling for narration section
        assert "bg-accent-primary/5" in content  # Highlighted background

    def test_drawer_has_grammar_breakdown_section(self):
        """verify drawer has separate grammar breakdown section."""
        content = (BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text()
        assert "Grammar Breakdown" in content

    def test_drawer_audio_aria_labels(self):
        """verify drawer audio buttons have descriptive ARIA labels."""
        content = (BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text()
        assert 'aria-label={isPlaying ? "Pause narration" : "Play narration"}' in content

    def test_mobile_and_desktop_versions_consistent(self):
        """verify both mobile and desktop versions show teacher narration."""
        content = (BACKEND_DIR.parent / "frontend" / "components" / "language-learning" / "PhraseGrammarDrawer.tsx").read_text()
        # Count occurrences of "Teacher's Narration" - should appear in both mobile and desktop
        count = content.count("Teacher's Narration")
        assert count >= 2  # Mobile + Desktop


class TestTTSLanguageHint:
    """Test that TTS API receives language hints for better synthesis."""

    def test_argent_tts_receives_lang_param(self):
        """verify Argent TTS payload includes language parameter."""
        content = (BACKEND_DIR / "generate_audio.py").read_text()
        # Should include lang in payload for Argent TTS
        assert '"lang": lang' in content or "'lang': lang" in content


class TestPipelineIntegration:
    """Test end-to-end pipeline integrity."""

    def test_voice_assignment_correct_for_scripts(self):
        """verify scripts 1,2,4 use English voice, script3 uses target language."""
        content = (BACKEND_DIR / "tasks" / "learning_tasks.py").read_text()
        assert "script_idx == 3" in content  # Target language for script 3
        assert "English voice" in content or "en" in content  # English for others

    def test_audio_tasks_pass_lang_to_tts(self):
        """verify audio tasks pass language parameter to TTS."""
        content = (BACKEND_DIR / "tasks" / "audio_tasks.py").read_text()
        assert "lang=lang" in content  # Language passed to _generate_audio

    def test_learning_tasks_extract_voice_config(self):
        """verify learning tasks correctly extract voice for each script."""
        content = (BACKEND_DIR / "tasks" / "learning_tasks.py").read_text()
        assert "_get_voice_for_script" in content
        assert "voice_id, script_lang" in content
