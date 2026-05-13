"use client";

import { Play, Pause, RotateCcw, RotateCw } from "lucide-react";
import { formatTime } from "@/lib/utils";

interface LearningAudioPlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  speed: number;
  cycleSpeed: () => void;
  togglePlayPause: () => void;
  seek: (time: number) => void;
  stepBack: () => void;
  stepForward: () => void;
  isLoading: boolean;
}

interface LearningAudioPlayerProps {
  player: LearningAudioPlayerState;
}

const buttClasses =
  "flex h-8 w-8 items-center justify-center rounded-full border border-rule bg-bg-surface text-text-primary transition-colors hover:bg-bg-surface-2";

const LEARNING_SPEEDS = [0.5, 0.75, 1];

export default function LearningAudioPlayer({
  player,
}: LearningAudioPlayerProps) {
  const { isPlaying, currentTime, duration, speed, cycleSpeed, togglePlayPause, seek, stepBack, stepForward, isLoading } = player;

  const progress = duration > 0 ? currentTime / duration : 0;

  return (
    <div className="rounded-xl border border-rule bg-bg-surface px-4 py-3 sm:px-5">
      {/* Progress bar */}
      <div
        className="group relative mb-3 h-1.5 cursor-pointer rounded-full bg-bg-tertiary"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const pct = Math.max(0, Math.min(1, x / rect.width));
          seek(pct * duration);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
          }
        }}
        role="slider"
        aria-label="Audio progress"
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

      {/* Controls */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Step back 5s */}
        <button
          type="button"
          onClick={stepBack}
          className={buttClasses}
          aria-label="Rewind 5 seconds"
        >
          <RotateCcw className="h-4 w-4" strokeWidth={1.75} />
        </button>

        {/* Play/Pause */}
        <button
          type="button"
          onClick={togglePlayPause}
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

        {/* Step forward 5s */}
        <button
          type="button"
          onClick={stepForward}
          className={buttClasses}
          aria-label="Forward 5 seconds"
        >
          <RotateCw className="h-4 w-4" strokeWidth={1.75} />
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Speed control */}
        <button
          type="button"
          onClick={cycleSpeed}
          className="flex h-8 items-center rounded-full border border-rule bg-bg-surface px-3 font-ui text-[13px] font-medium text-text-primary transition-colors hover:bg-bg-surface-2"
          aria-label={`Speed: ${speed}x`}
        >
          {speed}x
        </button>

        {/* Time display */}
        <span className="font-mono text-[12px] text-text-muted tabular-nums">
          {formatTime(currentTime)} / {duration > 0 ? formatTime(duration) : "--:--"}
        </span>
      </div>
    </div>
  );
}
