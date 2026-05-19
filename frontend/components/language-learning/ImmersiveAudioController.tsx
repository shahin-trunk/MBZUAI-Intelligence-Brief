"use client";

import { memo } from "react";
import { Loader2 } from "lucide-react";

interface ImmersiveAudioControllerProps {
  overallProgress: number;
  isLessonComplete: boolean;
  isLoading?: boolean;
}

const ImmersiveAudioController = memo(function ImmersiveAudioController({
  overallProgress,
  isLessonComplete,
  isLoading = false,
}: ImmersiveAudioControllerProps) {
  const pct = isLessonComplete ? 100 : Math.min(overallProgress * 100, 100);

  return (
    <div className="fixed top-0 left-0 right-0 z-50" role="banner" aria-label="Lesson progress">
      <div
        className="h-[2px] bg-rule/50"
        role="progressbar"
        aria-label={`Lesson progress: ${Math.round(pct)}%`}
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full bg-accent-primary transition-[width] duration-500 ease-out relative"
          style={{ width: `${pct}%` }}
        >
          {isLoading && (
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-accent-foreground/70 animate-pulse" aria-hidden="true" />
          )}
        </div>
      </div>
    </div>
  );
});

export default ImmersiveAudioController;
