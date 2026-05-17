"use client";

import type { LearningPhrase } from "@/lib/types/brief";
import PhraseHighlightText from "./PhraseHighlightText";

interface PhraseCardProps {
  phrase: LearningPhrase;
  language: "fr" | "ar";
  scriptIndex: 1 | 2 | 3; // Which script is currently active (1-3)
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  onExpandGrammar: () => void;
  showGrammarTrigger: boolean;
}

export default function PhraseCard({
  phrase,
  language,
  scriptIndex,
  currentTime,
  duration,
  isPlaying,
  onExpandGrammar,
  showGrammarTrigger,
}: PhraseCardProps) {
  // Script2 (transition): centered, dimmed
  if (scriptIndex === 2) {
    return (
      <div className="flex flex-col items-center justify-center py-12 animate-fade-in">
        <p className="font-body text-[18px] sm:text-[20px] text-text-secondary/70 text-center">
          {phrase.script2}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-8 space-y-6 animate-fade-in">
      {/* Script1: Bilingual explanation text */}
      {scriptIndex === 1 && (
        <PhraseHighlightText
          script={phrase.script1}
          language={language}
          currentTime={currentTime}
          duration={duration}
          isPlaying={isPlaying}
          highlightMode="group"
        />
      )}

      {/* Script3: Target-language phrase with word-level highlight */}
      {scriptIndex === 3 && (
        <div className="flex flex-col items-center space-y-4">
          <PhraseHighlightText
            script={phrase.script3}
            language={language}
            currentTime={currentTime}
            duration={duration}
            isPlaying={isPlaying}
            highlightMode="word"
          />
          <p className="font-body text-[16px] sm:text-[18px] text-text-secondary/60">
            {phrase.phrase_en}
          </p>
        </div>
      )}

      {/* Grammar expand trigger (shown after Script3 completes) */}
      {showGrammarTrigger && phrase.script4 && (
        <button
          onClick={onExpandGrammar}
          className="mt-4 text-sm font-medium text-accent-primary/80 hover:text-accent-primary transition-colors cursor-pointer"
        >
          Explore grammar & linguistic details
        </button>
      )}
    </div>
  );
}
