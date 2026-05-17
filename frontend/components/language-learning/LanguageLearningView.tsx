"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Pause, Loader2 } from "lucide-react";
import type { BriefItem, LearningPhrase } from "@/lib/types/brief";
import { useSectionAudio } from "@/hooks/useSectionAudio";
import LearningHeader from "./LearningHeader";
import PhraseCard from "./PhraseCard";
import PhraseGrammarDrawer from "./PhraseGrammarDrawer";
import PhraseNavigationDots from "./PhraseNavigationDots";
import ImmersiveAudioController from "./ImmersiveAudioController";

type LearnLang = "fr" | "ar";

interface LanguageLearningViewProps {
  item: BriefItem;
  briefDate: string;
  slideIndex: number;
}

export default function LanguageLearningView({
  item,
  briefDate,
  slideIndex,
}: LanguageLearningViewProps) {
  /* ------------------------------------------------------------------ */
  /*  State                                                              */
  /* ------------------------------------------------------------------ */
  const [language, setLanguage] = useState<LearnLang>(
    item.learning_fr ? "fr" : "ar",
  );
  const [isPaused, setIsPaused] = useState(false);
  const [isLessonComplete, setIsLessonComplete] = useState(false);
  const [completedPhrases, setCompletedPhrases] = useState<Set<number>>(new Set());
  const [expandedPhraseGrammar, setExpandedPhraseGrammar] = useState<number | null>(null);

  const hasFr = Boolean(item.learning_fr);
  const hasAr = Boolean(item.learning_ar);

  const currentContent =
    language === "fr" ? item.learning_fr : item.learning_ar;

  const phrases: LearningPhrase[] = currentContent?.phrases ?? [];

  /* ------------------------------------------------------------------ */
  /*  Flatten phrases into script-level audio URLs for useSectionAudio   */
  /*  Order: [p0.s1, p0.s2, p0.s3, p1.s1, p1.s2, p1.s3, ...]          */
  /* ------------------------------------------------------------------ */
  const scriptUrls = useMemo(
    () =>
      phrases.flatMap((p) => [p.audio_url_1, p.audio_url_2, p.audio_url_3]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [phrases.map((p) => `${p.audio_url_1}|${p.audio_url_2}|${p.audio_url_3}`).join("|")],
  );

  const scriptDurations = useMemo(
    () => {
      const totalScripts = phrases.length * 3;
      const perScript = phrases.length > 0
        ? (phrases.reduce((sum, p) => sum + (p.estimated_duration_seconds ?? 30), 0) / phrases.length)
        : 30;
      return Array(totalScripts).fill(perScript / 3);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [phrases.map((p) => p.estimated_duration_seconds).join("|")],
  );

  /* ------------------------------------------------------------------ */
  /*  Audio callbacks                                                    */
  /* ------------------------------------------------------------------ */
  const handleSectionComplete = useCallback((index: number) => {
    const phraseIdx = Math.floor(index / 3);
    setCompletedPhrases((prev) => {
      const next = new Set(prev);
      next.add(phraseIdx);
      return next;
    });
  }, []);

  const handleAllComplete = useCallback(() => {
    setIsLessonComplete(true);
  }, []);

  /* ------------------------------------------------------------------ */
  /*  Audio hook                                                         */
  /* ------------------------------------------------------------------ */
  const hasAnyAudio = scriptUrls.some((u) => !!u);
  const audio = useSectionAudio(scriptUrls, {
    autoAdvance: true,
    estimatedDurations: scriptDurations,
    onSectionComplete: handleSectionComplete,
    onAllComplete: handleAllComplete,
  });

  /* ------------------------------------------------------------------ */
  /*  Derive current phrase and script from audio index                  */
  /* ------------------------------------------------------------------ */
  const currentPhraseIndex = Math.floor(audio.currentSectionIndex / 3);
  const currentScriptIndex = (audio.currentSectionIndex % 3) + 1; // 1, 2, or 3
  const activePhrase = phrases[currentPhraseIndex];

  /* ------------------------------------------------------------------ */
  /*  One-shot auto-play on mount                                        */
  /* ------------------------------------------------------------------ */
  const hasStartedRef = useRef(false);
  const audioRef = useRef(audio);
  audioRef.current = audio;
  useEffect(() => {
    if (!hasStartedRef.current && hasAnyAudio && phrases.length > 0) {
      hasStartedRef.current = true;
      const t = setTimeout(() => {
        audioRef.current.playSection(0);
      }, 1200);
      return () => clearTimeout(t);
    }
  }, [hasAnyAudio, phrases.length, language]);

  /* ------------------------------------------------------------------ */
  /*  WakeLock                                                           */
  /* ------------------------------------------------------------------ */
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function acquire() {
      try {
        if ("wakeLock" in navigator && !wakeLockRef.current) {
          const sentinel = await navigator.wakeLock.request("screen");
          if (cancelled) {
            sentinel.release();
            return;
          }
          wakeLockRef.current = sentinel;
          sentinel.addEventListener("release", () => {
            wakeLockRef.current = null;
          });
        }
      } catch {
        /* WakeLock not available or denied — safe to ignore */
      }
    }

    async function release() {
      try {
        await wakeLockRef.current?.release();
        wakeLockRef.current = null;
      } catch {
        /* ignore */
      }
    }

    if (audio.isPlaying && !isPaused && !isLessonComplete) {
      acquire();
    } else {
      release();
    }

    return () => {
      cancelled = true;
      release();
    };
  }, [audio.isPlaying, isPaused, isLessonComplete]);

  /* ------------------------------------------------------------------ */
  /*  Tap-to-pause                                                       */
  /* ------------------------------------------------------------------ */
  const handleTapToggle = useCallback(() => {
    if (isLessonComplete) return;

    if (audio.isPlaying && !isPaused) {
      audio.pause();
      setIsPaused(true);
    } else if (isPaused) {
      audio.togglePlayPause();
      setIsPaused(false);
    }
  }, [audio, isPaused, isLessonComplete]);

  /* ------------------------------------------------------------------ */
  /*  Language change                                                     */
  /* ------------------------------------------------------------------ */
  const handleLanguageChange = useCallback(
    (lang: LearnLang) => {
      audio.pause();
      setLanguage(lang);
      setCompletedPhrases(new Set());
      setIsLessonComplete(false);
      setIsPaused(false);
      setExpandedPhraseGrammar(null);
      hasStartedRef.current = false;
    },
    [audio],
  );

  /* ------------------------------------------------------------------ */
  /*  Replay                                                             */
  /* ------------------------------------------------------------------ */
  const handleReplay = useCallback(() => {
    setIsLessonComplete(false);
    setCompletedPhrases(new Set());
    setIsPaused(false);
    setExpandedPhraseGrammar(null);
    audio.playSection(0);
  }, [audio]);

  /* ------------------------------------------------------------------ */
  /*  Phrase navigation                                                   */
  /* ------------------------------------------------------------------ */
  const handlePhraseSelect = useCallback(
    (phraseIdx: number) => {
      const scriptIdx = phraseIdx * 3; // Start at script 1 of that phrase
      audio.playSection(scriptIdx);
      setIsPaused(false);
      setExpandedPhraseGrammar(null);
    },
    [audio],
  );

  /* ------------------------------------------------------------------ */
  /*  Grammar drawer toggle                                               */
  /* ------------------------------------------------------------------ */
  const handleGrammarToggle = useCallback(
    (phraseIdx: number | null) => {
      if (phraseIdx !== null) {
        // Play script 4 audio if available
        const phrase = phrases[phraseIdx];
        if (phrase?.audio_url_4) {
          // Grammar drawer plays its own audio, not through main sequence
        }
      }
      setExpandedPhraseGrammar(phraseIdx);
    },
    [phrases],
  );

  /* ------------------------------------------------------------------ */
  /*  Derived                                                            */
  /* ------------------------------------------------------------------ */
  const backHref = `/brief/${briefDate}?slideIndex=${slideIndex}`;

  /* ------------------------------------------------------------------ */
  /*  Loading: generation in progress                                    */
  /* ------------------------------------------------------------------ */
  const isGenerating = !hasAnyAudio && phrases.length === 0;
  if (isGenerating) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-bg-primary px-6">
        <div className="mx-auto max-w-md text-center">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-accent-primary" />
          <h1 className="font-display text-xl text-text-primary">
            Generating learning content...
          </h1>
          <p className="mt-3 font-body text-sm text-text-secondary">
            Phrases and audio are being generated in the background. Please check back shortly.
          </p>
          <a
            href={backHref}
            className="mt-6 inline-block rounded-full border border-rule bg-bg-surface px-5 py-2.5 font-ui text-sm text-accent-primary transition-colors hover:bg-bg-surface-2"
          >
            Back to briefing
          </a>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Fallback: no content                                               */
  /* ------------------------------------------------------------------ */
  if (!currentContent || phrases.length === 0) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-bg-primary px-6">
        <div className="mx-auto max-w-md text-center">
          <h1 className="font-display text-xl text-text-primary">
            Content not available
          </h1>
          <p className="mt-3 font-body text-sm text-text-secondary">
            Learning content for{" "}
            {language === "fr" ? "French" : "Arabic"} is not available for
            this item.
          </p>
          <a
            href={backHref}
            className="mt-6 inline-block rounded-full border border-rule bg-bg-surface px-5 py-2.5 font-ui text-sm text-accent-primary transition-colors hover:bg-bg-surface-2"
          >
            Back to briefing
          </a>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Main render                                                        */
  /* ------------------------------------------------------------------ */
  return (
    <div
      className="min-h-[100dvh] flex flex-col bg-bg-primary"
      dir={language === "ar" ? "rtl" : "ltr"}
    >
      {/* Top progress bar */}
      <ImmersiveAudioController
        overallProgress={audio.overallProgress}
        isLessonComplete={isLessonComplete}
      />

      {/* Header: back + counter + language toggle */}
      <LearningHeader
        backHref={backHref}
        headline={item.headline}
        language={language}
        onLanguageChange={handleLanguageChange}
        hasFr={hasFr}
        hasAr={hasAr}
        currentSection={currentPhraseIndex + 1}
        totalSections={phrases.length}
      />

      {/* Phrase navigation dots */}
      <div className="flex justify-center py-3">
        <PhraseNavigationDots
          totalPhrases={phrases.length}
          currentPhraseIndex={currentPhraseIndex}
          completedPhrases={completedPhrases}
          onPhraseSelect={handlePhraseSelect}
        />
      </div>

      {/* Main content — tap to pause zone */}
      <div
        className="relative flex-1 flex flex-col items-center justify-start px-6 sm:px-10 lg:px-0 py-8 sm:py-12 lg:py-16 w-full mx-auto sm:max-w-[560px] lg:max-w-[620px] cursor-default select-none"
        onClick={handleTapToggle}
        role="button"
        tabIndex={-1}
      >
        {/* Pause indicator */}
        {isPaused && !isLessonComplete && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-bg-surface/60 border border-rule/20 animate-in fade-in duration-200">
              <Pause className="h-6 w-6 text-text-muted" />
            </div>
          </div>
        )}

        {/* Active phrase card */}
        {!isLessonComplete && activePhrase && (
          <PhraseCard
            key={`${activePhrase.id}-${currentScriptIndex}`}
            phrase={activePhrase}
            language={language}
            scriptIndex={currentScriptIndex as 1 | 2 | 3}
            currentTime={audio.currentTime}
            duration={audio.duration}
            isPlaying={audio.isPlaying}
            onExpandGrammar={() =>
              handleGrammarToggle(
                expandedPhraseGrammar === currentPhraseIndex
                  ? null
                  : currentPhraseIndex
              )
            }
            showGrammarTrigger={
              currentScriptIndex === 3 && !!activePhrase.script4
            }
          />
        )}

        {/* Grammar drawer for expanded phrase */}
        {expandedPhraseGrammar !== null && phrases[expandedPhraseGrammar] && (
          <PhraseGrammarDrawer
            grammar={phrases[expandedPhraseGrammar].grammar}
            script4AudioUrl={phrases[expandedPhraseGrammar].audio_url_4}
            script4Text={phrases[expandedPhraseGrammar].script4}
            isOpen={true}
            onToggle={() => handleGrammarToggle(null)}
            language={language}
          />
        )}

        {/* Completion state */}
        {isLessonComplete && (
          <div className="text-center">
            <h2 className="font-display text-2xl text-text-primary mb-4">
              Lesson Complete!
            </h2>
            <p className="font-body text-sm text-text-secondary mb-6">
              You&apos;ve practiced all {phrases.length} phrases.
            </p>
            <button
              onClick={handleReplay}
              className="rounded-full bg-accent-primary px-6 py-3 font-ui text-sm text-white transition-colors hover:bg-accent-primary/90"
            >
              Replay Lesson
            </button>
            <a
              href={backHref}
              className="mt-4 ml-4 inline-block rounded-full border border-rule bg-bg-surface px-5 py-2.5 font-ui text-sm text-accent-primary transition-colors hover:bg-bg-surface-2"
            >
              Back to briefing
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
