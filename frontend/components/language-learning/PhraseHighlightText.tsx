"use client";

import { useMemo, useRef } from "react";

interface PhraseHighlightTextProps {
  script: string;
  language: "fr" | "ar";
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  highlightMode?: "word" | "group";
}

/** Estimate speaking time weight using syllable approximation */
function estimateWeight(text: string, isArabic: boolean): number {
  const words = text.trim().split(/\s+/).filter((w) => w.length > 0);
  if (words.length === 0) return 1;

  if (isArabic) {
    const punctuationPauses = (text.match(/[،.؟!؛:]/g) || []).length * 0.3;
    return words.length * 2 + punctuationPauses;
  } else {
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

function splitIntoChunks(
  script: string,
  language: "fr" | "ar",
  mode: "word" | "group",
): string[] {
  if (!script) return [];

  const isArabic = language === "ar";
  const chunkSize = mode === "word" ? 1 : (isArabic ? 2 : 4);

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
      groups.push(trimmed);
    } else {
      for (let i = 0; i < words.length; i += chunkSize) {
        const chunk = words.slice(i, i + chunkSize);
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

  // In group mode, merge very short groups with neighbor
  if (mode === "group") {
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

  return groups;
}

function useStableDuration(duration: number, threshold = 0.5): number {
  const lastGoodRef = useRef(0);
  if (duration > threshold && isFinite(duration)) {
    lastGoodRef.current = duration;
  }
  return duration > threshold && isFinite(duration) ? duration : lastGoodRef.current;
}

export default function PhraseHighlightText({
  script,
  language,
  currentTime,
  duration,
  isPlaying,
  highlightMode = "group",
}: PhraseHighlightTextProps) {
  const isArabic = language === "ar";

  const chunks = useMemo(
    () => splitIntoChunks(script, language, highlightMode),
    [script, language, highlightMode],
  );

  // Persist last reliable duration via ref so highlighting doesn't
  // flash/break during audio transitions (when duration briefly drops to 0)
  const stableDuration = useStableDuration(duration);
  const isAudioTimingReliable = stableDuration > 0.5 && isFinite(stableDuration);

  const chunkRanges = useMemo(() => {
    if (chunks.length === 0 || !isAudioTimingReliable) return [];

    const weights = chunks.map((c) => estimateWeight(c, isArabic));
    const totalWeight = weights.reduce((a, b) => a + b, 0);

    let cumulative = 0;
    return chunks.map((_, idx) => {
      const weight = weights[idx] / totalWeight;
      const start = cumulative * stableDuration;
      cumulative += weight;
      const end = cumulative * stableDuration;
      return { start, end };
    });
  }, [chunks, stableDuration, isArabic, isAudioTimingReliable]);

  const activeIndex = useMemo(() => {
    if (!isAudioTimingReliable) return -1;
    if (chunkRanges.length === 0) return -1;
    for (let i = 0; i < chunkRanges.length; i++) {
      if (currentTime < chunkRanges[i].end) return i;
    }
    return chunkRanges.length - 1;
  }, [currentTime, chunkRanges, isAudioTimingReliable]);

  const isInitial = currentTime === 0 && !isPlaying;

  if (chunks.length === 0) {
    return (
      <p
        className="font-body text-[22px] sm:text-[26px] lg:text-[28px] text-gray-200 text-center"
        style={{ lineHeight: 1.8 }}
      >
        {script}
      </p>
    );
  }

  if (!isAudioTimingReliable) {
    return (
      <div
        dir={isArabic ? "rtl" : "ltr"}
        className={`font-body text-center ${
          highlightMode === "word"
            ? "text-[28px] sm:text-[32px] lg:text-[36px]"
            : "text-[22px] sm:text-[26px] lg:text-[28px]"
        }`}
        style={{ lineHeight: 1.8 }}
      >
        <span className="text-gray-200">
          {chunks.map((chunk, idx) => (
            <span key={idx}>
              {chunk}
              {idx < chunks.length - 1 ? " " : ""}
            </span>
          ))}
        </span>
      </div>
    );
  }

  return (
    <div
      dir={isArabic ? "rtl" : "ltr"}
      className={`font-body text-center ${
        highlightMode === "word"
          ? "text-[28px] sm:text-[32px] lg:text-[36px]"
          : "text-[22px] sm:text-[26px] lg:text-[28px]"
      }`}
      style={{ lineHeight: 1.8 }}
    >
      {chunks.map((chunk, idx) => {
        const isActive = idx === activeIndex;
        const isPast = activeIndex >= 0 && idx < activeIndex;

        let className = "transition-colors duration-300 ease-out inline ";

        if (isInitial) {
          className += "text-gray-400";
        } else if (isActive) {
          className += "text-indigo-300 font-semibold";
        } else if (isPast) {
          className += "text-gray-200";
        } else {
          className += "text-gray-500";
        }

        return (
          <span key={idx} className={className}>
            {chunk}
            {idx < chunks.length - 1 ? " " : ""}
          </span>
        );
      })}
    </div>
  );
}
