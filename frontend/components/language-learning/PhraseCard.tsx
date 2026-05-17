"use client";

import type { LearningPhrase } from "@/lib/types/brief";
import PhraseHighlightText from "./PhraseHighlightText";

interface PhraseCardProps {
  phrase: LearningPhrase;
  language: "fr" | "ar";
  scriptIndex: 1 | 2 | 3;
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
  const isArabic = language === "ar";

  /* ------------------------------------------------------------------ */
  /*  Script 2: Transition — elegant centered bridge                    */
  /* ------------------------------------------------------------------ */
  if (scriptIndex === 2) {
    return (
      <div className="flex flex-col items-center justify-center py-10 sm:py-14 animate-in fade-in duration-500">
        <div className="flex flex-col items-center space-y-3">
          {/* Decorative divider */}
          <div className="flex items-center gap-3 mb-2">
            <div className="h-px w-8 bg-accent-primary/30" />
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none" className="text-accent-primary/50">
              <circle cx="4" cy="4" r="3" stroke="currentColor" strokeWidth="1" />
            </svg>
            <div className="h-px w-8 bg-accent-primary/30" />
          </div>
          <p className="font-body text-[16px] sm:text-[18px] lg:text-[20px] text-text-secondary/70 text-center italic leading-relaxed">
            {phrase.script2}
          </p>
          {/* Decorative divider */}
          <div className="flex items-center gap-3 mt-2">
            <div className="h-px w-8 bg-accent-primary/30" />
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none" className="text-accent-primary/50">
              <circle cx="4" cy="4" r="3" stroke="currentColor" strokeWidth="1" />
            </svg>
            <div className="h-px w-8 bg-accent-primary/30" />
          </div>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Script 1: Bilingual explanation                                   */
  /* ------------------------------------------------------------------ */
  if (scriptIndex === 1) {
    return (
      <div className="flex flex-col items-center justify-center py-8 sm:py-10 animate-in fade-in duration-500">
        {/* Phrase header: target phrase + English translation */}
        <div className="mb-6 sm:mb-8 text-center space-y-2">
          <p
            dir={isArabic ? "rtl" : "ltr"}
            className="font-body text-[24px] sm:text-[28px] lg:text-[32px] text-text-primary font-semibold leading-snug"
          >
            {phrase.phrase_target}
          </p>
          <p className="font-body text-[14px] sm:text-[15px] text-text-secondary/60">
            {phrase.phrase_en}
          </p>
        </div>

        {/* Bilingual explanation with group highlight */}
        <div className="w-full px-2 sm:px-4">
          <PhraseHighlightText
            script={phrase.script1}
            language={language}
            currentTime={currentTime}
            duration={duration}
            isPlaying={isPlaying}
            highlightMode="group"
          />
        </div>

        {/* Grammar expand trigger */}
        {showGrammarTrigger && phrase.script4 && (
          <button
            onClick={onExpandGrammar}
            className="mt-6 sm:mt-8 text-sm font-medium text-accent-primary/80 hover:text-accent-primary transition-colors cursor-pointer px-4 py-2 rounded-full border border-accent-primary/20 hover:border-accent-primary/40 hover:bg-accent-primary/5"
          >
            Explore grammar & linguistic details
          </button>
        )}
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Script 3: Target language — prominent word-level highlight        */
  /* ------------------------------------------------------------------ */
  return (
    <div className="flex flex-col items-center justify-center py-8 sm:py-12 animate-in fade-in duration-500">
      {/* Context bridge: show this comes from the briefing */}
      <div className="mb-6 sm:mb-8 flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-surface/50 border border-rule/30">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-text-muted">
          <path d="M6 1L7.5 4.5L11 5L8.5 7.5L9 11L6 9.5L3 11L3.5 7.5L1 5L4.5 4.5L6 1Z" stroke="currentColor" strokeWidth="1" strokeLinejoin="round" />
        </svg>
        <span className="text-xs font-ui text-text-muted">From your briefing</span>
      </div>

      {/* Context anchor text (if available) */}
      {phrase.context_anchor && (
        <div className="w-full px-2 sm:px-4 mb-4">
          <p className="font-body text-[12px] sm:text-[13px] text-text-muted italic text-center leading-relaxed">
            &ldquo;{phrase.context_anchor}&rdquo;
          </p>
        </div>
      )}

      {/* Target language phrase — LARGE, prominent */}
      <div className="w-full px-2 sm:px-4 mb-6 sm:mb-8">
        <PhraseHighlightText
          script={phrase.script3}
          language={language}
          currentTime={currentTime}
          duration={duration}
          isPlaying={isPlaying}
          highlightMode="word"
        />
      </div>

      {/* English translation — subtle reference below */}
      <div className="flex items-center gap-2 mb-4">
        <div className="h-px w-6 bg-rule/50" />
        <p className="font-body text-[15px] sm:text-[16px] lg:text-[18px] text-text-secondary/50 italic">
          {phrase.phrase_en}
        </p>
        <div className="h-px w-6 bg-rule/50" />
      </div>

      {/* Pronunciation guide (if available) */}
      {phrase.grammar.phonetic_guide && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-bg-surface/40 border border-rule/20 mb-4">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-text-muted shrink-0">
            <path d="M3 5V9M5 3V11M7 2V12M9 4V10M11 6V8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <code className="font-mono text-[13px] sm:text-[14px] text-text-secondary/70">
            {phrase.grammar.phonetic_guide}
          </code>
        </div>
      )}

      {/* Grammar expand trigger */}
      {showGrammarTrigger && phrase.script4 && (
        <button
          onClick={onExpandGrammar}
          className="mt-4 text-sm font-medium text-accent-primary/80 hover:text-accent-primary transition-colors cursor-pointer px-4 py-2 rounded-full border border-accent-primary/20 hover:border-accent-primary/40 hover:bg-accent-primary/5"
        >
          Explore grammar & linguistic details
        </button>
      )}
    </div>
  );
}
