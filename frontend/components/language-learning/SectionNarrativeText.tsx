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
 * Splits the script into word-groups and highlights the active group
 * with smooth karaoke-style transitions for cinematic reading flow.
 */

/** Estimate speaking time weight using syllable approximation */
function estimateWeight(text: string, isArabic: boolean): number {
  const words = text.trim().split(/\s+/).filter((w) => w.length > 0);
  if (words.length === 0) return 1;

  if (isArabic) {
    // Arabic: roughly 2 syllables per word, plus pauses at punctuation
    const punctuationPauses = (text.match(/[،.؟!؛:]/g) || []).length * 0.3;
    return words.length * 2 + punctuationPauses;
  } else {
    // Bilingual English + target language: count vowel clusters as syllable proxy
    let syllables = 0;
    for (const word of words) {
      const vowelGroups =
        word.match(/[aeiouyéèêëàâîôûùüïÿæœ]+/gi) || [];
      syllables += Math.max(1, vowelGroups.length);
    }
    const punctuationPauses = (text.match(/[.!?;:,]/g) || []).length * 0.2;
    return syllables + punctuationPauses;
  }
}

function splitIntoWordGroups(script: string, language: "fr" | "ar"): string[] {
  if (!script) return [];

  const isArabic = language === "ar";
  const chunkSize = isArabic ? 2 : 4;

  // Split on sentence-level punctuation first
  const punctPattern = isArabic
    ? /([^،.؟!؛:]+[،.؟!؛:]?)/g
    : /([^.!?;:,]+[.!?;:,]?)/g;

  const clauses =
    script.match(punctPattern)?.filter((c) => c.trim().length > 0) || [];

  const groups: string[] = [];

  for (const clause of clauses) {
    const trimmed = clause.trim();
    if (!trimmed) continue;

    const words = trimmed.split(/\s+/).filter((w) => w.length > 0);

    if (words.length <= chunkSize + 1) {
      // Keep small clauses as a single group
      groups.push(trimmed);
    } else {
      // Split into chunks of chunkSize words
      for (let i = 0; i < words.length; i += chunkSize) {
        const chunk = words.slice(i, i + chunkSize);
        // If remainder is only 1-2 words, merge with current chunk
        const remaining = words.length - (i + chunkSize);
        if (remaining > 0 && remaining <= 2) {
          chunk.push(...words.slice(i + chunkSize));
          groups.push(chunk.join(" "));
          break;
        }
        groups.push(chunk.join(" "));
      }
    }
  }

  // Merge very short groups (<2 words) with their neighbor
  const merged: string[] = [];
  for (let i = 0; i < groups.length; i++) {
    const wordCount = groups[i].trim().split(/\s+/).length;
    if (wordCount < 2 && merged.length > 0) {
      merged[merged.length - 1] += " " + groups[i];
    } else {
      merged.push(groups[i]);
    }
  }

  return merged;
}

export default function SectionNarrativeText({
  script,
  language,
  currentTime,
  duration,
  isPlaying,
}: SectionNarrativeTextProps) {
  const isArabic = language === "ar";

  // Split script into word-groups
  const groups = useMemo(
    () => splitIntoWordGroups(script, language),
    [script, language]
  );

  // Compute time ranges for each group based on syllable-weighted proportion
  const groupRanges = useMemo(() => {
    if (groups.length === 0 || duration <= 0) return [];

    const weights = groups.map((g) => estimateWeight(g, isArabic));
    const totalWeight = weights.reduce((a, b) => a + b, 0);

    let cumulative = 0;
    return groups.map((_, idx) => {
      const weight = weights[idx] / totalWeight;
      const start = cumulative * duration;
      cumulative += weight;
      const end = cumulative * duration;
      return { start, end };
    });
  }, [groups, duration, isArabic]);

  // Determine which group is active
  const activeIndex = useMemo(() => {
    if (!isPlaying && currentTime === 0) return -1;
    if (groupRanges.length === 0) return -1;
    for (let i = 0; i < groupRanges.length; i++) {
      if (currentTime < groupRanges[i].end) return i;
    }
    return groupRanges.length - 1;
  }, [currentTime, groupRanges, isPlaying]);

  if (groups.length === 0) {
    return (
      <p
        className={`font-body text-[22px] sm:text-[26px] lg:text-[28px] text-text-primary text-center`}
        style={{ lineHeight: 1.8 }}
      >
        {script}
      </p>
    );
  }

  const idle = !isPlaying && currentTime === 0;

  return (
    <div
      dir={isArabic ? "rtl" : "ltr"}
      className={`font-body text-center text-[22px] sm:text-[26px] lg:text-[28px]`}
      style={{ lineHeight: 1.8 }}
    >
      {groups.map((group, idx) => {
        const isActive = idx === activeIndex;
        const isPast = activeIndex >= 0 && idx < activeIndex;

        let className =
          "transition-colors duration-300 ease-out inline ";

        if (idle) {
          className += "text-text-primary opacity-60";
        } else if (isActive) {
          className += "text-accent-primary font-medium";
        } else if (isPast) {
          className += "text-text-primary opacity-100";
        } else {
          className += "text-text-secondary/50";
        }

        return (
          <span key={idx} className={className}>
            {group}
            {idx < groups.length - 1 ? " " : ""}
          </span>
        );
      })}
    </div>
  );
}
