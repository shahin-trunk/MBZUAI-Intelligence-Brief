"use client";

import { useState, useCallback } from "react";
import type { BriefItem } from "@/lib/types/brief";
import { useLearningAudio } from "@/hooks/useLearningAudio";
import LearningHeader from "./LearningHeader";
import LearningReadingPassage from "./LearningReadingPassage";
import LearningAudioPlayer from "./LearningAudioPlayer";
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

  const hasFr = Boolean(item.learning_fr);
  const hasAr = Boolean(item.learning_ar);

  const currentContent =
    language === "fr" ? item.learning_fr : item.learning_ar;

  const audioUrl = currentContent?.audio_url;

  const player = useLearningAudio(audioUrl);

  const handleLanguageChange = useCallback((lang: LearnLang) => {
    setLanguage(lang);
  }, []);

  const backHref = `/brief/${briefDate}?slideIndex=${slideIndex}`;

  if (!currentContent) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-primary px-6">
        <div className="mx-auto max-w-md text-center">
          <h1 className="font-display text-2xl text-text-primary">
            Content Unavailable
          </h1>
          <p className="mt-3 text-text-secondary">
            Learning content for {language === "fr" ? "French" : "Arabic"} is not available for this slide.
          </p>
          <a
            href={backHref}
            className="mt-6 inline-block rounded-full border border-rule bg-bg-surface px-5 py-2.5 font-ui text-sm text-accent-primary hover:bg-bg-surface-2 transition-colors"
          >
            Back to briefing
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-primary" dir={language === "ar" ? "rtl" : "ltr"}>
      <LearningHeader
        backHref={backHref}
        headline={item.headline}
        language={language}
        onLanguageChange={handleLanguageChange}
        hasFr={hasFr}
        hasAr={hasAr}
      />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 pt-6 pb-8 sm:px-6 sm:pt-10 lg:mx-auto lg:max-w-[720px] lg:px-0">
        {/* Reading Passage */}
        <section className="mb-6 sm:mb-8">
          <LearningReadingPassage
            script={currentContent.script}
            language={language}
            currentTime={player.currentTime}
            isPlaying={player.isPlaying}
          />
        </section>

        {/* Audio Player */}
        {audioUrl ? (
          <section className="mb-8 sm:mb-10">
            <LearningAudioPlayer player={player} />
          </section>
        ) : (
          <section className="mb-8 sm:mb-10">
            <div className="rounded-xl border border-rule bg-bg-surface px-4 py-3 text-center font-ui text-sm text-text-muted">
              Audio narration not yet available for {language === "fr" ? "French" : "Arabic"}.
              Text-only learning is available below.
            </div>
          </section>
        )}

        {/* Key Vocabulary */}
        {currentContent.vocabulary.length > 0 && (
          <section>
            <h2 className="mb-4 font-display text-xl font-normal text-text-primary">
              {language === "fr" ? "Vocabulaire clé" : "المفردات الأساسية"}
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
