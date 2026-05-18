"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Pause, Play, Loader2, Sparkles, SkipBack, SkipForward } from "lucide-react";
import type { BriefItem, LearningPhrase } from "@/lib/types/brief";
import { useSectionAudio } from "@/hooks/useSectionAudio";
import { useLearningAnalytics } from "@/hooks/useLearningAnalytics";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import LearningHeader from "./LearningHeader";
import ContextBanner from "./ContextBanner";
import PhraseCard from "./PhraseCard";
import PhraseGrammarDrawer from "./PhraseGrammarDrawer";
import PhraseNavigationDots from "./PhraseNavigationDots";
import ImmersiveAudioController from "./ImmersiveAudioController";
import LearningStats from "./LearningStats";
import LanguageLearningErrorBoundary from "./LanguageLearningErrorBoundary";
import LanguageLearningSkeleton from "./LanguageLearningSkeleton";

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
  const [isTapFeedback, setIsTapFeedback] = useState(false);
  // ITER 18: Enhanced progress tracking
  const [sentencesViewed, setSentencesViewed] = useState<Set<number>>(new Set());
  const [grammarOpened, setGrammarOpened] = useState(0);
  const [lessonStartTime] = useState(Date.now());
  // Transition tracking between phrases
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [prevPhraseId, setPrevPhraseId] = useState<string | null>(null);

  const hasFr = Boolean(item.learning_fr);
  const hasAr = Boolean(item.learning_ar);

  const currentContent =
    language === "fr" ? item.learning_fr : item.learning_ar;

  const phrases: LearningPhrase[] = currentContent?.phrases ?? [];

  /* ------------------------------------------------------------------ */
  /*  Analytics tracking                                                 */
  /* ------------------------------------------------------------------ */
  const { trackEvent } = useLearningAnalytics(item.id);

  /* ------------------------------------------------------------------ */
  /*  Progress persistence with localStorage                             */
  /* ------------------------------------------------------------------ */
  const progressKey = useMemo(() => {
    if (!item.id) return null;
    return `ll-progress-${item.id}-${language}`;
  }, [item.id, language]);

  // Load saved progress on mount
  useEffect(() => {
    if (!progressKey) return;
    try {
      const saved = localStorage.getItem(progressKey);
      if (saved) {
        const data = JSON.parse(saved);
        if (data.completedPhrases?.length > 0) {
          setCompletedPhrases(new Set(data.completedPhrases));
        }
        if (data.isLessonComplete) {
          setIsLessonComplete(true);
        }
        // ITER 18: Load enhanced tracking data
        if (data.sentencesViewed?.length > 0) {
          setSentencesViewed(new Set(data.sentencesViewed));
        }
        if (data.grammarOpened) {
          setGrammarOpened(data.grammarOpened);
        }
      }
    } catch {
      // Ignore localStorage errors
    }
  }, [progressKey]);

  // Save progress when completed phrases change
  useEffect(() => {
    if (!progressKey) return;
    try {
      localStorage.setItem(progressKey, JSON.stringify({
        completedPhrases: Array.from(completedPhrases),
        isLessonComplete,
        // ITER 18: Enhanced tracking data
        sentencesViewed: Array.from(sentencesViewed),
        grammarOpened,
        lessonStartTime,
        timestamp: Date.now(),
      }));
    } catch {
      // Ignore localStorage errors
    }
  }, [progressKey, completedPhrases, isLessonComplete, sentencesViewed, grammarOpened, lessonStartTime]);

  /* ------------------------------------------------------------------ */
  /*  Handle audio URL missing gracefully                                */
  /* ------------------------------------------------------------------ */
  const hasMissingAudio = useMemo(() => {
    return phrases.some((p) => !p.audio_url_1 && !p.audio_url_2 && !p.audio_url_3);
  }, [phrases]);

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

  // Track phrase transitions for animation
  useEffect(() => {
    if (activePhrase) {
      if (prevPhraseId && prevPhraseId !== activePhrase.id) {
        setIsTransitioning(true);
        const t = setTimeout(() => setIsTransitioning(false), 600);
        return () => clearTimeout(t);
      }
      setPrevPhraseId(activePhrase.id);
    }
  }, [activePhrase?.id, prevPhraseId]);

  // Track lesson completion
  useEffect(() => {
    if (isLessonComplete) {
      trackEvent(language, currentPhraseIndex, currentScriptIndex, "lesson_complete");
    }
  }, [isLessonComplete, language, currentPhraseIndex, currentScriptIndex, trackEvent]);

  // ITER 18: Track sentences viewed as user navigates
  useEffect(() => {
    if (phrases.length > 0 && currentPhraseIndex >= 0 && currentPhraseIndex < phrases.length) {
      setSentencesViewed((prev) => {
        if (prev.has(currentPhraseIndex)) return prev;
        const next = new Set(prev);
        next.add(currentPhraseIndex);
        return next;
      });
    }
  }, [currentPhraseIndex, phrases.length]);

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
      // ITER 18: Track sentence viewed
      setSentencesViewed((prev) => {
        const next = new Set(prev);
        next.add(phraseIdx);
        return next;
      });
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
  /*  Tap-to-pause with haptic feedback                                  */
  /* ------------------------------------------------------------------ */
  const handleTapToggle = useCallback(() => {
    if (isLessonComplete) return;

    // Visual tap feedback
    setIsTapFeedback(true);
    setTimeout(() => setIsTapFeedback(false), 150);

    if (audio.isPlaying && !isPaused) {
      audio.pause();
      setIsPaused(true);
    } else if (isPaused) {
      audio.togglePlayPause();
      setIsPaused(false);
    }
  }, [audio, isPaused, isLessonComplete]);

  /* ------------------------------------------------------------------ */
  /*  Keyboard navigation for desktop                                    */
  /* ------------------------------------------------------------------ */
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isLessonComplete) return;

      switch (e.key) {
        case "ArrowLeft":
          e.preventDefault();
          setSwipeDirection("right");
          const prevIdx = Math.max(currentPhraseIndex - 1, 0);
          handlePhraseSelect(prevIdx);
          setTimeout(() => setSwipeDirection(null), 300);
          break;
        case "ArrowRight":
          e.preventDefault();
          setSwipeDirection("left");
          const nextIdx = Math.min(currentPhraseIndex + 1, phrases.length - 1);
          handlePhraseSelect(nextIdx);
          setTimeout(() => setSwipeDirection(null), 300);
          break;
        case " ":
          e.preventDefault();
          handleTapToggle();
          break;
        case "Escape":
          e.preventDefault();
          if (expandedPhraseGrammar !== null) {
            handleGrammarToggle(null);
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentPhraseIndex, phrases.length, handlePhraseSelect, handleTapToggle, isLessonComplete, expandedPhraseGrammar]);

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
  /*  Language change                                                     */
  /* ------------------------------------------------------------------ */
  const handleLanguageChange = useCallback(
    (lang: LearnLang) => {
      // CRITICAL: Kill ALL audio (main player + grammar drawer) before switching language
      audio.pause();
      // Direct DOM audio cleanup for any lingering elements
      if (typeof window !== 'undefined') {
        document.querySelectorAll("audio").forEach((el) => {
          el.pause();
          el.removeAttribute("src");
          el.load();
        });
      }
      setLanguage(lang);
      setCompletedPhrases(new Set());
      setIsLessonComplete(false);
      setIsPaused(false);
      setExpandedPhraseGrammar(null);
      setShowCelebration(false);
      // ITER 18: Reset tracking states
      setSentencesViewed(new Set());
      setGrammarOpened(0);
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
    trackEvent(language, 0, 1, "replay");
    audio.playSection(0);
  }, [audio, language, trackEvent]);

  /* ------------------------------------------------------------------ */
  /*  Reset progress (clear localStorage)                                */
  /* ------------------------------------------------------------------ */
  const handleResetProgress = useCallback(() => {
    if (progressKey) {
      try {
        localStorage.removeItem(progressKey);
      } catch {
        // Ignore
      }
    }
    handleReplay();
  }, [progressKey, handleReplay]);

  /* ------------------------------------------------------------------ */
  /*  Grammar drawer toggle                                               */
  /* ------------------------------------------------------------------ */
  const handleGrammarToggle = useCallback(
    (phraseIdx: number | null) => {
      setExpandedPhraseGrammar(phraseIdx);
      if (phraseIdx !== null) {
        trackEvent(language, phraseIdx, currentScriptIndex, "grammar_open");
        // ITER 18: Track grammar deep dive
        setGrammarOpened((prev) => prev + 1);
      }
    },
    [language, currentScriptIndex, trackEvent],
  );

  /* ------------------------------------------------------------------ */
  /*  Derived                                                            */
  /* ------------------------------------------------------------------ */
  const backHref = `/brief/${briefDate}?slideIndex=${slideIndex}`;

  /* ------------------------------------------------------------------ */
  /*  Loading: generation in progress                                    */
  /* ------------------------------------------------------------------ */
  const isGenerating = !hasAnyAudio && phrases.length === 0;

  // Check for partial generation (some phrases have audio, others don't)
  const phrasesWithAudio = phrases.filter((p) => p.audio_url_1).length;
  const isPartialGeneration = phrases.length > 0 && phrasesWithAudio < phrases.length && phrasesWithAudio > 0;

  /* ------------------------------------------------------------------ */
  /*  Keyboard shortcuts                                                  */
  /* ------------------------------------------------------------------ */
  useKeyboardShortcuts({
    onPrevious: () => {
      if (!isLessonComplete && !isGenerating) {
        const prevIdx = Math.max(currentPhraseIndex - 1, 0);
        handlePhraseSelect(prevIdx);
      }
    },
    onNext: () => {
      if (!isLessonComplete && !isGenerating) {
        const nextIdx = Math.min(currentPhraseIndex + 1, phrases.length - 1);
        handlePhraseSelect(nextIdx);
      }
    },
    onPlayPause: handleTapToggle,
    onReplay: handleReplay,
    onCloseGrammar: () => {
      if (expandedPhraseGrammar !== null) {
        handleGrammarToggle(null);
      }
    },
    onToggleLanguage: () => {
      if (hasFr && hasAr) {
        handleLanguageChange(language === "fr" ? "ar" : "fr");
      }
    },
    enabled: true,
  });

  if (isGenerating) {
    return <LanguageLearningSkeleton />;
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
  /*  Helper: format time                                                */
  /* ------------------------------------------------------------------ */
  const fmt = (seconds: number) => {
    if (!seconds || !isFinite(seconds)) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  /* ------------------------------------------------------------------ */
  /*  SCRIPT_LABELS for display in controller                            */
  /* ------------------------------------------------------------------ */
  const SCRIPT_LABELS: Record<number, string> = {
    1: "Teacher explains",
    2: "Transition",
    3: "Listen",
  };

  /* ------------------------------------------------------------------ */
  /*  Main render                                                        */
  /* ------------------------------------------------------------------ */
  return (
    <LanguageLearningErrorBoundary>
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
        difficulty={currentContent?.difficulty}
        lessonSummary={currentContent?.lesson_summary}
        totalDuration={currentContent?.total_duration_seconds}
      />

      {/* Context banner: link to parent briefing slide */}
      <div className="px-4 py-3">
        <ContextBanner
          headline={item.headline}
          briefDate={briefDate}
          slideIndex={slideIndex}
          category={item.section}
        />
      </div>

      {/* Missing audio warning banner */}
      {hasMissingAudio && (
        <div className="px-4 pb-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-amber-500 shrink-0">
              <path d="M7 1C3.68629 1 1 3.68629 1 7C1 10.3137 3.68629 13 7 13C10.3137 13 13 10.3137 13 7C13 3.68629 10.3137 1 7 1Z" stroke="currentColor" strokeWidth="1.2" />
              <path d="M7 4.5V7.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              <circle cx="7" cy="10" r="0.6" fill="currentColor" />
            </svg>
            <p className="font-body text-[11px] text-amber-700">
              Audio is being generated. Text and grammar content available.
            </p>
          </div>
        </div>
      )}

      {/* SPACER — push content area to center */}
      <div className="flex-1 flex flex-col" style={{ paddingBottom: "140px" }}>
        {/* Main content area — tap to pause zone, swipe for navigation */}
        <div
          className={`relative flex-1 flex flex-col items-center justify-start px-6 sm:px-10 lg:px-0 py-6 sm:py-10 lg:py-12 w-full mx-auto sm:max-w-[560px] lg:max-w-[620px] xl:max-w-[700px] cursor-default select-none touch-pan-y transition-transform duration-150 ${
            isTapFeedback ? "scale-[0.98]" : "scale-100"
          }`}
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

          {/* Active phrase card with transition animation */}
          {!isLessonComplete && activePhrase && (
            <div className={`w-full transition-all duration-500 ease-out ${
              isTransitioning ? "opacity-0 translate-y-4 scale-[0.97]" : "opacity-100 translate-y-0 scale-100"
            }`}>
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
                difficulty={currentContent?.difficulty}
              />
            </div>
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
              <p className="font-body text-sm text-text-muted mb-6">
                {completedPhrases.size} / {phrases.length} phrases mastered
              </p>

              {/* Learning stats */}
              <LearningStats
                totalPhrases={phrases.length}
                completedPhrases={completedPhrases.size}
                totalDuration={currentContent?.total_duration_seconds}
                language={language}
                // ITER 18: Enhanced tracking
                sentencesViewed={sentencesViewed.size}
                grammarOpened={grammarOpened}
                startTime={lessonStartTime}
              />

              {/* Action buttons */}
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
                <button
                  onClick={handleReplay}
                  className="w-full sm:w-auto rounded-full bg-accent-primary px-8 py-3 font-ui text-sm font-medium text-white transition-colors hover:bg-accent-primary/90 active:scale-95"
                >
                  Replay Lesson
                </button>
                <button
                  onClick={handleResetProgress}
                  className="w-full sm:w-auto rounded-full border border-rule bg-bg-surface px-8 py-3 font-ui text-sm font-medium text-text-secondary transition-colors hover:bg-bg-surface-2 hover:text-text-primary active:scale-95"
                >
                  Reset Progress
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
            <div className="absolute bottom-2 sm:bottom-4 left-0 right-0 flex items-center justify-center gap-1 text-text-muted opacity-40">
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

      {/* ================================================================ */}
      {/*  BOTTOM CONTROLS: Nav dots + Playback controls                    */}
      {/* ================================================================ */}
      {!isLessonComplete && (
        <div className="fixed bottom-0 left-0 right-0 z-40 bg-bg-primary/95 backdrop-blur-xl border-t border-rule/20"
             style={{ paddingBottom: "calc(0.5rem + env(safe-area-inset-bottom))" }}>
          {/* Navigation dots row */}
          <div className="flex justify-center py-2">
            <PhraseNavigationDots
              totalPhrases={phrases.length}
              currentPhraseIndex={currentPhraseIndex}
              currentScriptIndex={currentScriptIndex}
              completedPhrases={completedPhrases}
              scriptProgress={scriptProgress}
              onPhraseSelect={handlePhraseSelect}
            />
          </div>

          {/* Playback control bar */}
          <div className="flex items-center justify-center gap-4 sm:gap-6 px-4 pb-2">
            {/* Previous phrase */}
            <button
              onClick={() => {
                if (currentPhraseIndex > 0) {
                  handlePhraseSelect(currentPhraseIndex - 1);
                }
              }}
              disabled={currentPhraseIndex <= 0}
              className="flex items-center justify-center w-10 h-10 rounded-full text-text-muted hover:text-text-primary hover:bg-bg-surface transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Previous phrase"
            >
              <SkipBack className="w-5 h-5" strokeWidth={1.5} />
            </button>

            {/* Script label */}
            <div className="hidden sm:flex items-center min-w-[90px] justify-center">
              <span className="font-ui text-[11px] text-text-muted tabular-nums">
                {SCRIPT_LABELS[currentScriptIndex]}
              </span>
            </div>

            {/* Play/Pause button — big and prominent */}
            <button
              onClick={handleTapToggle}
              disabled={!hasAnyAudio}
              className="flex items-center justify-center w-14 h-14 rounded-full bg-accent-primary text-white hover:bg-accent-primary/90 active:scale-95 transition-all shadow-lg shadow-accent-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label={isPaused || !audio.isPlaying ? "Play" : "Pause"}
            >
              {audio.isLoading ? (
                <Loader2 className="w-6 h-6 animate-spin" />
              ) : isPaused || !audio.isPlaying ? (
                <Play className="w-6 h-6 ml-0.5" fill="white" strokeWidth={1.5} />
              ) : (
                <Pause className="w-6 h-6" fill="white" strokeWidth={1.5} />
              )}
            </button>

            {/* Time display */}
            <div className="min-w-[60px] text-center">
              <span className="font-ui text-[11px] text-text-muted tabular-nums">
                {fmt(audio.currentTime)} / {fmt(audio.duration > 0 ? audio.duration : (scriptDurations[audio.currentSectionIndex] || 0))}
              </span>
            </div>

            {/* Next phrase */}
            <button
              onClick={() => {
                if (currentPhraseIndex < phrases.length - 1) {
                  handlePhraseSelect(currentPhraseIndex + 1);
                } else if (!audio.isPlaying && !isPaused) {
                  // If on last phrase and paused, go to start
                  handlePhraseSelect(0);
                }
              }}
              disabled={currentPhraseIndex >= phrases.length - 1 && !(!audio.isPlaying && !isPaused)}
              className="flex items-center justify-center w-10 h-10 rounded-full text-text-muted hover:text-text-primary hover:bg-bg-surface transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Next phrase"
            >
              <SkipForward className="w-5 h-5" strokeWidth={1.5} />
            </button>
          </div>
        </div>
      )}
    </div>
    </LanguageLearningErrorBoundary>
  );
}
