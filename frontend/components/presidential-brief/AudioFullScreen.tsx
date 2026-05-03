"use client";

import { ChevronDown, Loader2, Pause, Play, RotateCcw, RotateCw } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { AudioPlayerState, AudioPlayerActions } from "@/lib/presidential-brief/hooks/useAudioPlayer";
import { formatBriefDateShort, formatTime } from "@/lib/utils";

const MOCK_TRANSCRIPT =
  "Today's MBZUAI Intelligence Brief. April 6th, 2026. 8 stories.\n\nUAE. The UAE government announced a 2 billion dollar sovereign AI fund targeting regional startups, with initial deployment expected in Q3. ADNOC signed a multi-year research agreement with Google DeepMind for industrial AI applications.\n\nInternational Politics. The EU AI Act enforcement timeline has been accelerated to January 2027, compressing the compliance window by six months. China unveiled a national AI compute infrastructure plan spanning 10 provinces.\n\nModel Releases. Meta open-sourced Llama 4 Maverick, a 400 billion parameter mixture of experts model with 128 expert modules. Google DeepMind achieved a 10x protein folding speed improvement.\n\nEnd of brief.";

function stripSsmlForDisplay(text: string): string {
  return text
    .replace(/<break\b[^>]*\/?>/gi, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function splitTranscriptParagraphs(raw: string): string[] {
  const cleaned = stripSsmlForDisplay(raw);
  const chunks = cleaned
    .split(/\n\s*\n/)
    .map((s) => s.trim().replace(/\s+/g, " "))
    .filter(Boolean);
  if (chunks.length > 0) return chunks;
  const single = cleaned.trim();
  return single ? [single] : [];
}

/** Top breathing room so the first line is not clipped after scroll; avoids scrollIntoView overshoot with layout transitions. */
const TRANSCRIPT_SCROLL_TOP_INSET_PX = 12;

function scrollTranscriptSegmentIntoView(
  scroller: HTMLElement,
  el: HTMLElement,
  behavior: ScrollBehavior,
) {
  const scrollerRect = scroller.getBoundingClientRect();
  const elRect = el.getBoundingClientRect();
  const delta = elRect.top - scrollerRect.top;
  const nextTop = scroller.scrollTop + delta - TRANSCRIPT_SCROLL_TOP_INSET_PX;
  scroller.scrollTo({ top: Math.max(0, nextTop), behavior });
}

function allocateSegmentTimes(
  paragraphs: string[],
  durationSec: number,
): { text: string; startSec: number; endSec: number }[] {
  if (paragraphs.length === 0) return [];
  if (durationSec <= 0) {
    return paragraphs.map((text) => ({ text, startSec: 0, endSec: 0 }));
  }
  const weights = paragraphs.map((p) => Math.max(p.length, 1));
  const totalW = weights.reduce((a, b) => a + b, 0);
  let acc = 0;
  const out = paragraphs.map((text, i) => {
    const len = (weights[i]! / totalW) * durationSec;
    const startSec = acc;
    acc += len;
    return { text, startSec, endSec: acc };
  });
  if (out.length > 0) {
    out[out.length - 1]!.endSec = durationSec;
  }
  return out;
}

interface AudioFullScreenProps {
  player: AudioPlayerState & AudioPlayerActions;
  briefDate: string;
  transcript?: string;
  /** Used when audio language is French. Falls back to `transcript` if omitted. */
  transcriptFr?: string;
  onClose: () => void;
  linkedStoryIds?: string[];
  onOpenStoryDetail?: (itemId: string) => void;
  /** When true, sheet sits above this overlay; keep mounted so closing the sheet does not replay the enter animation. */
  behindStoryDetail?: boolean;
}

export default function AudioFullScreen({
  player,
  briefDate,
  transcript,
  transcriptFr,
  onClose,
  linkedStoryIds,
  onOpenStoryDetail,
  behindStoryDetail = false,
}: AudioFullScreenProps) {
  const {
    isPlaying,
    isLoading,
    progress,
    formattedTime,
    duration,
    speed,
    language,
    hasEnglishAudio,
    hasFrenchAudio,
    currentTime,
    togglePlayPause,
    seek,
    cycleSpeed,
    setLanguage,
  } = player;

  const scrubRef = useRef<HTMLDivElement | null>(null);
  const transcriptScrollerRef = useRef<HTMLDivElement | null>(null);
  const transcriptInnerRef = useRef<HTMLDivElement | null>(null);
  const transcriptEndSpacerRef = useRef<HTMLDivElement | null>(null);
  const closeStartedRef = useRef(false);
  const lyricLineRefs = useRef<(HTMLDivElement | null)[]>([]);
  const transcriptScrollBehaviorRef = useRef<ScrollBehavior>("smooth");
  const transcriptInitialScrollDoneRef = useRef(false);
  const [panelEntered, setPanelEntered] = useState(false);
  const [transcriptEndSpacerPx, setTranscriptEndSpacerPx] = useState(0);
  const scrubbingRef = useRef(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => setPanelEntered(true));
    });
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    if (!panelEntered) {
      transcriptInitialScrollDoneRef.current = false;
    }
  }, [panelEntered]);

  const closeWithAnimation = useCallback(() => {
    if (closeStartedRef.current) return;
    closeStartedRef.current = true;
    setPanelEntered(false);
    window.setTimeout(() => onClose(), 320);
  }, [onClose]);

  const seekFromScrubClientX = useCallback(
    (clientX: number) => {
      if (!duration || !scrubRef.current) return;
      const rect = scrubRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      seek(ratio * duration);
    },
    [duration, seek],
  );

  const onScrubPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!duration) return;
      scrubbingRef.current = true;
      e.currentTarget.setPointerCapture(e.pointerId);
      seekFromScrubClientX(e.clientX);
    },
    [duration, seekFromScrubClientX],
  );

  const onScrubPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!scrubbingRef.current) return;
      seekFromScrubClientX(e.clientX);
    },
    [seekFromScrubClientX],
  );

  const onScrubPointerUp = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    scrubbingRef.current = false;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  }, []);

  const skipDeltaSec = 10;

  const skipBack = useCallback(() => {
    seek(Math.max(0, currentTime - skipDeltaSec));
  }, [currentTime, seek]);

  const skipForward = useCallback(() => {
    if (duration) seek(Math.min(duration, currentTime + skipDeltaSec));
  }, [currentTime, duration, seek]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (behindStoryDetail) return;
      if (e.key === "Escape") closeWithAnimation();
      if (e.key === "ArrowLeft") skipBack();
      if (e.key === "ArrowRight") skipForward();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [behindStoryDetail, closeWithAnimation, skipBack, skipForward]);

  const scriptRaw =
    language === "fr" ? (transcriptFr?.trim() ? transcriptFr : transcript) : transcript;
  const displayTranscript = scriptRaw?.trim()
    ? stripSsmlForDisplay(scriptRaw)
    : MOCK_TRANSCRIPT;

  const speedLabel = speed === 1 ? "1×" : `${speed}×`;
  const titleLine = `Daily brief for ${formatBriefDateShort(briefDate)}`;
  const remainingSeconds = duration > 0 ? Math.max(0, duration - currentTime) : 0;
  const remainingLabel = duration > 0 ? `-${formatTime(remainingSeconds)}` : "—";

  const lyricRanges = useMemo(() => {
    const paragraphs = splitTranscriptParagraphs(displayTranscript);
    return allocateSegmentTimes(paragraphs, duration);
  }, [displayTranscript, duration]);

  const lyricActiveIndex = useMemo(() => {
    if (lyricRanges.length === 0) return 0;
    if (duration <= 0) return 0;
    const idx = lyricRanges.findIndex((r) => currentTime >= r.startSec && currentTime < r.endSec);
    if (idx !== -1) return idx;
    const last = lyricRanges[lyricRanges.length - 1]!;
    if (currentTime >= last.endSec) return lyricRanges.length - 1;
    return 0;
  }, [currentTime, duration, lyricRanges]);

  useEffect(() => {
    const scroller = transcriptScrollerRef.current;
    const inner = transcriptInnerRef.current;
    if (!scroller || !inner || !panelEntered) return;

    const updateSpacer = () => {
      const lastIdx = lyricRanges.length - 1;
      if (lastIdx < 0) {
        setTranscriptEndSpacerPx((p) => (p === 0 ? p : 0));
        return;
      }
      const lastEl = lyricLineRefs.current[lastIdx];
      if (!lastEl) {
        setTranscriptEndSpacerPx((p) => (p === 0 ? p : 0));
        return;
      }

      const H = scroller.clientHeight;
      const topLast =
        lastEl.getBoundingClientRect().top - inner.getBoundingClientRect().top;
      const curSpacerH = transcriptEndSpacerRef.current?.offsetHeight ?? 0;
      const baseLessSpacer = inner.scrollHeight - curSpacerH;
      const neededInnerHeight = H + topLast - TRANSCRIPT_SCROLL_TOP_INSET_PX;
      const newS = Math.max(0, Math.round(neededInnerHeight - baseLessSpacer));

      setTranscriptEndSpacerPx((prev) => (prev === newS ? prev : newS));
    };

    updateSpacer();
    const raf = requestAnimationFrame(updateSpacer);
    const ro = new ResizeObserver(updateSpacer);
    ro.observe(scroller);
    ro.observe(inner);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [panelEntered, lyricRanges, lyricActiveIndex]);

  useLayoutEffect(() => {
    const scroller = transcriptScrollerRef.current;
    if (!scroller) return;
    const max = scroller.scrollHeight - scroller.clientHeight;
    if (scroller.scrollTop > max + 0.5) {
      scroller.scrollTop = Math.max(0, max);
    }
  }, [transcriptEndSpacerPx]);

  useLayoutEffect(() => {
    if (!panelEntered) return;
    const el = lyricLineRefs.current[lyricActiveIndex];
    const scroller = transcriptScrollerRef.current;
    if (!el || !scroller) return;

    const firstLayout = !transcriptInitialScrollDoneRef.current;
    const behavior: ScrollBehavior = firstLayout ? "auto" : transcriptScrollBehaviorRef.current;
    transcriptScrollBehaviorRef.current = "smooth";
    if (firstLayout) {
      transcriptInitialScrollDoneRef.current = true;
    }

    const apply = () => scrollTranscriptSegmentIntoView(scroller, el, behavior);
    if (behavior === "auto") {
      apply();
      const id = requestAnimationFrame(apply);
      return () => cancelAnimationFrame(id);
    }
    const id = requestAnimationFrame(apply);
    return () => cancelAnimationFrame(id);
  }, [lyricActiveIndex, panelEntered]);

  /** Nudge past segment boundary so float math does not leave playhead in the previous block when paused. */
  const TRANSCRIPT_SEEK_EPS = 0.05;

  const seekToSegmentStart = useCallback(
    (startSec: number, segmentIndex: number) => {
      if (!Number.isFinite(duration) || duration <= 0) return;
      transcriptScrollBehaviorRef.current = "smooth";
      const upper = Math.max(0, duration - 0.02);
      const t = Math.min(upper, Math.max(0, startSec + TRANSCRIPT_SEEK_EPS));
      const sameSegment = segmentIndex === lyricActiveIndex;
      seek(t);
      if (sameSegment) {
        queueMicrotask(() => {
          requestAnimationFrame(() => {
            const scroller = transcriptScrollerRef.current;
            const el = lyricLineRefs.current[segmentIndex];
            if (scroller && el) {
              requestAnimationFrame(() =>
                scrollTranscriptSegmentIntoView(scroller, el, "smooth"),
              );
            }
          });
        });
      }
    },
    [duration, lyricActiveIndex, seek],
  );

  const canSeekTranscript =
    Number.isFinite(duration) && duration > 0;

  return (
    <div
      className={`fixed inset-0 flex h-[100dvh] max-h-[100dvh] w-full max-w-none flex-col overflow-hidden bg-bg-primary ${
        behindStoryDetail
          ? "pointer-events-none z-[54] translate-y-0"
          : `z-[60] transition-transform duration-[320ms] ease-[cubic-bezier(0.22,1,0.36,1)] ${
              panelEntered ? "translate-y-0" : "translate-y-full"
            }`
      }`}
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      role="dialog"
      aria-modal={behindStoryDetail ? "false" : "true"}
      aria-hidden={behindStoryDetail}
      aria-label="Audio player"
    >
      <div
        className="relative flex min-h-0 flex-1 flex-col overflow-hidden"
        style={{ paddingTop: "max(8px, env(safe-area-inset-top))" }}
      >
        <div className="grid flex-shrink-0 grid-cols-[2.75rem_1fr_2.75rem] items-center gap-2 px-4 pb-2 pt-0.5">
          <button
            type="button"
            onClick={closeWithAnimation}
            className="flex h-11 w-11 items-center justify-center justify-self-start rounded-full text-text-primary transition-colors active:bg-bg-surface-2"
            aria-label="Minimize player"
          >
            <ChevronDown className="h-5 w-5 shrink-0" strokeWidth={2} aria-hidden />
          </button>
          <h2 className="min-w-0 max-w-full justify-self-center truncate text-center font-display text-[18px] font-normal leading-snug tracking-[-0.01em] text-text-primary sm:text-[20px] md:text-[21px]">
            {titleLine}
          </h2>
          <span className="h-11 w-11 justify-self-end" aria-hidden />
        </div>

        <div className="flex min-h-0 flex-1 flex-col px-6 pb-4">
          <div className="flex min-h-0 flex-1 flex-col gap-3 px-2 pb-4">
            <div className="relative min-h-0 flex-1 overflow-hidden" aria-label="Transcript">
              <div
                ref={transcriptScrollerRef}
                className="h-full overflow-y-auto overflow-x-hidden [-webkit-overflow-scrolling:touch] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              >
                <div ref={transcriptInnerRef} className="flex flex-col gap-8 py-5">
                  {lyricRanges.length === 0 ? (
                    <p className="text-center font-body text-[16px] text-text-muted">
                      No transcript text
                    </p>
                  ) : (
                    lyricRanges.map((range, index) => {
                      const isActive = index === lyricActiveIndex;
                      const linkedId = linkedStoryIds?.[index];
                      const isIntroOrOutroBlock =
                        lyricRanges.length > 1 &&
                        (index === 0 || index === lyricRanges.length - 1);
                      const showDetails = Boolean(
                        linkedId &&
                          onOpenStoryDetail &&
                          !isIntroOrOutroBlock
                      );
                      return (
                        <div
                          key={`${index}-${range.startSec}`}
                          ref={(el) => {
                            lyricLineRefs.current[index] = el;
                          }}
                          className={[
                            "mx-auto box-border flex w-full max-w-md flex-col items-stretch gap-2 px-3 text-center transition-[background-color,box-shadow] duration-300 ease-out",
                            isActive
                              ? "scale-100 rounded-2xl bg-bg-surface-2 pb-2.5 pt-2"
                              : "scale-[0.992] rounded-2xl py-0.5",
                          ].join(" ")}
                        >
                          <button
                            type="button"
                            onClick={() => seekToSegmentStart(range.startSec, index)}
                            disabled={!canSeekTranscript}
                            className={[
                              "w-full touch-manipulation text-center transition-[font-weight,color] duration-300 outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary disabled:pointer-events-none disabled:opacity-40",
                              isActive
                                ? "font-semibold text-text-primary"
                                : "font-normal text-text-primary/72 dark:text-text-primary/68",
                            ].join(" ")}
                            aria-label={`Seek to ${formatTime(range.startSec)}`}
                          >
                            <span className="font-body text-[16px] leading-[1.65] tracking-[-0.01em]">
                              {range.text}
                            </span>
                          </button>
                          {showDetails ? (
                            <div className="flex w-full justify-center">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (linkedId) onOpenStoryDetail?.(linkedId);
                                }}
                                className={[
                                  "inline-flex min-h-7 shrink-0 touch-manipulation items-center justify-center rounded-full border px-3.5 py-1 font-ui text-[12px] font-medium leading-none transition-colors",
                                  isActive
                                    ? "border-transparent bg-bg-surface text-text-secondary backdrop-blur-sm active:bg-bg-surface-2"
                                    : "border-rule bg-bg-surface text-text-secondary active:bg-bg-surface-2",
                                ].join(" ")}
                              >
                                View details
                              </button>
                            </div>
                          ) : null}
                        </div>
                      );
                    })
                  )}
                  {lyricRanges.length > 0 ? (
                    <div
                      ref={transcriptEndSpacerRef}
                      className="shrink-0"
                      style={{ minHeight: transcriptEndSpacerPx }}
                      aria-hidden
                    />
                  ) : null}
                </div>
              </div>
              {/* Fade transcript into chrome above scrubber — short band so fade sits close to the scrubber */}
              <div
                className="pointer-events-none absolute inset-x-0 bottom-0 z-[1] h-16 bg-[linear-gradient(to_top,var(--bg-primary)_0%,var(--bg-primary)_20%,color-mix(in_oklab,var(--bg-primary)_48%,transparent)_55%,transparent_100%)] sm:h-[4.75rem]"
                aria-hidden
              />
            </div>

            {/* Scrubber + transport share max-w-md so side controls sit closer to center */}
            <div className="mx-auto flex w-full max-w-md shrink-0 flex-col gap-5">
              <div>
                <div
                  ref={scrubRef}
                  role="slider"
                  aria-label="Seek"
                  aria-valuenow={Math.round(progress * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  tabIndex={0}
                  className="relative w-full cursor-pointer touch-none py-3 outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary"
                  onPointerDown={onScrubPointerDown}
                  onPointerMove={onScrubPointerMove}
                  onPointerUp={onScrubPointerUp}
                  onPointerCancel={onScrubPointerUp}
                  onKeyDown={(e) => {
                    if (!duration) return;
                    if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
                      e.preventDefault();
                      seek(Math.max(0, currentTime - skipDeltaSec));
                    }
                    if (e.key === "ArrowRight" || e.key === "ArrowUp") {
                      e.preventDefault();
                      seek(Math.min(duration, currentTime + skipDeltaSec));
                    }
                  }}
                >
                  <div className="relative h-[3px] w-full rounded-full bg-rule">
                    <div
                      className="absolute inset-y-0 left-0 rounded-full bg-text-primary"
                      style={{ width: `${progress * 100}%` }}
                    />
                    <div
                      className="absolute top-1/2 h-3 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-[1px] bg-text-primary"
                      style={{ left: `${progress * 100}%` }}
                      aria-hidden
                    />
                  </div>
                </div>
                <div
                  className="mt-1 flex w-full items-baseline justify-between font-body text-[13px] tabular-nums text-text-secondary"
                  aria-live="polite"
                  aria-atomic="true"
                >
                  <span className="text-left">{formattedTime}</span>
                  <span className="text-right">{remainingLabel}</span>
                </div>
              </div>

              <div className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2">
                <div className="flex min-w-0 justify-start">
                  <button
                    type="button"
                    onClick={cycleSpeed}
                    className="inline-flex min-h-10 min-w-[3.25rem] items-center justify-center rounded-full border border-rule bg-bg-surface px-4 py-2.5 font-ui text-[13px] font-semibold text-text-primary transition-colors active:bg-bg-surface-2"
                    aria-label={`Playback speed ${speedLabel}`}
                  >
                    {speedLabel}
                  </button>
                </div>

                <div className="flex shrink-0 items-center justify-center gap-2 sm:gap-5">
                  <button
                    type="button"
                    onClick={skipBack}
                    className="flex h-12 w-12 min-h-[48px] min-w-[48px] shrink-0 touch-manipulation items-center justify-center text-text-primary transition-opacity active:opacity-55 sm:h-14 sm:w-14 sm:min-h-[56px] sm:min-w-[56px]"
                    aria-label={`Skip back ${skipDeltaSec} seconds`}
                  >
                    <span className="relative flex h-11 w-11 items-center justify-center">
                      <RotateCcw className="absolute h-8 w-8" strokeWidth={1.35} aria-hidden />
                      <span className="relative z-[1] font-ui text-[10px] font-bold tabular-nums leading-none">
                        {skipDeltaSec}
                      </span>
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => togglePlayPause()}
                    className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent text-white shadow-md shadow-accent/25 transition-opacity active:opacity-85"
                    aria-label={isPlaying ? "Pause" : "Play"}
                  >
                    {isLoading ? (
                      <Loader2 className="h-6 w-6 animate-spin" aria-hidden />
                    ) : isPlaying ? (
                      <Pause
                        className="h-6 w-6"
                        fill="currentColor"
                        stroke="none"
                        strokeWidth={0}
                        aria-hidden
                      />
                    ) : (
                      <Play
                        className="ml-0.5 h-6 w-6"
                        fill="currentColor"
                        stroke="none"
                        strokeWidth={0}
                        aria-hidden
                      />
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={skipForward}
                    className="flex h-12 w-12 min-h-[48px] min-w-[48px] shrink-0 touch-manipulation items-center justify-center text-text-primary transition-opacity active:opacity-55 sm:h-14 sm:w-14 sm:min-h-[56px] sm:min-w-[56px]"
                    aria-label={`Skip forward ${skipDeltaSec} seconds`}
                  >
                    <span className="relative flex h-11 w-11 items-center justify-center">
                      <RotateCw className="absolute h-8 w-8" strokeWidth={1.35} aria-hidden />
                      <span className="relative z-[1] font-ui text-[10px] font-bold tabular-nums leading-none">
                        {skipDeltaSec}
                      </span>
                    </span>
                  </button>
                </div>

                <div className="flex min-w-0 justify-end">
                  <div
                    className="inline-flex min-h-10 items-center rounded-full border border-rule bg-bg-surface p-1 shadow-sm"
                    role="group"
                    aria-label="Audio language"
                  >
                    <button
                      type="button"
                      onClick={() => setLanguage("en")}
                      disabled={!hasEnglishAudio}
                      aria-pressed={language === "en"}
                      className={`min-h-8 min-w-[2.5rem] rounded-full px-2.5 py-1.5 font-ui text-[13px] font-semibold transition-colors sm:min-w-[3.1rem] sm:px-3 ${
                        language === "en"
                          ? "bg-accent text-white"
                          : "text-text-primary hover:bg-bg-surface-2"
                      } ${!hasEnglishAudio ? "cursor-not-allowed opacity-40 hover:bg-transparent" : ""}`}
                    >
                      EN
                    </button>
                    <button
                      type="button"
                      onClick={() => setLanguage("fr")}
                      disabled={!hasFrenchAudio}
                      aria-pressed={language === "fr"}
                      className={`min-h-8 min-w-[2.5rem] rounded-full px-2.5 py-1.5 font-ui text-[13px] font-semibold transition-colors sm:min-w-[3.1rem] sm:px-3 ${
                        language === "fr"
                          ? "bg-accent text-white"
                          : "text-text-primary hover:bg-bg-surface-2"
                      } ${!hasFrenchAudio ? "cursor-not-allowed opacity-40 hover:bg-transparent" : ""}`}
                    >
                      FR
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
