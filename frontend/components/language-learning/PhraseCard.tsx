"use client";

import { memo } from "react";
import { BookOpen, Languages, Mic } from "lucide-react";
import type { LearningPhrase } from "@/lib/types/brief";
import PhraseHighlightText from "./PhraseHighlightText";
import PhraseBookmark from "./PhraseBookmark";

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

/** Get the target language text, preferring sentence fields when available (ITER 18). */
function getTargetText(phrase: LearningPhrase): string {
  return phrase.sentence_target || phrase.phrase_target;
}

/** Get the English translation, preferring sentence fields when available (ITER 18). */
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
  difficulty,
}: PhraseCardProps) {
  const isArabic = language === "ar";
  const targetText = getTargetText(phrase);
  const englishText = getEnglishText(phrase);

  /* ------------------------------------------------------------------ */
  /*  Script 2: Transition — elegant centered bridge                    */
  /* ------------------------------------------------------------------ */
  if (scriptIndex === 2) {
    return (
      <div className="flex flex-col items-center justify-center py-10 sm:py-14 animate-in fade-in duration-500">
        <div className="flex flex-col items-center space-y-4 transition-all duration-300 hover:scale-105">
          {/* Decorative divider */}
          <div className="flex items-center gap-3 mb-2">
            <div className="h-px w-10 bg-gradient-to-r from-transparent to-accent-primary/40" />
            <div className="h-1.5 w-1.5 rounded-full bg-accent-primary/50" />
            <div className="h-px w-10 bg-gradient-to-l from-transparent to-accent-primary/40" />
          </div>
          <p className="font-body text-[16px] sm:text-[18px] lg:text-[20px] text-text-secondary/70 text-center italic leading-relaxed">
            {phrase.script2}
          </p>
          {/* Decorative divider */}
          <div className="flex items-center gap-3 mt-2">
            <div className="h-px w-10 bg-gradient-to-r from-transparent to-accent-primary/40" />
            <div className="h-1.5 w-1.5 rounded-full bg-accent-primary/50" />
            <div className="h-px w-10 bg-gradient-to-l from-transparent to-accent-primary/40" />
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
      <div className="flex flex-col items-center justify-center py-6 sm:py-8 lg:py-10 animate-in fade-in duration-500">
        {/* Phrase badge + target phrase + English translation */}
        <div className="mb-5 sm:mb-7 text-center space-y-3 transition-all duration-300">
          {/* Progress badge + bookmark + difficulty indicator */}
          <div className="flex items-center justify-center gap-2">
            <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-accent-primary/10 border border-accent-primary/20">
              <Languages className="h-3 w-3 text-accent-primary/70" />
              <span className="text-xs font-ui font-semibold text-accent-primary">
                {phraseNumber} / {totalPhrases}
              </span>
            </div>
            {difficulty && (
              <div className={`inline-flex items-center gap-0.5 px-2 py-1 rounded-full border text-[10px] font-ui font-medium ${
                difficulty === 'beginner' ? 'bg-green-500/10 border-green-500/20 text-green-600' :
                difficulty === 'intermediate' ? 'bg-amber-500/10 border-amber-500/20 text-amber-600' :
                'bg-red-500/10 border-red-500/20 text-red-600'
              }`}>
                {difficulty === 'beginner' ? '●' : difficulty === 'intermediate' ? '●●' : '●●●'}
              </div>
            )}
            <PhraseBookmark
              phraseId={phrase.id}
              phraseText={targetText}
              language={language}
            />
          </div>

          {/* Target phrase/sentence — large, prominent */}
          <p
            dir={isArabic ? "rtl" : "ltr"}
            className="font-body text-[26px] sm:text-[30px] lg:text-[34px] text-text-primary font-semibold leading-tight tracking-tight"
          >
            {targetText}
          </p>

          {/* English translation */}
          <p className="font-body text-[14px] sm:text-[15px] text-text-secondary/60">
            {englishText}
          </p>

          {/* Context anchor badge */}
          {phrase.context_anchor && (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-bg-surface/60 border border-rule/30">
              <BookOpen className="h-3 w-3 text-text-muted/60" />
              <span className="font-body text-[11px] text-text-muted italic">
                &ldquo;{phrase.context_anchor}&rdquo;
              </span>
            </div>
          )}
        </div>

        {/* Bilingual explanation with group highlight */}
        <div className="w-full px-3 sm:px-4 lg:px-0 lg:max-w-[560px] xl:max-w-[620px]">
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
            className="mt-6 sm:mt-8 text-sm font-medium text-accent-primary/80 hover:text-accent-primary transition-all duration-200 cursor-pointer px-5 py-2.5 rounded-full border border-accent-primary/25 hover:border-accent-primary/50 hover:bg-accent-primary/5 hover:scale-105 active:scale-95"
          >
            <Mic className="inline h-3.5 w-3.5 mr-1.5 -mt-0.5" />
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
    <div className="flex flex-col items-center justify-center py-6 sm:py-10 lg:py-12 animate-in fade-in duration-500">
      {/* Context bridge: show this comes from the briefing */}
      <div className="mb-5 sm:mb-7 flex flex-col items-center gap-2.5 transition-all duration-300">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-surface/60 border border-rule/30">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-accent-primary/60">
              <path d="M6 1L7.5 4.5L11 5L8.5 7.5L9 11L6 9.5L3 11L3.5 7.5L1 5L4.5 4.5L6 1Z" stroke="currentColor" strokeWidth="1" strokeLinejoin="round" />
            </svg>
            <span className="text-xs font-ui text-text-secondary">From your briefing</span>
          </div>
          {difficulty && (
            <div className={`inline-flex items-center gap-0.5 px-2 py-1 rounded-full border text-[10px] font-ui font-medium ${
              difficulty === 'beginner' ? 'bg-green-500/10 border-green-500/20 text-green-600' :
              difficulty === 'intermediate' ? 'bg-amber-500/10 border-amber-500/20 text-amber-600' :
              'bg-red-500/10 border-red-500/20 text-red-600'
            }`}>
              {difficulty === 'beginner' ? '● Easy' : difficulty === 'intermediate' ? '●● Medium' : '●●● Hard'}
            </div>
          )}
          <PhraseBookmark
            phraseId={phrase.id}
            phraseText={targetText}
            language={language}
          />
        </div>

        {/* Context anchor text (if available) */}
        {phrase.context_anchor && (
          <div className="w-full px-4">
            <p className="font-body text-[11px] sm:text-[12px] text-text-muted/80 italic text-center leading-relaxed max-w-[300px] sm:max-w-[420px] mx-auto">
              &ldquo;{phrase.context_anchor}&rdquo;
            </p>
          </div>
        )}
      </div>

      {/* Target language phrase — LARGE, prominent */}
      <div className="w-full px-3 sm:px-4 lg:px-0 lg:max-w-[560px] xl:max-w-[620px] mb-6 sm:mb-8">
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
      <div className="flex items-center gap-3 mb-5">
        <div className="h-px w-10 bg-gradient-to-r from-transparent to-rule/40" />
        <p className="font-body text-[14px] sm:text-[15px] lg:text-[16px] text-text-secondary/50 italic">
          {englishText}
        </p>
        <div className="h-px w-10 bg-gradient-to-l from-transparent to-rule/40" />
      </div>

      {/* ITER 18: Key words breakdown — vocabulary at a glance */}
      {phrase.grammar.key_words && phrase.grammar.key_words.length > 0 && (
        <div className="w-full px-4 mb-5 max-w-[340px] sm:max-w-[420px] mx-auto">
          <div className="flex flex-wrap gap-2 justify-center">
            {phrase.grammar.key_words.map((kw, i) => (
              <div
                key={i}
                className="flex flex-col items-center px-3 py-2 rounded-lg bg-bg-surface/60 border border-rule/20 min-w-[80px]"
              >
                <span
                  className="font-body text-[13px] sm:text-[14px] text-accent-primary font-semibold"
                  dir={language === "ar" ? "rtl" : "ltr"}
                >
                  {kw.word}
                </span>
                <span className="font-body text-[10px] text-text-muted mt-0.5 text-center leading-tight">
                  {kw.note}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Phonetic features (ITER 18) — pronunciation tips */}
      {phrase.grammar.phonetic_features && (
        <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl bg-purple-500/5 border border-purple-500/20 mb-5 max-w-[340px] sm:max-w-[420px] mx-auto">
          <span className="text-sm shrink-0" role="img" aria-label="music">🎵</span>
          <p className="font-body text-[12px] sm:text-[13px] text-text-secondary/70 leading-relaxed">
            {phrase.grammar.phonetic_features}
          </p>
        </div>
      )}

      {/* Pronunciation guide (if available) */}
      {phrase.grammar.phonetic_guide && (
        <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl bg-bg-surface/50 border border-rule/25 mb-5 transition-all duration-200 hover:border-accent-primary/30 hover:bg-bg-surface/60 max-w-[340px] sm:max-w-[420px] mx-auto">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-text-muted shrink-0 mt-0.5">
            <path d="M3 5V9M5 3V11M7 2V12M9 4V10M11 6V8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <code className="font-mono text-[12px] sm:text-[13px] text-text-secondary/70 leading-relaxed">
            {phrase.grammar.phonetic_guide}
          </code>
        </div>
      )}

      {/* Cognate note (if available) */}
      {phrase.grammar.cognate_note && (
        <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl bg-green-500/5 border border-green-500/20 mb-5 max-w-[340px] sm:max-w-[420px] mx-auto">
          <span className="text-sm shrink-0">💡</span>
          <p className="font-body text-[12px] sm:text-[13px] text-text-secondary/70 leading-relaxed">
            {phrase.grammar.cognate_note}
          </p>
        </div>
      )}

      {/* Grammar expand trigger */}
      {showGrammarTrigger && phrase.script4 && (
        <button
          onClick={onExpandGrammar}
          className="mt-2 text-sm font-medium text-accent-primary/80 hover:text-accent-primary transition-all duration-200 cursor-pointer px-5 py-2.5 rounded-full border border-accent-primary/25 hover:border-accent-primary/50 hover:bg-accent-primary/5 hover:scale-105 active:scale-95"
        >
          <Mic className="inline h-3.5 w-3.5 mr-1.5 -mt-0.5" />
          Explore grammar & linguistic details
        </button>
      )}
    </div>
  );
});

export default PhraseCard;
