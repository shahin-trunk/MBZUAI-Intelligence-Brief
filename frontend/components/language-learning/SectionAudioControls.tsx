"use client";

import { Play, Pause, SkipForward, SkipBack } from "lucide-react";
import { formatTime } from "@/lib/utils";

interface SectionAudioControlsProps {
  isPlaying: boolean;
  isLoading: boolean;
  currentTime: number;
  duration: number;
  speed: number;
  currentSectionIndex: number;
  totalSections: number;
  onTogglePlayPause: () => void;
  onSeek: (time: number) => void;
  onCycleSpeed: () => void;
  onNextSection: () => void;
  onPrevSection: () => void;
}

export default function SectionAudioControls({
  isPlaying,
  isLoading,
  currentTime,
  duration,
  speed,
  currentSectionIndex,
  totalSections,
  onTogglePlayPause,
  onSeek,
  onCycleSpeed,
  onNextSection,
  onPrevSection,
}: SectionAudioControlsProps) {
  const progress = duration > 0 ? currentTime / duration : 0;
  const isFirst = currentSectionIndex === 0;
  const isLast = currentSectionIndex >= totalSections - 1;

  return (
    <div className="rounded-xl border border-rule bg-bg-surface px-4 py-3 sm:px-5">
      {/* Progress bar */}
      <div
        className="group relative mb-3 h-1.5 cursor-pointer rounded-full bg-bg-tertiary"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const pct = Math.max(0, Math.min(1, x / rect.width));
          onSeek(pct * duration);
        }}
        role="slider"
        aria-label="Section audio progress"
        aria-valuenow={Math.round(currentTime)}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        tabIndex={0}
      >
        <div
          className="h-full rounded-full bg-accent-primary transition-[width] duration-100 ease-linear"
          style={{ width: `${progress * 100}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-3 w-3 rounded-full bg-accent-primary opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
          style={{ left: `calc(${progress * 100}% - 6px)` }}
        />
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Prev section */}
        <button
          type="button"
          onClick={onPrevSection}
          disabled={isFirst && currentTime < 3}
          className="flex h-8 w-8 items-center justify-center rounded-full text-text-primary transition-colors hover:bg-bg-surface-2 disabled:opacity-30"
          aria-label="Previous section"
        >
          <SkipBack className="h-4 w-4" strokeWidth={1.75} />
        </button>

        {/* Play/Pause */}
        <button
          type="button"
          onClick={onTogglePlayPause}
          disabled={isLoading}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-primary text-white transition-transform hover:scale-105 disabled:opacity-50"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isLoading ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
          ) : isPlaying ? (
            <Pause className="h-5 w-5" strokeWidth={2} />
          ) : (
            <Play className="ml-0.5 h-5 w-5" strokeWidth={2} />
          )}
        </button>

        {/* Next section */}
        <button
          type="button"
          onClick={onNextSection}
          disabled={isLast}
          className="flex h-8 w-8 items-center justify-center rounded-full text-text-primary transition-colors hover:bg-bg-surface-2 disabled:opacity-30"
          aria-label="Next section"
        >
          <SkipForward className="h-4 w-4" strokeWidth={1.75} />
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Speed control */}
        <button
          type="button"
          onClick={onCycleSpeed}
          className="flex h-7 items-center rounded-full border border-rule bg-bg-surface px-2.5 font-ui text-[12px] font-medium text-text-primary transition-colors hover:bg-bg-surface-2"
          aria-label={`Speed: ${speed}x`}
        >
          {speed}x
        </button>

        {/* Time display */}
        <span className="font-mono text-[11px] text-text-muted tabular-nums">
          {formatTime(currentTime)}{" / "}{duration > 0 ? formatTime(duration) : "--:--"}
        </span>
      </div>
    </div>
  );
}
