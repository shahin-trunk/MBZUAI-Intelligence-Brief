"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Pause, Play, Loader2, Sparkles, SkipBack, SkipForward, ChevronLeft, ChevronRight } from "lucide-react";
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
  const [sentencesViewed, setSentencesViewed] = useState<Set<number>>(new Set());
  const [grammarOpened, setGrammarOpened] = useState(0);
  const [lessonStartTime] = useState(Date.now());
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [transitionMessage, setTransitionMessage] = useState<string | null>(null);

  const hasFr = Boolean(item.learning_fr);
  const hasAr = Boolean(item.learning_ar);

  const currentContent =
    language === "fr" ? item.learning_fr : item.learning_ar;

  const phrases: LearningPhrase[] = currentContent?.phrases ?? [];

  /* ------------------------------------------------------------------ */
  /*  Analytics                                                          */
  /* ------------------------------------------------------------------ */
  const { trackEvent } = useLearningAnalytics(item.id);

  /* ------------------------------------------------------------------ */
  /*  Progress persistence                                               */
  /* ------------------------------------------------------------------ */
  const progressKey = useMemo(() => {
    if (!item.id) return null;
    return `ll-progress-${item.id}-${language}`;
  }, [item.id, language]);

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
        if (data.sentencesViewed?.length > 0) {
          setSentencesViewed(new Set(data.sentencesViewed));
        }
        if (data.grammarOpened) {
          setGrammarOpened(data.grammarOpened);
        }
      }
    } catch { /* ignore */ }
  }, [progressKey]);

  useEffect(() => {
    if (!progressKey) return;
    try {
      localStorage.setItem(progressKey, JSON.stringify({
        completedPhrases: Array.from(completedPhrases),
        isLessonComplete,
        sentencesViewed: Array.from(sentencesViewed),
        grammarOpened,
        lessonStartTime,
        timestamp: Date.now(),
      }));
    } catch { /* ignore */ }
  }, [progressKey, completedPhrases, isLessonComplete, sentencesViewed, grammarOpened, lessonStartTime]);

  /* ------------------------------------------------------------------ */
  /*  Missing audio check                                                */
  /* ------------------------------------------------------------------ */
  const hasMissingAudio = useMemo(() => {
    return phrases.some((p) => !p.audio_url_1 && !p.audio_url_2 && !p.audio_url_3);
  }, [phrases]);

  /* ------------------------------------------------------------------ */
  /*  Flatten script URLs                                                */
  /* ------------------------------------------------------------------ */
  const scriptUrls = useMemo(
    () => phrases.flatMap((p) => [p.audio_url_1, p.audio_url_2, p.audio_url_3]),
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

  // Persistent refs for callbacks that need latest values
  const scriptUrlsRef = useRef(scriptUrls);
  scriptUrlsRef.current = scriptUrls;
  const phrasesRef = useRef(phrases);
  phrasesRef.current = phrases;
  const audioRef = useRef<ReturnType<typeof useSectionAudio> | null>(null);
  const advancerTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const advanceToNext = useCallback((fromIndex: number) => {
    let target = fromIndex + 1;
    while (target < scriptUrlsRef.current.length && !scriptUrlsRef.current[target]) {
      target++;
    }
    if (target < scriptUrlsRef.current.length) {
      audioRef.current?.playSection(target);
    } else {
      setIsLessonComplete(true);
      setShowCelebration(true);
      setTimeout(() => setShowCelebration(false), 3000);
    }
  }, []);

  const handleSectionComplete = useCallback((index: number) => {
    const phraseIdx = Math.floor(index / 3);
    setCompletedPhrases((prev) => {
      const next = new Set(prev);
      next.add(phraseIdx);
      return next;
    });

    // Phrase boundary detection: script 3 (last of phrase) just finished
    const isPhraseBoundary = (index % 3 === 2) && phraseIdx < phrasesRef.current.length - 1;

    if (isPhraseBoundary) {
      // Add smooth narrative transition delay at phrase boundaries
      const nextPhrase = phrasesRef.current[phraseIdx + 1];
      const nextHint = nextPhrase?.sentence_en || nextPhrase?.phrase_en || "";
      const preview = nextHint.length > 60 ? nextHint.slice(0, 57) + "..." : nextHint;
      setTransitionMessage(preview);
      setIsTransitioning(true);

      // Clear any existing timers
      advancerTimersRef.current.forEach(clearTimeout);
      const timer = setTimeout(() => {
        setIsTransitioning(false);
        setTransitionMessage(null);
        advanceToNext(index);
      }, 1200);
      advancerTimersRef.current = [timer];
    } else {
      // Within-phrase script change — advance immediately for seamless flow
      advanceToNext(index);
    }
  }, [advanceToNext]);

  // Cleanup transition timers on unmount
  useEffect(() => {
    return () => {
      advancerTimersRef.current.forEach(clearTimeout);
    };
  }, []);

  /* ------------------------------------------------------------------ */
  /*  Audio hook                                                         */
  /* ------------------------------------------------------------------ */
  const hasAnyAudio = scriptUrls.some((u) => !!u);
  const audio = useSectionAudio(scriptUrls, {
    autoAdvance: false,
    estimatedDurations: scriptDurations,
    onSectionComplete: handleSectionComplete,
    onAllComplete: () => {},
  });
  // Sync audio ref for callback usage
  audioRef.current = audio;

  /* ------------------------------------------------------------------ */
  /*  Derive current phrase and script                                   */
  /* ------------------------------------------------------------------ */
  const currentPhraseIndex = Math.floor(audio.currentSectionIndex / 3);
  const currentScriptIndex = (audio.currentSectionIndex % 3) + 1;
  const activePhrase = phrases[currentPhraseIndex];

  /* ------------------------------------------------------------------ */
  /*  Phrase transition tracking — (coordinated via handleSectionComplete) */
  /* ------------------------------------------------------------------ */

  useEffect(() => {
    if (isLessonComplete) {
      trackEvent(language, currentPhraseIndex, currentScriptIndex, "lesson_complete");
    }
  }, [isLessonComplete, language, currentPhraseIndex, currentScriptIndex, trackEvent]);

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

  const scriptProgress = useMemo(() => {
    const scriptStartIndex = currentPhraseIndex * 3;
    const scriptsInPhrase = 3;
    const completedScripts = audio.currentSectionIndex - scriptStartIndex;
    const currentScriptFraction = audio.sectionProgress;
    return (completedScripts + currentScriptFraction) / scriptsInPhrase;
  }, [currentPhraseIndex, audio.currentSectionIndex, audio.sectionProgress]);

  /* ------------------------------------------------------------------ */
  /*  Navigation                                                         */
  /* ------------------------------------------------------------------ */
  const handlePhraseSelect = useCallback(
    (phraseIdx: number) => {
      const scriptIdx = phraseIdx * 3;
      audio.playSection(scriptIdx);
      setIsPaused(false);
      setExpandedPhraseGrammar(null);
      setSentencesViewed((prev) => {
        const next = new Set(prev);
        next.add(phraseIdx);
        return next;
      });
    },
    [audio],
  );

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
  /*  Auto-play on mount                                                 */
  /* ------------------------------------------------------------------ */
  const hasStartedRef = useRef(false);
  useEffect(() => {
    if (!hasStartedRef.current && hasAnyAudio && phrases.length > 0) {
      hasStartedRef.current = true;
      const t = setTimeout(() => {
        audioRef.current?.playSection(0);
      }, 800);
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
          if (cancelled) { sentinel.release(); return; }
          wakeLockRef.current = sentinel;
          sentinel.addEventListener("release", () => { wakeLockRef.current = null; });
        }
      } catch { /* ignore */ }
    }
    async function release() {
      try { await wakeLockRef.current?.release(); wakeLockRef.current = null; } catch { /* ignore */ }
    }
    if (audio.isPlaying && !isPaused && !isLessonComplete) {
      acquire();
    } else {
      release();
    }
    return () => { cancelled = true; release(); };
  }, [audio.isPlaying, isPaused, isLessonComplete]);

  /* ------------------------------------------------------------------ */
  /*  Language change                                                    */
  /* ------------------------------------------------------------------ */
  const handleLanguageChange = useCallback(
    (lang: LearnLang) => {
      audio.pause();
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
      setSentencesViewed(new Set());
      setGrammarOpened(0);
      hasStartedRef.current = false;
    },
    [audio],
  );

  const handleReplay = useCallback(() => {
    setIsLessonComplete(false);
    setCompletedPhrases(new Set());
    setIsPaused(false);
    setExpandedPhraseGrammar(null);
    setShowCelebration(false);
    trackEvent(language, 0, 1, "replay");
    audio.playSection(0);
  }, [audio, language, trackEvent]);

  const handleResetProgress = useCallback(() => {
    if (progressKey) {
      try { localStorage.removeItem(progressKey); } catch { /* ignore */ }
    }
    handleReplay();
  }, [progressKey, handleReplay]);

  const handleGrammarToggle = useCallback(
    (phraseIdx: number | null) => {
      setExpandedPhraseGrammar(phraseIdx);
      if (phraseIdx !== null) {
        trackEvent(language, phraseIdx, currentScriptIndex, "grammar_open");
        setGrammarOpened((prev) => prev + 1);
      }
    },
    [language, currentScriptIndex, trackEvent],
  );

  /* ------------------------------------------------------------------ */
  /*  Derived                                                            */
  /* ------------------------------------------------------------------ */
  const backHref = `/brief/${briefDate}?slideIndex=${slideIndex}`;
  const isGenerating = !hasAnyAudio && phrases.length === 0;
  const phrasesWithAudio = phrases.filter((p) => p.audio_url_1).length;
  const isPartialGeneration = phrases.length > 0 && phrasesWithAudio < phrases.length && phrasesWithAudio > 0;

  /* ------------------------------------------------------------------ */
  /*  Keyboard shortcuts                                                 */
  /* ------------------------------------------------------------------ */
  useKeyboardShortcuts({
    onPrevious: () => {
      if (!isLessonComplete && !isGenerating) {
        handlePhraseSelect(Math.max(currentPhraseIndex - 1, 0));
      }
    },
    onNext: () => {
      if (!isLessonComplete && !isGenerating) {
        handlePhraseSelect(Math.min(currentPhraseIndex + 1, phrases.length - 1));
      }
    },
    onPlayPause: handleTapToggle,
    onReplay: handleReplay,
    onCloseGrammar: () => { if (expandedPhraseGrammar !== null) handleGrammarToggle(null); },
    onToggleLanguage: () => { if (hasFr && hasAr) handleLanguageChange(language === "fr" ? "ar" : "fr"); },
    enabled: true,
  });

  /* ------------------------------------------------------------------ */
  /*  Loading / Empty states                                             */
  /* ------------------------------------------------------------------ */
  if (isGenerating) return <LanguageLearningSkeleton />;

  if (!currentContent || phrases.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-950 px-6">
        <div className="mx-auto max-w-md text-center">
          <h1 className="font-display text-xl text-gray-200">Content not available</h1>
          <p className="mt-3 font-body text-sm text-gray-500">
            Learning content for {language === "fr" ? "French" : "Arabic"} is not available for this item.
          </p>
          <a href={backHref} className="mt-6 inline-block rounded-full border border-gray-700 bg-gray-900/50 px-5 py-2.5 font-ui text-sm text-indigo-400 transition-colors hover:bg-gray-800/50">
            Back to briefing
          </a>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Format time helper                                                 */
  /* ------------------------------------------------------------------ */
  const fmt = (seconds: number) => {
    if (!seconds || !isFinite(seconds)) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const scriptLabels: Record<number, string> = {
    1: "Explanation",
    2: "Bridge",
    3: "Listen",
  };

  /* ------------------------------------------------------------------ */
  /*  Main render                                                        */
  /* ------------------------------------------------------------------ */
  return (
    <LanguageLearningErrorBoundary>
      <div
        className="min-h-screen flex flex-col bg-gray-950 text-gray-100"
        dir={language === "ar" ? "rtl" : "ltr"}
      >
        {/* Top progress bar */}
        <ImmersiveAudioController
          overallProgress={audio.overallProgress}
          isLessonComplete={isLessonComplete}
          isLoading={audio.isLoading}
        />

        {/* Minimal header */}
        <LearningHeader
          backHref={backHref}
          language={language}
          onLanguageChange={handleLanguageChange}
          hasFr={hasFr}
          hasAr={hasAr}
        />

        {/* Context */}
        <ContextBanner
          headline={item.headline}
          briefDate={briefDate}
          slideIndex={slideIndex}
          category={item.section}
        />

        {/* Missing audio warning */}
        {hasMissingAudio && (
          <div className="px-5 py-2">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/5 border border-amber-500/15">
              <span className="text-[10px] text-amber-400/70 font-ui">Audio is being generated. Text available.</span>
            </div>
          </div>
        )}

        {/* MAIN CONTENT */}
        <div className="flex-1 flex flex-col" style={{ paddingBottom: "160px" }}>
          <div
            className="relative flex-1 flex flex-col items-center justify-start px-5 sm:px-8 lg:px-0 py-6 sm:py-8 w-full mx-auto sm:max-w-[560px] lg:max-w-[620px] xl:max-w-[700px] select-none"
            onClick={handleTapToggle}
            role="button"
            tabIndex={-1}
          >
            {/* Celebration */}
            {showCelebration && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20 animate-in fade-in duration-500">
                <div className="relative">
                  <Sparkles className="w-16 h-16 text-indigo-400/20" />
                  <div className="absolute -top-4 -left-4 animate-in spin-in duration-700">
                    <Sparkles className="w-5 h-5 text-yellow-400/60" />
                  </div>
                  <div className="absolute -bottom-2 -right-4 animate-in spin-in duration-700 delay-200">
                    <Sparkles className="w-4 h-4 text-amber-400/60" />
                  </div>
                </div>
              </div>
            )}

            {/* Pause indicator */}
            {isPaused && !isLessonComplete && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white/5 border border-white/10 backdrop-blur-sm animate-in fade-in duration-150">
                  <Pause className="h-6 w-6 text-gray-400" />
                </div>
              </div>
            )}

            {/* Transition overlay — shows upcoming sentence preview */}
            {isTransitioning && transitionMessage && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-20 animate-in fade-in duration-300">
                <div className="text-center">
                  <span className="font-ui text-[9px] uppercase tracking-[0.2em] text-indigo-400/60 block mb-3">
                    Next sentence
                  </span>
                  <div className="w-16 h-px bg-gradient-to-r from-transparent via-indigo-400/30 to-transparent mb-4" />
                  <p className="font-body text-[13px] text-gray-400 italic leading-relaxed max-w-xs mx-auto">
                    {transitionMessage}
                  </p>
                </div>
              </div>
            )}

            {/* Active phrase card */}
            {!isLessonComplete && activePhrase && (
              <div className={`w-full transition-all duration-500 ease-out ${
                isTransitioning ? "opacity-0 translate-y-3" : "opacity-100 translate-y-0"
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
                      expandedPhraseGrammar === currentPhraseIndex ? null : currentPhraseIndex
                    )
                  }
                  showGrammarTrigger={currentScriptIndex === 3 && !!activePhrase.script4}
                />
              </div>
            )}

            {/* Grammar drawer */}
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
              <div className="text-center animate-in fade-in slide-in-from-bottom-8 duration-700 mt-12">
                <div className="mb-6 flex justify-center">
                  <div className="w-20 h-20 rounded-full bg-indigo-500/10 flex items-center justify-center">
                    <Sparkles className="w-10 h-10 text-indigo-400" />
                  </div>
                </div>
                <h2 className="font-display text-2xl text-gray-100 mb-2 font-semibold">Lesson Complete</h2>
                <p className="font-body text-base text-gray-500 mb-1">All {phrases.length} sentence{phrases.length > 1 ? "s" : ""} practiced.</p>
                <p className="font-body text-sm text-gray-600 mb-6">{completedPhrases.size} / {phrases.length} mastered</p>

                <LearningStats
                  totalPhrases={phrases.length}
                  completedPhrases={completedPhrases.size}
                  totalDuration={currentContent?.total_duration_seconds}
                  language={language}
                  sentencesViewed={sentencesViewed.size}
                  grammarOpened={grammarOpened}
                  startTime={lessonStartTime}
                />

                <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-6">
                  <button onClick={handleReplay} className="w-full sm:w-auto rounded-full bg-indigo-500 px-8 py-3 font-ui text-sm font-medium text-white hover:bg-indigo-400 transition-colors active:scale-95">
                    Replay Lesson
                  </button>
                  <button onClick={handleResetProgress} className="w-full sm:w-auto rounded-full border border-gray-700 bg-gray-900/50 px-8 py-3 font-ui text-sm font-medium text-gray-300 hover:bg-gray-800/50 transition-colors active:scale-95">
                    Reset Progress
                  </button>
                  <a href={backHref} className="w-full sm:w-auto rounded-full border border-gray-700 bg-gray-900/50 px-8 py-3 font-ui text-sm font-medium text-gray-300 hover:bg-gray-800/50 transition-colors active:scale-95 text-center">
                    Back to briefing
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ================================================================ */}
        {/*  ELEGANT BOTTOM CONTROLS: Counter + Nav Dots + Playback           */}
        {/* ================================================================ */}
        {!isLessonComplete && (
          <div className="fixed bottom-0 left-0 right-0 z-40"
               style={{ paddingBottom: "calc(0.5rem + env(safe-area-inset-bottom))" }}>
            {/* Glass container */}
            <div className="mx-3 sm:mx-auto sm:max-w-lg rounded-2xl bg-gray-900/80 backdrop-blur-xl border border-gray-800/40 shadow-2xl">
              {/* Lesson counter + label row */}
              <div className="flex items-center justify-between px-5 pt-2.5 pb-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-ui text-[11px] font-medium text-indigo-300 tabular-nums">
                    {currentPhraseIndex + 1} / {phrases.length}
                  </span>
                  <span className="font-ui text-[9px] text-gray-500 uppercase tracking-wider">
                    {scriptLabels[currentScriptIndex]}
                  </span>
                </div>
                <span className="font-ui text-[10px] text-gray-500 tabular-nums">
                  {fmt(audio.currentTime)} / {fmt(audio.duration > 0 ? audio.duration : (scriptDurations[audio.currentSectionIndex] || 0))}
                </span>
              </div>

              {/* Navigation dots */}
              <div className="flex justify-center py-1">
                <PhraseNavigationDots
                  totalPhrases={phrases.length}
                  currentPhraseIndex={currentPhraseIndex}
                  completedPhrases={completedPhrases}
                  scriptProgress={scriptProgress}
                  onPhraseSelect={handlePhraseSelect}
                />
              </div>

              {/* Main playback bar */}
              <div className="flex items-center justify-center gap-5 px-5 pb-3 pt-1">
                {/* Previous */}
                <button
                  onClick={() => { if (currentPhraseIndex > 0) handlePhraseSelect(currentPhraseIndex - 1); }}
                  disabled={currentPhraseIndex <= 0}
                  className="flex items-center justify-center w-9 h-9 rounded-full text-gray-500 hover:text-gray-300 hover:bg-gray-800/50 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                  aria-label="Previous sentence"
                >
                  <ChevronLeft className="w-5 h-5" strokeWidth={1.5} />
                </button>

                {/* Play/Pause */}
                <button
                  onClick={handleTapToggle}
                  disabled={!hasAnyAudio}
                  className="flex items-center justify-center w-13 h-13 rounded-full bg-indigo-500 text-white hover:bg-indigo-400 active:scale-95 transition-all shadow-lg shadow-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ width: "52px", height: "52px" }}
                  aria-label={isPaused || !audio.isPlaying ? "Play" : "Pause"}
                >
                  {audio.isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : isPaused || !audio.isPlaying ? (
                    <Play className="w-5 h-5 ml-0.5" fill="white" strokeWidth={1.5} />
                  ) : (
                    <Pause className="w-5 h-5" fill="white" strokeWidth={1.5} />
                  )}
                </button>

                {/* Next */}
                <button
                  onClick={() => {
                    if (currentPhraseIndex < phrases.length - 1) {
                      handlePhraseSelect(currentPhraseIndex + 1);
                    } else if (!audio.isPlaying && !isPaused) {
                      handlePhraseSelect(0);
                    }
                  }}
                  disabled={currentPhraseIndex >= phrases.length - 1 && !(!audio.isPlaying && !isPaused)}
                  className="flex items-center justify-center w-9 h-9 rounded-full text-gray-500 hover:text-gray-300 hover:bg-gray-800/50 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                  aria-label="Next sentence"
                >
                  <ChevronRight className="w-5 h-5" strokeWidth={1.5} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </LanguageLearningErrorBoundary>
  );
}
