"use client";

import { useMemo } from "react";

interface SectionNarrativeTextProps {
  script: string;
  language: "fr" | "ar";
  currentTime: number;
  duration: number;
  isPlaying: boolean;
}

/**
 * Splits the script into sentences and highlights the current one
 * based on proportional time estimation (karaoke-style).
 */
export default function SectionNarrativeText({
  script,
  language,
  currentTime,
  duration,
  isPlaying,
}: SectionNarrativeTextProps) {
  const isArabic = language === "ar";

  // Split script into sentences
  const sentences = useMemo(() => {
    if (!script) return [];
    // Arabic uses different punctuation
    const pattern = isArabic
      ? /(?<=[.!?،؟۔])\s+/
      : /(?<=[.!?])\s+/;
    return script.split(pattern).filter((s) => s.trim().length > 0);
  }, [script, isArabic]);

  // Compute time ranges for each sentence based on character proportion
  const sentenceRanges = useMemo(() => {
    if (sentences.length === 0 || duration <= 0) return [];
    const totalChars = sentences.reduce((sum, s) => sum + s.length, 0);
    let cumulative = 0;
    return sentences.map((s) => {
      const weight = s.length / totalChars;
      const start = cumulative * duration;
      cumulative += weight;
      const end = cumulative * duration;
      return { start, end };
    });
  }, [sentences, duration]);

  // Determine which sentence is active
  const activeIndex = useMemo(() => {
    if (!isPlaying && currentTime === 0) return -1;
    if (sentenceRanges.length === 0) return -1;
    for (let i = 0; i < sentenceRanges.length; i++) {
      if (currentTime < sentenceRanges[i].end) return i;
    }
    return sentenceRanges.length - 1;
  }, [currentTime, sentenceRanges, isPlaying]);

  if (sentences.length === 0) {
    return (
      <p
        className={`font-body text-[18px] leading-relaxed text-text-primary sm:text-[20px] ${isArabic ? "text-right" : "text-left"}`}
        style={{ lineHeight: isArabic ? 2.0 : 1.75 }}
      >
        {script}
      </p>
    );
  }

  return (
    <div
      className={isArabic ? "text-right" : "text-left"}
      style={{ lineHeight: isArabic ? 2.0 : 1.75 }}
    >
      {sentences.map((sentence, idx) => {
        const isActive = idx === activeIndex;
        const isPast = activeIndex >= 0 && idx < activeIndex;
        return (
          <span
            key={idx}
            className={`font-body text-[18px] transition-colors duration-300 sm:text-[20px] ${
              isActive
                ? "text-accent-primary font-medium"
                : isPast
                  ? "text-text-primary"
                  : "text-text-secondary/60"
            }`}
          >
            {sentence}
            {idx < sentences.length - 1 ? " " : ""}
          </span>
        );
      })}
    </div>
  );
}
