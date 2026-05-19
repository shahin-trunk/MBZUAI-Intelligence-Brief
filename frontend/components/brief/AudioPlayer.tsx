"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  Play,
  Pause,
  Volume2,
  ChevronDown,
  ChevronUp,
  FileText,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { LanguageSelector, type AudioLanguage } from "@/components/common/LanguageSelector";

/* ─── Types ──────────────────────────────────────────────────────────── */

interface AudioPlayerProps {
  audioUrl: string;
  audioScript?: string;
  audioUrlFr?: string;
  audioScriptFr?: string;
  audioUrlAr?: string;
  audioScriptAr?: string;
}

/* ─── Constants ──────────────────────────────────────────────────────── */

const SPEED_OPTIONS = [1, 1.25, 1.5, 2] as const;

/* ─── Helpers ────────────────────────────────────────────────────────── */

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function clampTime(currentTime: number, duration: number): number {
  if (!isFinite(currentTime) || currentTime < 0) return 0;
  if (!isFinite(duration) || duration <= 0) return currentTime;
  return Math.min(currentTime, duration);
}

async function probeDecodedDuration(audioUrl: string): Promise<number | null> {
  if (typeof window === "undefined" || typeof window.AudioContext === "undefined") {
    return null;
  }

  const response = await fetch(audioUrl, { cache: "force-cache" });
  if (!response.ok) {
    return null;
  }

  const arrayBuffer = await response.arrayBuffer();
  const audioContext = new window.AudioContext();

  try {
    const decoded = await audioContext.decodeAudioData(arrayBuffer.slice(0));
    return isFinite(decoded.duration) && decoded.duration > 0
      ? decoded.duration
      : null;
  } finally {
    await audioContext.close();
  }
}

/** Strip SSML tags (e.g. <break time="0.8s" />) from transcript text. */
function stripSsmlTags(text: string): string {
  return text
    .replace(/<break\s+time="[^"]*"\s*\/>/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/* ─── Component ──────────────────────────────────────────────────────── */

export default function AudioPlayer({
  audioUrl,
  audioScript,
  audioUrlFr,
  audioScriptFr,
  audioUrlAr,
  audioScriptAr,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);

  const [lang, setLang] = useState<AudioLanguage>("en");
  const hasFrench = !!audioUrlFr;
  const hasArabic = !!audioUrlAr;
  const activeUrl =
    lang === "ar" ? (audioUrlAr ?? audioUrl) :
    lang === "fr" ? (audioUrlFr ?? audioUrl) :
    audioUrl;
  const activeScript =
    lang === "ar" ? (audioScriptAr ?? audioScript) :
    lang === "fr" ? (audioScriptFr ?? audioScript) :
    audioScript;

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speedIndex, setSpeedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [decodedDuration, setDecodedDuration] = useState<number | null>(null);

  /* ── Audio event listeners ──────────────────────────────────────────── */

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => {
      setCurrentTime(clampTime(audio.currentTime, audio.duration));
    };
    const onLoadedMetadata = () => {
      const nextDuration = isFinite(audio.duration) ? audio.duration : 0;
      setDuration(nextDuration);
      setCurrentTime((prev) => clampTime(audio.currentTime || prev, nextDuration));
      setIsLoading(false);
    };
    const onDurationChange = () => {
      const nextDuration = isFinite(audio.duration) ? audio.duration : 0;
      setDuration(nextDuration);
      setCurrentTime((prev) => clampTime(prev, nextDuration));
    };
    const onEnded = () => {
      setCurrentTime(clampTime(audio.duration, audio.duration));
      setIsPlaying(false);
    };
    const onError = () => {
      setHasError(true);
      setIsPlaying(false);
      setIsLoading(false);
    };
    const onWaiting = () => setIsLoading(true);
    const onCanPlay = () => setIsLoading(false);

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("durationchange", onDurationChange);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);
    audio.addEventListener("waiting", onWaiting);
    audio.addEventListener("canplay", onCanPlay);

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("durationchange", onDurationChange);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
      audio.removeEventListener("waiting", onWaiting);
      audio.removeEventListener("canplay", onCanPlay);
    };
  }, []);

  /* ── Reset state when the audio source changes ─────────────────────── */

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    audio.pause();
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setDecodedDuration(null);
    setIsLoading(false);
    setHasError(false);

    try {
      audio.currentTime = 0;
    } catch {
      // Ignore browsers that disallow resetting currentTime before metadata.
    }

    audio.load();
  }, [activeUrl]);

  useEffect(() => {
    let cancelled = false;

    probeDecodedDuration(activeUrl)
      .then((nextDuration) => {
        if (!cancelled) {
          setDecodedDuration(nextDuration);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDecodedDuration(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeUrl]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.playbackRate = SPEED_OPTIONS[speedIndex];
  }, [speedIndex]);

  /* ── Controls ───────────────────────────────────────────────────────── */

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || hasError) return;

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      setIsLoading(true);
      audio.play().then(() => {
        setIsPlaying(true);
        setIsLoading(false);
      }).catch(() => {
        setIsLoading(false);
      });
    }
  }, [isPlaying, hasError]);

  const cycleSpeed = useCallback(() => {
    const nextIndex = (speedIndex + 1) % SPEED_OPTIONS.length;
    setSpeedIndex(nextIndex);
    if (audioRef.current) {
      audioRef.current.playbackRate = SPEED_OPTIONS[nextIndex];
    }
  }, [speedIndex]);

  /* ── Derived values ─────────────────────────────────────────────────── */

  const effectiveDuration =
    decodedDuration !== null &&
    (duration <= 0 || Math.abs(decodedDuration - duration) > 1)
      ? decodedDuration
      : duration;
  const displayCurrentTime = clampTime(currentTime, effectiveDuration);
  const progress =
    effectiveDuration > 0
      ? Math.min(100, (displayCurrentTime / effectiveDuration) * 100)
      : 0;

  const seekTo = useCallback(
    (nextTime: number) => {
      const audio = audioRef.current;
      if (!audio || !isFinite(nextTime)) return;
      audio.currentTime = clampTime(nextTime, effectiveDuration);
      setCurrentTime(clampTime(nextTime, effectiveDuration));
    },
    [effectiveDuration]
  );

  /* ── Error state ────────────────────────────────────────────────────── */

  if (hasError) {
    return (
      <div className="mt-6 mb-2 rounded-md border border-border-primary bg-bg-tertiary px-4 py-3">
        <p className="font-mono text-[13px] text-text-muted">
          Audio unavailable
        </p>
      </div>
    );
  }

  /* ── Render ─────────────────────────────────────────────────────────── */

  return (
    <div className="mt-6 mb-2">
      {/* Hidden native audio element */}
      <audio ref={audioRef} src={activeUrl} preload="metadata" />

      {/* Player chrome */}
      <div className="rounded-md border border-border-primary bg-bg-tertiary px-4 py-3 space-y-3">
        {/* Controls row */}
        <div className="flex flex-wrap items-center gap-3 sm:flex-nowrap">
          {/* Play/Pause button */}
          <button
            onClick={togglePlay}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent-primary text-white transition-colors hover:bg-accent-primary/90"
            aria-label={isPlaying ? "Pause" : "Play"}
          >
            {isLoading ? (
              <div className="h-3.5 w-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            ) : isPlaying ? (
              <Pause className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5 ml-0.5" />
            )}
          </button>

          {/* Time display */}
          <span className="shrink-0 font-mono text-[13px] tabular-nums text-text-muted">
            {formatTime(displayCurrentTime)}
            <span className="text-text-muted/50"> / </span>
            {formatTime(effectiveDuration)}
          </span>

          {/* Speed control */}
          <button
            onClick={cycleSpeed}
            className="min-h-9 min-w-[2.5rem] shrink-0 rounded px-1.5 py-0.5 text-center font-mono text-[13px] text-text-secondary transition-colors hover:bg-bg-secondary hover:text-text-primary"
            aria-label={`Playback speed: ${SPEED_OPTIONS[speedIndex]}x`}
          >
            {SPEED_OPTIONS[speedIndex]}x
          </button>

          {/* Language selector with flags */}
          {hasArabic || hasFrench ? (
            <LanguageSelector
              language={lang}
              onLanguageChange={setLang}
              availability={{ en: true, fr: hasFrench, ar: hasArabic }}
              size="sm"
            />
          ) : null}

          {/* Volume icon */}
          <Volume2 className="h-3.5 w-3.5 text-text-muted shrink-0 hidden sm:block" />
        </div>

        {/* Progress bar */}
        <div
          className="h-1.5 w-full rounded-full bg-border-accent"
          style={{
            backgroundImage: `linear-gradient(to right, var(--accent-primary) 0%, var(--accent-primary) ${progress}%, var(--border-accent) ${progress}%, var(--border-accent) 100%)`,
          }}
        >
          <input
            type="range"
            min={0}
            max={effectiveDuration > 0 ? effectiveDuration : 0}
            step={0.1}
            value={displayCurrentTime}
            onChange={(e) => seekTo(Number(e.target.value))}
            className="h-1.5 w-full cursor-pointer appearance-none bg-transparent"
            aria-label="Audio progress"
            aria-valuemin={0}
            aria-valuemax={Math.round(effectiveDuration)}
            aria-valuenow={Math.round(displayCurrentTime)}
            aria-valuetext={`${formatTime(displayCurrentTime)} of ${formatTime(effectiveDuration)}`}
            disabled={effectiveDuration <= 0}
          />
        </div>
      </div>

      {/* Transcript toggle */}
      {activeScript && (
        <Collapsible open={transcriptOpen} onOpenChange={setTranscriptOpen}>
          <CollapsibleTrigger className="mt-2 flex min-h-9 items-center gap-1.5 font-mono text-[13px] text-text-muted transition-colors cursor-pointer hover:text-text-secondary">
            <FileText className="h-3 w-3" />
            {transcriptOpen ? "Hide Transcript" : "View Transcript"}
            {transcriptOpen ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-3 rounded-md border border-border-primary bg-bg-secondary p-4 max-h-96 overflow-y-auto">
              <div className="font-sans text-sm text-text-secondary leading-relaxed whitespace-pre-line">
                {stripSsmlTags(activeScript)}
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}
