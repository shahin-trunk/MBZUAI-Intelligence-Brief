"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Pause, Loader2, Sparkles } from "lucide-react";
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
  const [showCelebration, setShowCelebration] = useState(false);
  const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(null);

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
    setShowCelebration(true);
    setTimeout(() => setShowCelebration(false), 3000);
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

  // Script-level progress within the phrase (0-1)
  const scriptProgress = useMemo(() => {
    const scriptStartIndex = currentPhraseIndex * 3;
    const scriptsInPhrase = 3;
    const completedScripts = audio.currentSectionIndex - scriptStartIndex;
    const currentScriptFraction = audio.sectionProgress;
    return (completedScripts + currentScriptFraction) / scriptsInPhrase;
  }, [currentPhraseIndex, audio.currentSectionIndex, audio.sectionProgress]);

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
  /*  Swipe gesture handling                                             */
  /* ------------------------------------------------------------------ */
  const touchStartRef = useRef<{ x: number; y: number } | null>(null);
  const SWIPE_THRESHOLD = 50;

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    touchStartRef.current = {
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
    };
  }, []);

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    if (!touchStartRef.current) return;

    const deltaX = e.changedTouches[0].clientX - touchStartRef.current.x;
    const deltaY = e.changedTouches[0].clientY - touchStartRef.current.y;

    // Only handle horizontal swipes (more horizontal than vertical movement)
    if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > SWIPE_THRESHOLD) {
      if (deltaX < 0) {
        // Swipe left -> next phrase
        setSwipeDirection("left");
        const nextIdx = Math.min(currentPhraseIndex + 1, phrases.length - 1);
        handlePhraseSelect(nextIdx);
      } else {
        // Swipe right -> previous phrase
        setSwipeDirection("right");
        const prevIdx = Math.max(currentPhraseIndex - 1, 0);
        handlePhraseSelect(prevIdx);
      }

      // Clear swipe feedback after animation
      setTimeout(() => setSwipeDirection(null), 300);
    }

    touchStartRef.current = null;
  }, [currentPhraseIndex, phrases.length, handlePhraseSelect]);

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
      setShowCelebration(false);
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
    setShowCelebration(false);
    audio.playSection(0);
  }, [audio]);

  /* ------------------------------------------------------------------ */
  /*  Grammar drawer toggle                                               */
  /* ------------------------------------------------------------------ */
  const handleGrammarToggle = useCallback(
    (phraseIdx: number | null) => {
      setExpandedPhraseGrammar(phraseIdx);
    },
    [],
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
        currentScriptIndex={currentScriptIndex}
        speed={audio.speed}
        onSpeedChange={audio.cycleSpeed}
        isLoading={audio.isLoading}
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
      <div className="flex justify-center py-3 sm:py-4">
        <PhraseNavigationDots
          totalPhrases={phrases.length}
          currentPhraseIndex={currentPhraseIndex}
          currentScriptIndex={currentScriptIndex}
          completedPhrases={completedPhrases}
          scriptProgress={scriptProgress}
          onPhraseSelect={handlePhraseSelect}
        />
      </div>

      {/* Main content — tap to pause zone, swipe for navigation */}
      <div
        className="relative flex-1 flex flex-col items-center justify-start px-6 sm:px-10 lg:px-0 py-6 sm:py-10 lg:py-12 w-full mx-auto sm:max-w-[560px] lg:max-w-[620px] cursor-default select-none touch-pan-y"
        onClick={handleTapToggle}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        role="button"
        tabIndex={-1}
      >
        {/* Celebration overlay */}
        {showCelebration && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20 animate-in fade-in duration-500">
            <div className="relative">
              {/* Sparkle burst effect */}
              <div className="absolute inset-0 flex items-center justify-center animate-in zoom-in-50 duration-700">
                <Sparkles className="w-16 h-16 sm:w-20 sm:h-20 text-accent-primary/30" />
              </div>
              <div className="absolute -top-4 -left-4 animate-in spin-in duration-700">
                <Sparkles className="w-6 h-6 text-yellow-400" />
              </div>
              <div className="absolute -top-2 -right-6 animate-in spin-in duration-700 delay-150">
                <Sparkles className="w-4 h-4 text-amber-400" />
              </div>
              <div className="absolute -bottom-4 -left-6 animate-in spin-in duration-700 delay-300">
                <Sparkles className="w-5 h-5 text-orange-400" />
              </div>
              <div className="absolute -bottom-2 -right-4 animate-in spin-in duration-700 delay-200">
                <Sparkles className="w-4 h-4 text-yellow-400" />
              </div>
            </div>
          </div>
        )}

        {/* Swipe direction feedback */}
        {swipeDirection && !isLessonComplete && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-15 animate-in fade-out duration-300">
            <div className={`flex h-16 w-16 items-center justify-center rounded-full bg-bg-surface/40 backdrop-blur-sm border border-rule/20 ${
              swipeDirection === "left" ? "animate-in slide-in-from-right duration-200" : "animate-in slide-in-from-left duration-200"
            }`}>
              {swipeDirection === "left" ? (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-text-muted/60">
                  <path d="M9 6L3 12L9 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M3 12H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              ) : (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-text-muted/60">
                  <path d="M15 6L21 12L15 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M21 12H3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              )}
            </div>
          </div>
        )}

        {/* Pause indicator */}
        {isPaused && !isLessonComplete && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-bg-surface/60 border border-rule/20 animate-in fade-in duration-200 backdrop-blur-sm">
              <Pause className="h-6 w-6 text-text-muted" />
            </div>
          </div>
        )}

        {/* Active phrase card */}
        {!isLessonComplete && activePhrase && (
          <PhraseCard
            key={`${activePhrase.id}-${currentScriptIndex}`}
            phrase={activePhrase}
            phraseNumber={currentPhraseIndex + 1}
            totalPhrases={phrases.length}
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
          <div className="text-center animate-in fade-in slide-in-from-bottom-8 duration-700">
            {/* Celebration icon */}
            <div className="mb-6 flex justify-center">
              <div className="relative">
                <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-accent-primary/10 flex items-center justify-center">
                  <Sparkles className="w-10 h-10 sm:w-12 sm:h-12 text-accent-primary" />
                </div>
                {/* Orbiting sparkles */}
                <div className="absolute -top-1 -left-1 animate-bounce">
                  <Sparkles className="w-4 h-4 text-yellow-400" />
                </div>
                <div className="absolute -top-1 -right-1 animate-bounce delay-150">
                  <Sparkles className="w-3 h-3 text-amber-400" />
                </div>
                <div className="absolute -bottom-1 -left-2 animate-bounce delay-300">
                  <Sparkles className="w-4 h-4 text-orange-400" />
                </div>
              </div>
            </div>

            <h2 className="font-display text-2xl sm:text-3xl text-text-primary mb-2">
              Lesson Complete!
            </h2>
            <p className="font-body text-base sm:text-lg text-text-secondary/70 mb-2">
              You&apos;ve practiced all {phrases.length} phrase{phrases.length > 1 ? "s" : ""}.
            </p>
            <p className="font-body text-sm text-text-muted mb-8">
              {completedPhrases.size} / {phrases.length} phrases mastered
            </p>

            {/* Action buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
              <button
                onClick={handleReplay}
                className="w-full sm:w-auto rounded-full bg-accent-primary px-8 py-3 font-ui text-sm font-medium text-white transition-colors hover:bg-accent-primary/90 active:scale-95"
              >
                Replay Lesson
              </button>
              <a
                href={backHref}
                className="w-full sm:w-auto rounded-full border border-rule bg-bg-surface px-8 py-3 font-ui text-sm font-medium text-text-primary transition-colors hover:bg-bg-surface-2 active:scale-95 text-center"
              >
                Back to briefing
              </a>
            </div>
          </div>
        )}

        {/* Swipe hint for mobile (shown briefly on first interaction) */}
        {!isLessonComplete && phrases.length > 1 && (
          <div className="absolute bottom-4 left-0 right-0 flex items-center justify-center gap-1 text-text-muted opacity-40">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="rotate-180">
              <path d="M6 3L2 8L6 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M2 8H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span className="text-xs font-ui">swipe</span>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M6 3L2 8L6 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M2 8H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}
