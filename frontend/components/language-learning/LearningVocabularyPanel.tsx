"use client";

import { useState, useEffect } from "react";
import { Check } from "lucide-react";
import type { LearningVocabulary } from "@/lib/types/brief";

interface LearningVocabularyPanelProps {
  vocabulary: LearningVocabulary[];
  language: "fr" | "ar";
  isRevealed: boolean;
  onReplayLesson?: () => void;
  backHref?: string;
}

export default function LearningVocabularyPanel({
  vocabulary,
  language,
  isRevealed,
  onReplayLesson,
  backHref,
}: LearningVocabularyPanelProps) {
  const [mounted, setMounted] = useState(false);
  const [showFooter, setShowFooter] = useState(false);

  const isArabic = language === "ar";
  const totalCards = vocabulary.length;
  const lastCardDelay = (totalCards) * 150;
  const footerDelay = lastCardDelay + 400;

  useEffect(() => {
    if (isRevealed) {
      requestAnimationFrame(() => setMounted(true));
      const timer = setTimeout(() => setShowFooter(true), footerDelay);
      return () => clearTimeout(timer);
    } else {
      setMounted(false);
      setShowFooter(false);
    }
  }, [isRevealed, footerDelay]);

  if (!isRevealed) return null;

  return (
    <section className="pt-8 px-1 sm:px-0 w-full">
      <div className="mx-auto max-w-[500px]">
        {/* Heading with checkmark */}
        <div
          className="text-center transition-opacity duration-300 ease-out mb-8"
          style={{ opacity: mounted ? 1 : 0 }}
        >
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-accent-primary/30 bg-accent-primary/5">
            <Check className="h-6 w-6 text-accent-primary" strokeWidth={2} />
          </div>
          <h3 className="font-display text-[15px] uppercase tracking-widest text-text-primary">
            Lesson Complete
          </h3>
        </div>

        {/* Vocabulary cards */}
        <div className="space-y-3">
          {vocabulary.map((entry, idx) => {
            const examples = entry.example_sentences?.length
              ? entry.example_sentences
              : entry.example_sentence
                ? [entry.example_sentence]
                : [];

            return (
              <div
                key={idx}
                className="rounded-xl border border-rule/20 bg-bg-surface/40 overflow-hidden transition-all duration-400 ease-out"
                style={{
                  opacity: mounted ? 1 : 0,
                  transform: mounted ? "translateY(0)" : "translateY(12px)",
                  transitionDelay: `${(idx + 1) * 150}ms`,
                }}
              >
                {/* Term + POS + pronunciation */}
                <div className="px-4 pt-3.5 pb-2.5">
                  <p className="font-display text-[15px] font-medium text-text-primary">
                    {entry.term}
                    {entry.part_of_speech && (
                      <span className="font-mono text-[10px] uppercase text-text-muted ml-2">
                        {entry.part_of_speech}
                      </span>
                    )}
                  </p>

                  {/* Translation */}
                  <p
                    className={`text-[15px] text-accent-primary mt-0.5 ${
                      isArabic ? "text-right" : ""
                    }`}
                  >
                    {entry.translation}
                  </p>

                  {/* Pronunciation */}
                  {entry.pronunciation_guide && (
                    <p className="text-[11px] text-text-muted mt-1 italic">
                      {entry.pronunciation_guide}
                    </p>
                  )}
                </div>

                {/* Grammar note */}
                {entry.grammar_note && (
                  <div className="border-t border-rule/10 px-4 py-2">
                    <p className="text-[12px] text-text-secondary leading-snug">
                      <span className="text-[10px] uppercase tracking-widest text-text-muted/50 mr-1.5">
                        Grammar
                      </span>
                      {entry.grammar_note}
                    </p>
                  </div>
                )}

                {/* Definition */}
                {entry.definition && (
                  <div className="border-t border-rule/10 px-4 py-2">
                    <p
                      className={`text-[13px] text-text-secondary leading-relaxed ${
                        isArabic ? "text-right" : ""
                      }`}
                    >
                      {entry.definition}
                    </p>
                  </div>
                )}

                {/* Example sentences */}
                {examples.length > 0 && (
                  <div className="border-t border-rule/10 px-4 py-2">
                    <div className="space-y-1">
                      {examples.slice(0, 2).map((ex, i) => (
                        <p
                          key={i}
                          className={`text-[12px] leading-relaxed text-text-secondary ${
                            isArabic ? "text-right" : ""
                          }`}
                        >
                          {ex}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer actions */}
        <div
          className="mt-8 flex flex-col items-center gap-4 transition-opacity duration-300 ease-out"
          style={{ opacity: showFooter ? 1 : 0 }}
        >
          {/* Back to Briefing — primary */}
          {backHref && (
            <a
              href={backHref}
              className="inline-block rounded-full border border-rule bg-bg-surface px-6 py-2.5 font-ui text-[13px] font-medium text-accent-primary transition-colors hover:bg-bg-surface-2"
            >
              Back to Briefing
            </a>
          )}

          {/* Replay — subtle text link */}
          {onReplayLesson && (
            <button
              type="button"
              onClick={onReplayLesson}
              className="text-[13px] text-text-muted hover:text-text-secondary transition-colors cursor-pointer bg-transparent border-none p-0"
            >
              Replay Lesson
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
