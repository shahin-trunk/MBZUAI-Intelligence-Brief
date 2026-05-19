"use client";

import {
  ChevronUp,
  FastForward,
  Loader2,
  Pause,
  Play,
  Rewind,
} from "lucide-react";
import type { AudioPlayerState, AudioPlayerActions } from "@/lib/presidential-brief/hooks/useAudioPlayer";

interface AudioMiniPlayerProps {
  player: AudioPlayerState & AudioPlayerActions;
  onExpand: () => void;
}

export default function AudioMiniPlayer({ player, onExpand }: AudioMiniPlayerProps) {
  const {
    isPlaying,
    isLoading,
    progress,
    formattedTime,
    formattedDuration,
    language,
    currentTime,
    duration,
    togglePlayPause,
    seek,
  } = player;

  const skipBack = () => seek(Math.max(0, currentTime - 5));
  const skipForward = () => {
    if (duration) seek(Math.min(duration, currentTime + 5));
  };

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-rule bg-bg-primary shadow-[0_-2px_10px_rgba(0,0,0,0.04)]"
      style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom))" }}
    >
      <div className="h-[2px] w-full bg-rule">
        <div
          className="h-full bg-accent transition-none"
          style={{ width: `${progress * 100}%` }}
        />
      </div>

      <div className="flex h-16 items-center gap-1 px-3">
        <button
          onClick={(e) => {
            e.stopPropagation();
            skipBack();
          }}
          className="flex min-h-[44px] min-w-[36px] flex-shrink-0 items-center justify-center text-text-muted active:text-accent"
          aria-label="Skip back 5 seconds"
        >
          <Rewind className="h-5 w-5" strokeWidth={1.5} aria-hidden />
        </button>

        <button
          onClick={(e) => {
            e.stopPropagation();
            togglePlayPause();
          }}
          className="flex min-h-[44px] min-w-[44px] flex-shrink-0 items-center justify-center transition-opacity active:opacity-70"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-white">
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : isPlaying ? (
              <Pause className="h-4 w-4" strokeWidth={2.5} aria-hidden />
            ) : (
              <Play className="h-4 w-4 translate-x-px" strokeWidth={2.5} aria-hidden />
            )}
          </span>
        </button>

        <button
          onClick={(e) => {
            e.stopPropagation();
            skipForward();
          }}
          className="flex min-h-[44px] min-w-[36px] flex-shrink-0 items-center justify-center text-text-muted active:text-accent"
          aria-label="Skip forward 5 seconds"
        >
          <FastForward className="h-5 w-5" strokeWidth={1.5} aria-hidden />
        </button>

        <button
          onClick={onExpand}
          className="flex min-h-[44px] min-w-0 flex-1 flex-col items-start justify-center pl-2 text-left"
          aria-label="Open full audio player"
        >
          <span className="font-ui text-[13px] font-semibold leading-tight text-text-primary">
            Today&apos;s Brief
          </span>
          <span className="font-mono text-[11px] leading-tight text-text-muted">
            {formattedTime} / {formattedDuration} ·{" "}
            {language === "ar" ? "AR" : language === "fr" ? "FR" : "EN"}
          </span>
        </button>

        <button
          onClick={onExpand}
          className="flex min-h-[44px] min-w-[44px] flex-shrink-0 items-center justify-center text-text-muted"
          aria-label="Expand player"
        >
          <ChevronUp className="h-5 w-5" strokeWidth={2} aria-hidden />
        </button>
      </div>
    </div>
  );
}
