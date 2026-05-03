"use client";

import { Loader2, Pause, Play } from "lucide-react";
import type { AudioPlayerState, AudioPlayerActions } from "@/lib/presidential-brief/hooks/useAudioPlayer";
import { formatBriefDateShort } from "@/lib/utils";

interface BriefingPinnedPlayerProps {
  player: AudioPlayerState & AudioPlayerActions;
  briefDate: string;
  onOpenFullScreen: () => void;
}

/** Podcast-style bar pinned to the viewport bottom (card brief route). */
export default function BriefingPinnedPlayer({
  player,
  briefDate,
  onOpenFullScreen,
}: BriefingPinnedPlayerProps) {
  const {
    isPlaying,
    isLoading,
    formattedTime,
    formattedDuration,
    togglePlayPause,
    isUnavailable,
  } = player;

  const title = `Daily brief for ${formatBriefDateShort(briefDate)}`;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-rule bg-bg-primary"
      style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom))" }}
      role="region"
      aria-label="Briefing audio"
    >
      <div className="flex items-center gap-3 px-4 pb-0.5 pt-3">
        <button
          type="button"
          onClick={onOpenFullScreen}
          className="flex min-h-[44px] min-w-0 flex-1 flex-col justify-center gap-1 rounded-[2px] text-left active:opacity-80"
          aria-label="Open full audio player"
        >
          <span className="truncate font-display text-[15px] font-medium leading-snug text-text-primary">
            {title}
          </span>
          <span className="font-body text-[12px] leading-none tabular-nums text-text-muted">
            {formattedTime} / {formattedDuration}
          </span>
        </button>

        <button
          type="button"
          onClick={() => togglePlayPause()}
          disabled={isUnavailable}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-colors hover:bg-accent-hover disabled:pointer-events-none disabled:opacity-30"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isLoading ? (
            <Loader2 className="h-[18px] w-[18px] animate-spin" aria-hidden />
          ) : isPlaying ? (
            <Pause
              className="h-[18px] w-[18px]"
              fill="currentColor"
              stroke="none"
              strokeWidth={0}
              aria-hidden
            />
          ) : (
            <Play
              className="ml-px h-[18px] w-[18px]"
              fill="currentColor"
              stroke="none"
              strokeWidth={0}
              aria-hidden
            />
          )}
        </button>
      </div>
    </div>
  );
}
