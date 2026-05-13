"use client";

import type { LearningVocabulary } from "@/lib/types/brief";

type LearnLang = "fr" | "ar";

interface LearningVocabularyPanelProps {
  vocabulary: LearningVocabulary[];
  language: LearnLang;
}

const posLabelClasses = "inline-block rounded-full border border-rule bg-bg-tertiary px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider text-text-muted";

export default function LearningVocabularyPanel({
  vocabulary,
  language,
}: LearningVocabularyPanelProps) {
  if (vocabulary.length === 0) {
    return (
      <p className="font-body text-sm text-text-muted">
        {language === "fr" ? "Aucun vocabulaire pour cet élément." : "لا توجد مفردات لهذا العنصر."}
      </p>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3">
      {vocabulary.map((entry, idx) => (
        <article
          key={idx}
          className="rounded-xl border border-rule bg-bg-surface p-4 transition-shadow hover:shadow-sm"
        >
          {/* English term */}
          <p className="font-display text-[15px] font-medium text-text-primary">
            {entry.term}
          </p>

          {/* Translation */}
          <p className="mt-1 font-body text-[16px] leading-snug text-accent-primary">
            {entry.translation}
          </p>

          {/* Definition */}
          {entry.definition && (
            <p className="mt-2 font-body text-[13px] leading-relaxed text-text-secondary">
              {entry.definition}
            </p>
          )}

          {/* Example sentence */}
          {entry.example_sentence && (
            <p className="mt-2 rounded-lg bg-bg-tertiary px-3 py-2 font-body text-[13px] italic leading-relaxed text-text-secondary">
              &ldquo;{entry.example_sentence}&rdquo;
            </p>
          )}

          {/* Part of speech */}
          {entry.part_of_speech && (
            <div className="mt-3 flex items-center gap-2">
              <span className={posLabelClasses}>
                {entry.part_of_speech}
              </span>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
