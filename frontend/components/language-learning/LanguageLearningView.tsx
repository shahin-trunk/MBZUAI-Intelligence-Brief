"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Pause } from "lucide-react";
import type { BriefItem, LearningSection } from "@/lib/types/brief";
import { useSectionAudio } from "@/hooks/useSectionAudio";
import LearningHeader from "./LearningHeader";
import AutoFlowSection from "./AutoFlowSection";
import SectionNarrativeText from "./SectionNarrativeText";
import ImmersiveAudioController from "./ImmersiveAudioController";
import LearningVocabularyPanel from "./LearningVocabularyPanel";

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
  const [, setCompletedSections] = useState<Set<number>>(new Set());

  const hasFr = Boolean(item.learning_fr);
  const hasAr = Boolean(item.learning_ar);

  const currentContent =
    language === "fr" ? item.learning_fr : item.learning_ar;

  const sections: LearningSection[] = currentContent?.sections ?? [];

  // Serialize URLs to a stable string for comparison
  const urlsKey = sections.map((s) => s.audio_url ?? "").join("|");
  const sectionAudioUrls = useMemo(
    () => sections.map((s) => s.audio_url),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [urlsKey],
  );

  /* ------------------------------------------------------------------ */
  /*  Audio callbacks                                                    */
  /* ------------------------------------------------------------------ */
  const handleSectionComplete = useCallback((_index: number) => {
    setCompletedSections((prev) => {
      const next = new Set(prev);
      next.add(_index);
      return next;
    });
  }, []);

  const handleAllComplete = useCallback(() => {
    setIsLessonComplete(true);
  }, []);

  /* ------------------------------------------------------------------ */
  /*  Audio hook                                                         */
  /* ------------------------------------------------------------------ */
  const hasAnyAudio = sectionAudioUrls.some((u) => !!u);
  const audio = useSectionAudio(sectionAudioUrls, {
    autoAdvance: true,
    estimatedDurations: sections.map(
      (s) => s.estimated_duration_seconds ?? 30,
    ),
    onSectionComplete: handleSectionComplete,
    onAllComplete: handleAllComplete,
  });

  /* ------------------------------------------------------------------ */
  /*  One-shot auto-play on mount                                        */
  /* ------------------------------------------------------------------ */
  const hasStartedRef = useRef(false);
  // Stable ref so we never close over a stale audio object
  const audioRef = useRef(audio);
  audioRef.current = audio;
  useEffect(() => {
    if (!hasStartedRef.current && hasAnyAudio && sections.length > 0) {
      hasStartedRef.current = true;
      const t = setTimeout(() => {
        audioRef.current.playSection(0);
      }, 1200);
      return () => clearTimeout(t);
    }
  }, [hasAnyAudio, sections.length, language]);

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
      audio.pause(); // STOP CURRENT AUDIO BEFORE SWITCHING
      setLanguage(lang);
      setCompletedSections(new Set());
      setIsLessonComplete(false);
      setIsPaused(false);
      hasStartedRef.current = false; // Allow auto-play for new language
    },
    [audio],
  );

  /* ------------------------------------------------------------------ */
  /*  Replay                                                             */
  /* ------------------------------------------------------------------ */
  const handleReplay = useCallback(() => {
    setIsLessonComplete(false);
    setCompletedSections(new Set());
    setIsPaused(false);
    audio.playSection(0);
  }, [audio]);

  /* ------------------------------------------------------------------ */
  /*  Derived                                                            */
  /* ------------------------------------------------------------------ */
  const backHref = `/brief/${briefDate}?slideIndex=${slideIndex}`;

  /* ------------------------------------------------------------------ */
  /*  Fallback: no content                                               */
  /* ------------------------------------------------------------------ */
  if (!currentContent || sections.length === 0) {
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
  /*  Fallback: sections exist but no audio yet                          */
  /* ------------------------------------------------------------------ */
  if (sections.length > 0 && !hasAnyAudio) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-bg-primary px-6">
        <div className="mx-auto max-w-md text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-accent-primary border-t-transparent" />
          <h1 className="font-display text-xl text-text-primary">
            Generating audio...
          </h1>
          <p className="mt-3 font-body text-sm text-text-secondary">
            Audio for this lesson is still being generated. Please check back shortly.
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
  /*  Active section                                                     */
  /* ------------------------------------------------------------------ */
  const activeSection = sections[audio.currentSectionIndex];

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
        currentSection={audio.currentSectionIndex + 1}
        totalSections={sections.length}
      />

      {/* Main content — tap to pause zone */}
      <div
        className="relative flex-1 flex flex-col items-center justify-center px-6 sm:px-10 lg:px-0 py-16 sm:py-20 lg:py-24 w-full mx-auto sm:max-w-[560px] lg:max-w-[620px] cursor-default select-none"
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
        {/* Single active section with crossfade */}
        {!isLessonComplete && activeSection && (
          <AutoFlowSection
            key={`${activeSection.id}-${audio.currentSectionIndex}`}
            section={activeSection}
            sectionProgress={audio.sectionProgress}
            language={language}
          >
            <SectionNarrativeText
              script={activeSection.script}
              language={language}
              currentTime={audio.currentTime}
              duration={audio.duration}
              isPlaying={audio.isPlaying}
            />
          </AutoFlowSection>
        )}

        {/* Vocabulary reveal after completion */}
        <LearningVocabularyPanel
          vocabulary={currentContent?.vocabulary ?? []}
          language={language}
          isRevealed={isLessonComplete}
          onReplayLesson={handleReplay}
          backHref={backHref}
        />
      </div>
    </div>
  );
}
