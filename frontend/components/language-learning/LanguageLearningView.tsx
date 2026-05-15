"use client";

import { useState, useCallback, useMemo } from "react";
import type { BriefItem, LearningSection } from "@/lib/types/brief";
import { useSectionAudio } from "@/hooks/useSectionAudio";
import LearningHeader from "./LearningHeader";
import LearningSectionNav from "./LearningSectionNav";
import SectionNarrativeText from "./SectionNarrativeText";
import SectionAudioControls from "./SectionAudioControls";
import LearningPhrasesPanel from "./LearningPhrasesPanel";
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
  const [language, setLanguage] = useState<LearnLang>(
    item.learning_fr ? "fr" : "ar"
  );
  const [completedSections, setCompletedSections] = useState<Set<number>>(
    new Set()
  );
  const [allSectionsPlayed, setAllSectionsPlayed] = useState(false);

  const hasFr = Boolean(item.learning_fr);
  const hasAr = Boolean(item.learning_ar);

  const currentContent =
    language === "fr" ? item.learning_fr : item.learning_ar;

  const sections: LearningSection[] = currentContent?.sections ?? [];

  // Build audio URL playlist for the hook
  const sectionAudioUrls = useMemo(
    () => sections.map((s) => s.audio_url),
    [sections],
  );

  const handleSectionComplete = useCallback(
    (index: number) => {
      setCompletedSections((prev) => {
        const next = new Set(prev);
        next.add(index);
        return next;
      });
    },
    [],
  );

  const handleAllComplete = useCallback(() => {
    setAllSectionsPlayed(true);
  }, []);

  const audio = useSectionAudio(sectionAudioUrls, {
    autoAdvance: true,
    onSectionComplete: handleSectionComplete,
    onAllComplete: handleAllComplete,
  });

  const currentSection = sections[audio.currentSectionIndex] ?? null;

  const handleLanguageChange = useCallback(
    (lang: LearnLang) => {
      setLanguage(lang);
      setCompletedSections(new Set());
      setAllSectionsPlayed(false);
    },
    [],
  );

  const handleSectionSelect = useCallback(
    (index: number) => {
      audio.playSection(index);
      setAllSectionsPlayed(false);
    },
    [audio],
  );

  const backHref = `/brief/${briefDate}?slideIndex=${slideIndex}`;

  if (!currentContent || sections.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-primary px-6">
        <div className="mx-auto max-w-md text-center">
          <h1 className="font-display text-2xl text-text-primary">
            Content Unavailable
          </h1>
          <p className="mt-3 text-text-secondary">
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

  return (
    <div
      className="flex min-h-screen flex-col bg-bg-primary"
      dir={language === "ar" ? "rtl" : "ltr"}
    >
      {/* Header */}
      <LearningHeader
        backHref={backHref}
        headline={item.headline}
        language={language}
        onLanguageChange={handleLanguageChange}
        hasFr={hasFr}
        hasAr={hasAr}
      />

      {/* Section Navigation */}
      <div className="border-b border-rule bg-bg-primary py-2">
        <LearningSectionNav
          sections={sections}
          currentIndex={audio.currentSectionIndex}
          completedIndices={completedSections}
          onSelect={handleSectionSelect}
          language={language}
        />
      </div>

      {/* Main content area */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 pt-6 pb-8 sm:px-6 sm:pt-8 lg:mx-auto lg:w-full lg:max-w-[720px] lg:px-0">
        {/* Section title */}
        {currentSection && (
          <div className="mb-4">
            <p className="font-ui text-[11px] uppercase tracking-widest text-text-muted">
              {currentSection.title_en}
            </p>
          </div>
        )}

        {/* Narrative text with karaoke highlighting */}
        {currentSection && (
          <section className="mb-5 rounded-2xl border border-rule bg-bg-surface px-5 py-6 sm:px-7 sm:py-8">
            <SectionNarrativeText
              script={currentSection.script}
              language={language}
              currentTime={audio.currentTime}
              duration={audio.duration}
              isPlaying={audio.isPlaying}
            />
          </section>
        )}

        {/* Audio controls */}
        <section className="mb-6">
          <SectionAudioControls
            isPlaying={audio.isPlaying}
            isLoading={audio.isLoading}
            currentTime={audio.currentTime}
            duration={audio.duration}
            speed={audio.speed}
            currentSectionIndex={audio.currentSectionIndex}
            totalSections={sections.length}
            onTogglePlayPause={audio.togglePlayPause}
            onSeek={audio.seek}
            onCycleSpeed={audio.cycleSpeed}
            onNextSection={audio.nextSection}
            onPrevSection={audio.prevSection}
          />
        </section>

        {/* Key phrases for current section */}
        {currentSection?.key_phrases && currentSection.key_phrases.length > 0 && (
          <section className="mb-6">
            <h2 className="mb-3 font-display text-lg font-normal text-text-primary">
              {language === "fr" ? "Expressions clés" : "العبارات الرئيسية"}
            </h2>
            <LearningPhrasesPanel
              phrases={currentSection.key_phrases}
              language={language}
            />
          </section>
        )}

        {/* Vocabulary — always accessible, emphasized after all sections played */}
        {currentContent.vocabulary.length > 0 && (
          <section
            className={`transition-opacity duration-500 ${
              allSectionsPlayed ? "opacity-100" : "opacity-80"
            }`}
          >
            <h2 className="mb-4 font-display text-lg font-normal text-text-primary">
              {language === "fr" ? "Vocabulaire" : "المفردات"}
            </h2>
            <LearningVocabularyPanel
              vocabulary={currentContent.vocabulary}
              language={language}
            />
          </section>
        )}
      </div>
    </div>
  );
}

