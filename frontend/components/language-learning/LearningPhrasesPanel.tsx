"use client";

import type { LearningPhrase } from "@/lib/types/brief";

type LearnLang = "fr" | "ar";

interface LearningPhrasesPanelProps {
  phrases: LearningPhrase[];
  language: LearnLang;
}

export default function LearningPhrasesPanel({
  phrases,
  language,
}: LearningPhrasesPanelProps) {
  if (phrases.length === 0) return null;

  const isArabic = language === "ar";

  return (
    <div className="space-y-3">
      {phrases.map((phrase, idx) => (
        <div
          key={idx}
          className="rounded-xl border border-rule bg-bg-surface p-4 transition-shadow hover:shadow-sm"
        >
          {/* Target language phrase */}
          <p
            className={`font-body text-[17px] font-medium leading-snug text-text-primary ${isArabic ? "text-right" : "text-left"}`}
            style={{ lineHeight: isArabic ? 1.9 : 1.6 }}
          >
            {phrase.phrase}
          </p>

          {/* English translation */}
          <p className="mt-1.5 font-body text-[14px] text-accent-primary">
            {phrase.translation}
          </p>

          {/* Context note */}
          {phrase.context_note && (
            <p
              className={`mt-2 font-body text-[13px] leading-relaxed text-text-secondary ${isArabic ? "text-right" : "text-left"}`}
            >
              {phrase.context_note}
            </p>
          )}

          {/* Example sentence */}
          {phrase.example_sentence && (
            <div
              className={`mt-2 rounded-lg bg-bg-tertiary px-3 py-2 ${isArabic ? "text-right" : "text-left"}`}
            >
              <p
                className="font-body text-[13px] italic leading-relaxed text-text-secondary"
                style={{ lineHeight: isArabic ? 1.9 : 1.6 }}
              >
                {phrase.example_sentence}
              </p>
            </div>
          )}

          {/* Part of speech */}
          {phrase.part_of_speech && (
            <div className="mt-2">
              <span className="inline-block rounded-full border border-rule bg-bg-tertiary px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                {phrase.part_of_speech}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
