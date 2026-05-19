"use client";

import { memo } from "react";
import { Mic } from "lucide-react";
import type { LearningPhrase } from "@/lib/types/brief";
import PhraseHighlightText from "./PhraseHighlightText";

interface PhraseCardProps {
  phrase: LearningPhrase;
  phraseNumber: number;
  totalPhrases: number;
  language: "fr" | "ar";
  scriptIndex: 1 | 2 | 3;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  onExpandGrammar: () => void;
  showGrammarTrigger: boolean;
  difficulty?: "beginner" | "intermediate" | "advanced";
}

function getTargetText(phrase: LearningPhrase): string {
  return phrase.sentence_target || phrase.phrase_target;
}

function getEnglishText(phrase: LearningPhrase): string {
  return phrase.sentence_en || phrase.phrase_en;
}

const PhraseCard = memo(function PhraseCard({
  phrase,
  phraseNumber,
  totalPhrases,
  language,
  scriptIndex,
  currentTime,
  duration,
  isPlaying,
  onExpandGrammar,
  showGrammarTrigger,
}: PhraseCardProps) {
  const isArabic = language === "ar";
  const targetText = getTargetText(phrase);
  const englishText = getEnglishText(phrase);
  const learnLang = language === "fr" ? "French" : "Arabic";

  /* ------------------------------------------------------------------ */
  /*  Script 2: Transition — an elegant centered bridge                 */
  /* ------------------------------------------------------------------ */
  if (scriptIndex === 2) {
    return (
      <div className="flex flex-col items-center justify-center py-14 sm:py-20 animate-in fade-in duration-500">
        <div className="flex flex-col items-center space-y-6 max-w-md">
          <span className="font-ui text-[10px] uppercase tracking-[0.2em] text-text-muted">
            Bridge
          </span>
          <div className="w-16 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
          <p className="font-body text-[17px] sm:text-[19px] text-text-secondary text-center italic leading-[1.7] font-light px-4">
            {phrase.script2}
          </p>
          <div className="w-16 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Script 1: Bilingual explanation — learn the meaning              */
  /* ------------------------------------------------------------------ */
  if (scriptIndex === 1) {
    return (
      <div className="flex flex-col items-center py-6 sm:py-8 animate-in fade-in duration-500">
        {/* Target sentence — large, elegant */}
        <div className="w-full max-w-lg text-center mb-8">
          <p
            dir={isArabic ? "rtl" : "ltr"}
            className="font-body text-[28px] sm:text-[34px] lg:text-[38px] text-text-primary font-semibold leading-tight tracking-tight"
          >
            {targetText}
          </p>
          <p className="font-body text-[14px] sm:text-[15px] text-text-muted mt-3 font-light">
            {englishText}
          </p>
        </div>

        {/* Teacher explanation with word-group highlighting */}
        {phrase.script1 && (
          <div className="w-full">
            <div className="flex items-center gap-2 mb-5">
              <div className="h-4 w-0.5 rounded-full bg-accent/40" />
              <span className="font-ui text-[10px] uppercase tracking-[0.15em] text-text-muted">
                Teacher explains
              </span>
            </div>
            <PhraseHighlightText
              script={phrase.script1}
              language={language}
              currentTime={currentTime}
              duration={duration}
              isPlaying={isPlaying}
              highlightMode="group"
            />
          </div>
        )}

        {/* Grammar detail button */}
        {showGrammarTrigger && phrase.script4 && (
          <button
            onClick={onExpandGrammar}
            className="mt-8 group inline-flex items-center gap-2 px-4 py-2 rounded-full border border-accent/20 text-accent-primary/70 hover:text-accent-primary hover:border-accent/40 hover:bg-accent/[0.03] transition-all duration-200 text-xs font-ui active:scale-[0.97]"
          >
            <Mic className="h-3.5 w-3.5" strokeWidth={1.5} />
            <span>Grammar deep dive</span>
          </button>
        )}
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Script 3: Target language — listen and repeat                     */
  /* ------------------------------------------------------------------ */
  return (
    <div className="flex flex-col items-center py-6 sm:py-10 animate-in fade-in duration-500">
      {/* Target language — prominent word-level highlighting */}
      <div className="w-full mb-6">
        <div className="flex items-center gap-2 mb-5">
          <div className="h-4 w-0.5 rounded-full bg-accent/40" />
          <span className="font-ui text-[10px] uppercase tracking-[0.15em] text-text-muted">
            Listen & repeat
          </span>
        </div>
        <PhraseHighlightText
          script={phrase.script3}
          language={language}
          currentTime={currentTime}
          duration={duration}
          isPlaying={isPlaying}
          highlightMode="word"
        />
      </div>

      {/* English reference */}
      <p className="font-body text-[13px] text-text-muted italic font-light text-center mb-6">
        {englishText}
      </p>

      {/* Key vocabulary chips */}
      {phrase.grammar.key_words && phrase.grammar.key_words.length > 0 && (
        <div className="flex flex-wrap gap-2 justify-center mb-5 max-w-sm">
          {phrase.grammar.key_words.map((kw, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-bg-surface-2 border border-rule"
            >
              <span
                className="font-body text-[12px] text-accent-primary font-medium"
                dir={language === "ar" ? "rtl" : "ltr"}
              >
                {kw.word}
              </span>
              <span className="font-body text-[10px] text-text-muted">
                {kw.note}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Phonetic features */}
      {phrase.grammar.phonetic_features && (
        <div className="px-4 py-2.5 rounded-lg bg-accent/5 border border-accent/10 mb-4 max-w-sm text-center">
          <p className="font-body text-[11px] text-text-secondary leading-relaxed">
            {phrase.grammar.phonetic_features}
          </p>
        </div>
      )}

      {/* Pronunciation guide */}
      {phrase.grammar.phonetic_guide && (
        <code className="font-mono text-[11px] text-text-muted mb-4 text-center block">
          {phrase.grammar.phonetic_guide}
        </code>
      )}

      {/* Cognate note */}
      {phrase.grammar.cognate_note && (
        <div className="px-4 py-2.5 rounded-lg bg-accent-success/5 border border-accent-success/10 mb-4 max-w-sm text-center">
          <p className="font-body text-[11px] text-text-secondary leading-relaxed">
            {phrase.grammar.cognate_note}
          </p>
        </div>
      )}

      {/* Grammar detail button */}
      {showGrammarTrigger && phrase.script4 && (
        <button
          onClick={onExpandGrammar}
          className="mt-2 group inline-flex items-center gap-2 px-4 py-2 rounded-full border border-accent/20 text-accent-primary/70 hover:text-accent-primary hover:border-accent/40 hover:bg-accent/[0.03] transition-all duration-200 text-xs font-ui active:scale-[0.97]"
        >
          <Mic className="h-3.5 w-3.5" strokeWidth={1.5} />
          <span>Grammar deep dive</span>
        </button>
      )}
    </div>
  );
});

export default PhraseCard;
