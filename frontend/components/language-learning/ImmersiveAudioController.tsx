"use client";

import { useState, useCallback } from "react";
import { Gauge } from "lucide-react";

interface ImmersiveAudioControllerProps {
  overallProgress: number; // 0-1, across all sections
  isLessonComplete: boolean;
  currentScriptIndex?: number; // 1, 2, or 3
  speed?: number;
  onSpeedChange?: () => void;
  isLoading?: boolean;
}

const SCRIPT_LABELS = ["Explanation", "Transition", "In Context"];

export default function ImmersiveAudioController({
  overallProgress,
  isLessonComplete,
  currentScriptIndex,
  speed = 1,
  onSpeedChange,
  isLoading = false,
}: ImmersiveAudioControllerProps) {
  const [showSpeed, setShowSpeed] = useState(false);
  const pct = isLessonComplete ? 100 : Math.min(overallProgress * 100, 100);

  const handleBarClick = useCallback(() => {
    if (onSpeedChange) {
      onSpeedChange();
      setShowSpeed(true);
      setTimeout(() => setShowSpeed(false), 1000);
    }
  }, [onSpeedChange]);

  const speedLabel = speed === 0.75 ? "0.75x" : speed === 1 ? "1x" : "1.25x";

  return (
    <div className="fixed top-0 left-0 right-0 z-50">
      {/* Progress bar */}
      <div
        className="h-[3px] bg-rule/20 cursor-pointer group"
        onClick={handleBarClick}
        role="button"
        tabIndex={-1}
        aria-label={`Lesson progress: ${Math.round(pct)}%. Click to change playback speed.`}
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
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-white/80 animate-pulse" />
          )}
        </div>

        {/* Hover tooltip */}
        <div className="absolute top-1 left-0 right-0 flex items-center justify-between px-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
          <span className="text-[10px] font-ui text-text-muted">
            {currentScriptIndex && SCRIPT_LABELS[currentScriptIndex - 1]}
          </span>
          {onSpeedChange && (
            <span className="text-[10px] font-ui text-text-muted flex items-center gap-1">
              <Gauge className="w-3 h-3" />
              {speedLabel}
            </span>
          )}
        </div>
      </div>

      {/* Speed change toast */}
      {showSpeed && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-full bg-bg-surface/90 backdrop-blur-sm border border-rule/20 animate-in fade-in slide-in-from-top duration-200">
          <span className="text-xs font-ui text-text-primary">
            Speed: {speedLabel}
          </span>
        </div>
      )}
    </div>
  );
}
