"use client";

import { useMemo, useRef, useEffect } from "react";

interface PhraseHighlightTextProps {
  script: string;
  language: "fr" | "ar";
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  highlightMode?: "word" | "group";
}

// ---------------------------------------------------------------------------
// Module-level duration cache — persists across component remounts so that
// when PhraseCard switches keys (script/phrase transition), the NEW instance
// already knows the previous script's duration and can highlight immediately
// instead of waiting for loadedmetadata.
// ---------------------------------------------------------------------------
const scriptDurationCache = new Map<string, number>();

function getCachedDuration(scriptText: string): number {
  return scriptDurationCache.get(scriptText) ?? 0;
}

function updateCachedDuration(scriptText: string, duration: number) {
  scriptDurationCache.set(scriptText, duration);
}

/** Fallback duration estimate from text length when no real duration is known yet. */
function estimateDurationFromText(text: string): number {
  if (!text) return 0;
  const words = text.trim().split(/\s+/).filter((w) => w.length > 0).length;
  if (words === 0) return 0;
  // TTS: ~2 words/second with pauses; also account for char-length for long words
  const byWords = words / 2;
  const byChars = text.length * 0.065;
  return Math.max(1.5, byWords, byChars);
}

/** Estimate speaking time weight for a single chunk. Uses syllable approximation
 *  for French, word-count-based for Arabic. Guarantees a minimum weight so no
 *  chunk gets an invisibly short duration. */
function estimateWeight(text: string, isArabic: boolean): number {
  const words = text.trim().split(/\s+/).filter((w) => w.length > 0);
  if (words.length === 0) return 1;

  let base: number;
  if (isArabic) {
    const punctuationPauses = (text.match(/[،.؟!؛:]/g) || []).length * 0.3;
    base = words.length * 2 + punctuationPauses;
  } else {
    let syllables = 0;
    for (const word of words) {
      const vowelGroups =
        word.match(/[aeiouyéèêëàâîôûùüïÿæœ]+/gi) || [];
      syllables += Math.max(1, vowelGroups.length);
    }
    const punctuationPauses = (text.match(/[.!?;:,]/g) || []).length * 0.2;
    base = syllables + punctuationPauses;
  }
  // Floor so even a tiny chunk gets a meaningful slice of the timeline
  return Math.max(base, 0.5);
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

/** Small silence buffer at the start of TTS audio — prevents highlighting from
 *  jumping to the first word before it's actually spoken. */
const START_SILENCE_BUFFER = 0.15;

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

  // -------------------------------------------------------------------
  // Three-layer duration fallback:
  //   1. Live `duration` from the audio element (most authoritative)
  //   2. Module-level cache from a previous render of this script text
  //   3. Text-length estimate (cold start, first-ever play of this text)
  // -------------------------------------------------------------------
  const liveOk = duration > 0.3 && isFinite(duration);

  // Persist live duration into the module cache
  if (liveOk) {
    updateCachedDuration(script, duration);
  }

  // Determine the duration we'll actually use
  const stableDuration = useMemo(() => {
    if (liveOk) return duration;
    const cached = getCachedDuration(script);
    if (cached > 0.3) return cached;
    return estimateDurationFromText(script);
  }, [duration, script, liveOk]);

  const isAudioTimingReliable =
    stableDuration > 0.3 && isFinite(stableDuration);

  // We use a ref to remember the last "reliable" timing state so we don't
  // flash from "highlighted" -> "plain" then back during short hiccups.
  const wasReliableRef = useRef(false);
  if (isAudioTimingReliable) {
    wasReliableRef.current = true;
  }

  // If we have no timing data AND never had any, fall through to plain text.
  // If we HAD reliable timing but briefly lost it, keep using the cached one.
  const isInitiallyLoading = !isAudioTimingReliable && !wasReliableRef.current;

  // -------------------------------------------------------------------
  // Build chunk time ranges from weight-proportional distribution.
  // -------------------------------------------------------------------
  const chunkRanges = useMemo(() => {
    if (chunks.length === 0 || !isAudioTimingReliable) return [];

    const weights = chunks.map((c) => estimateWeight(c, isArabic));
    const totalWeight = weights.reduce((a, b) => a + b, 0);

    // Reserve the START_SILENCE_BUFFER at the beginning and distribute the
    // remaining usable duration proportionally across chunks.
    const usableDuration = stableDuration - START_SILENCE_BUFFER;

    let cumulative = 0;
    return chunks.map((_, idx) => {
      const ratio = weights[idx] / totalWeight;
      const start = START_SILENCE_BUFFER + cumulative * usableDuration;
      cumulative += ratio;
      // Force the last chunk's end to exactly equal stableDuration,
      // preventing floating-point accumulation drift.
      const end =
        idx === chunks.length - 1
          ? stableDuration
          : START_SILENCE_BUFFER + cumulative * usableDuration;
      return { start, end };
    });
  }, [chunks, stableDuration, isArabic, isAudioTimingReliable]);

  // -------------------------------------------------------------------
  // Raw active chunk index computed directly from currentTime.
  // This value can jump multiple chunks when coarse timeupdate events
  // (typically 250ms intervals) skip past narrow chunk boundaries.
  // -------------------------------------------------------------------
  const rawActiveIndex = useMemo(() => {
    if (!isAudioTimingReliable) return -1;
    if (chunkRanges.length === 0) return -1;

    // At or before the first chunk's start -> first chunk is active.
    if (currentTime <= chunkRanges[0].start) return 0;

    for (let i = 0; i < chunkRanges.length; i++) {
      // Small hysteresis buffer (50ms) inside each chunk endpoint.
      // Prevents rapid back-and-forth when currentTime wavers near a
      // boundary (e.g. from timeupdate rounding variance).
      if (currentTime < chunkRanges[i].end - 0.05) return i;
    }
    return chunkRanges.length - 1;
  }, [currentTime, chunkRanges, isAudioTimingReliable]);

  // -------------------------------------------------------------------
  // Smoothed active index computed via ref-based clamping.
  //
  // Unlike the previous useState + useEffect approach (which suffered
  // from an effect-ordering bug: the clamp effect would read a stale
  // `prev` from the functional updater when the script-reset effect
  // ran after it in the same commit), this computes the clamp inline
  // during render using a ref to the LAST committed index.
  //
  // The ref is persisted across renders via useEffect (no deps, runs
  // after every commit). Since the clamping only depends on the ref
  // and the raw input props, it's always consistent with the current
  // render's data — even after script changes.
  // -------------------------------------------------------------------
  const lastCommittedRef = useRef(-1);

  const activeIndex = useMemo(() => {
    if (rawActiveIndex < 0 || chunkRanges.length === 0) return -1;

    if (isPlaying && lastCommittedRef.current >= 0) {
      // During playback: advance at most one chunk per update.
      // Never go backward unless currentTime was clearly reset.
      if (rawActiveIndex > lastCommittedRef.current + 1) {
        return lastCommittedRef.current + 1;
      }
      if (rawActiveIndex >= lastCommittedRef.current) {
        return rawActiveIndex;
      }
      if (currentTime <= chunkRanges[0].start + 0.1) {
        // currentTime was reset — new phrase or seek to start
        return rawActiveIndex;
      }
      return lastCommittedRef.current;
    }

    // Not playing: use raw index directly (paused, seeking, script change)
    return rawActiveIndex;
  }, [rawActiveIndex, isPlaying, chunkRanges, currentTime]);

  // Persist the active index ref after every render so the NEXT
  // render's useMemo sees the last committed value for clamping.
  // No deps array — intentionally runs after every commit.
  useEffect(() => {
    lastCommittedRef.current = activeIndex;
  });

  // -------------------------------------------------------------------
  // Auto-focus: scroll the active chunk into view for a smooth
  // reading experience that follows the audio playback position.
  // -------------------------------------------------------------------
  const activeChunkRef = useRef<HTMLSpanElement | null>(null);
  const prevActiveRef = useRef(-1);

  useEffect(() => {
    if (
      activeIndex >= 0 &&
      activeIndex !== prevActiveRef.current &&
      activeChunkRef.current
    ) {
      activeChunkRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
      prevActiveRef.current = activeIndex;
    }
  }, [activeIndex]);

  const isInitial = currentTime === 0 && !isPlaying && !isInitiallyLoading;

  if (chunks.length === 0) {
    return (
      <p
        className="font-body text-[22px] sm:text-[26px] lg:text-[28px] text-text-primary text-center"
        style={{ lineHeight: 1.8 }}
      >
        {script}
      </p>
    );
  }

  // -------------------------------------------------------------------
  // Timing-unavailable render — used only on very first load before any
  // duration information arrives (cold start). We still show the text
  // plainly but mark it as muted to indicate "loading".
  // -------------------------------------------------------------------
  if (isInitiallyLoading) {
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
        <span className="text-text-muted">
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

  // -------------------------------------------------------------------
  // Normal highlighted render
  // -------------------------------------------------------------------
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

        if (isActive) {
          // Active chunk is always highlighted — this check must come BEFORE
          // isInitial so that the first chunk shows accent-primary immediately
          // on mount, rather than being swallowed by the isInitial dimmed state.
          className += "text-accent-primary font-semibold";
        } else if (isPast) {
          className += "text-text-primary";
        } else if (isInitial) {
          className += "text-text-secondary";
        } else {
          className += "text-text-muted";
        }

        return (
          <span
            key={idx}
            ref={(el) => {
              if (isActive) activeChunkRef.current = el;
            }}
            className={className}
          >
            {chunk}
            {idx < chunks.length - 1 ? " " : ""}
          </span>
        );
      })}
    </div>
  );
}
