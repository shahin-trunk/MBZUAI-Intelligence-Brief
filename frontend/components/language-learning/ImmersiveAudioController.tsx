"use client";

import { memo } from "react";
import { Loader2 } from "lucide-react";

interface ImmersiveAudioControllerProps {
  overallProgress: number; // 0-1, across all sections
  isLessonComplete: boolean;
  currentScriptIndex?: number; // 1, 2, or 3
  speed?: number;
  onSpeedChange?: () => void;
  isLoading?: boolean;
}

const ImmersiveAudioController = memo(function ImmersiveAudioController({
  overallProgress,
  isLessonComplete,
  currentScriptIndex,
  speed = 1,
  onSpeedChange,
  isLoading = false,
}: ImmersiveAudioControllerProps) {
  const pct = isLessonComplete ? 100 : Math.min(overallProgress * 100, 100);

  const speedLabel = speed === 0.75 ? "0.75x" : speed === 1 ? "1x" : "1.25x";

  return (
    <div className="fixed top-0 left-0 right-0 z-50" role="banner" aria-label="Lesson progress">
      {/* Progress bar */}
      <div
        className="h-[3px] bg-rule/20"
        role="progressbar"
        aria-label={`Lesson progress: ${Math.round(pct)}%`}
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full bg-accent-primary transition-[width] duration-200 ease-linear relative"
          style={{
            width: `${pct}%`,
            ...(pct > 0 && !isLessonComplete
              ? { boxShadow: "0 0 6px 1px var(--color-accent-primary, #6366f1)" }
              : {}),
          }}
        >
          {/* Loading indicator */}
          {isLoading && (
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-white/80 animate-pulse" aria-hidden="true" />
          )}
        </div>
      </div>

      {/* Meta row */}
      <div className="flex items-center justify-between px-3 py-1">
        <span className="text-[9px] font-ui text-text-muted/60">
          {currentScriptIndex === 1 && "Explanation"}
          {currentScriptIndex === 2 && "Transition"}
          {currentScriptIndex === 3 && "Pronunciation"}
        </span>

        {/* Speed toggle */}
        {onSpeedChange && (
          <button
            onClick={onSpeedChange}
            className="text-[9px] font-ui text-text-muted/60 hover:text-text-muted transition-colors cursor-pointer"
            aria-label={`Playback speed ${speedLabel}`}
          >
            {isLoading ? (
              <Loader2 className="w-2.5 h-2.5 animate-spin inline" />
            ) : (
              speedLabel
            )}
          </button>
        )}
      </div>
    </div>
  );
});

export default ImmersiveAudioController;
