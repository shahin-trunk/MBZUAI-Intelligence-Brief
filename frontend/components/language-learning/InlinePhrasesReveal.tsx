"use client";

import React from "react";
import type { LearningPhrase } from "@/lib/types/brief";

interface InlinePhrasesRevealProps {
  phrases: LearningPhrase[];
  isVisible: boolean;
  language: "fr" | "ar";
}

export default function InlinePhrasesReveal({
  phrases,
  isVisible,
  language,
}: InlinePhrasesRevealProps) {
  const isRTL = language === "ar";
  const align = isRTL ? "text-right" : "text-left";

  return (
    <div dir={isRTL ? "rtl" : "ltr"} className="space-y-4">
      {phrases.map((entry, idx) => {
        const examples = entry.example_sentences?.length
          ? entry.example_sentences
          : entry.example_sentence
            ? [entry.example_sentence]
            : [];

        return (
          <div
            key={`${entry.phrase}-${idx}`}
            className="rounded-xl border border-rule/20 bg-bg-surface/40 overflow-hidden transition-all duration-300 ease-out"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? "translateY(0)" : "translateY(12px)",
              transitionDelay: isVisible ? `${idx * 150}ms` : "0ms",
            }}
          >
            {/* Header: phrase + POS + translation */}
            <div className="px-4 pt-3.5 pb-3">
              <div className={`flex items-baseline justify-between gap-2 ${align}`}>
                <p className="text-[16px] font-semibold text-accent-primary leading-snug">
                  {entry.phrase}
                </p>
                {entry.part_of_speech && (
                  <span className="shrink-0 font-mono text-[10px] uppercase tracking-wide text-text-muted/60">
                    {entry.part_of_speech}
                  </span>
                )}
              </div>
              <p className={`text-[14px] text-text-secondary mt-0.5 ${align}`}>
                {entry.translation}
              </p>
            </div>

            {/* Linguistic details */}
            {(entry.grammar_note ||
              entry.pronunciation_guide ||
              entry.word_root ||
              entry.conjugation) && (
              <div className="border-t border-rule/10 px-4 py-2.5 space-y-1.5">
                {entry.grammar_note && (
                  <LingRow label="Grammar" value={entry.grammar_note} align={align} />
                )}
                {entry.pronunciation_guide && (
                  <LingRow label="Sound" value={entry.pronunciation_guide} align={align} />
                )}
                {entry.conjugation && (
                  <LingRow label="Forms" value={entry.conjugation} align={align} />
                )}
                {entry.word_root && (
                  <LingRow label="Root" value={entry.word_root} align={align} />
                )}
              </div>
            )}

            {/* Example sentences */}
            {examples.length > 0 && (
              <div className="border-t border-rule/10 px-4 py-2.5">
                <p className="text-[10px] uppercase tracking-widest text-text-muted/50 mb-1.5">
                  Examples
                </p>
                <div className="space-y-1.5">
                  {examples.slice(0, 3).map((ex, i) => (
                    <p
                      key={i}
                      className={`text-[13px] leading-relaxed text-text-secondary ${align}`}
                    >
                      {ex}
                    </p>
                  ))}
                </div>
              </div>
            )}

            {/* Register + context note */}
            {(entry.register || entry.context_note) && (
              <div className="border-t border-rule/10 px-4 py-2 flex flex-wrap gap-x-4 gap-y-1">
                {entry.register && (
                  <span className="text-[11px] text-text-muted italic">
                    {entry.register}
                  </span>
                )}
                {entry.context_note && (
                  <span className="text-[11px] text-text-muted italic">
                    {entry.context_note}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* Small helper for linguistic detail rows */
function LingRow({
  label,
  value,
  align,
}: {
  label: string;
  value: string;
  align: string;
}) {
  return (
    <div className={`flex gap-2 ${align}`}>
      <span className="shrink-0 text-[10px] uppercase tracking-widest text-text-muted/50 mt-px w-[52px]">
        {label}
      </span>
      <span className="text-[12px] leading-snug text-text-secondary">
        {value}
      </span>
    </div>
  );
}
