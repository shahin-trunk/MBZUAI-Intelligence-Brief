"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

interface PhraseNavigationDotsProps {
  totalPhrases: number;
  currentPhraseIndex: number;
  currentScriptIndex: number; // 1, 2, or 3
  completedPhrases: Set<number>;
  scriptProgress: number; // 0-1 progress within current script
  onPhraseSelect: (index: number) => void;
}

const PhraseNavigationDots = memo(function PhraseNavigationDots({
  totalPhrases,
  currentPhraseIndex,
  currentScriptIndex,
  completedPhrases,
  scriptProgress,
  onPhraseSelect,
}: PhraseNavigationDotsProps) {
  if (totalPhrases <= 1) return null;

  return (
    <div className="flex items-center gap-2.5 sm:gap-3" role="navigation" aria-label="Phrase navigation">
      {Array.from({ length: totalPhrases }, (_, i) => {
        const isActive = i === currentPhraseIndex;
        const isCompleted = completedPhrases.has(i);

        return (
          <button
            key={i}
            type="button"
            onClick={() => onPhraseSelect(i)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onPhraseSelect(i);
              }
            }}
            className="relative flex items-center justify-center transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent-primary/50 focus:ring-offset-2 rounded-full"
            aria-label={`Phrase ${i + 1} of ${totalPhrases}${isCompleted ? ", completed" : ""}${isActive ? ", currently playing" : ""}`}
            aria-current={isActive ? "step" : undefined}
            aria-posinset={i + 1}
            aria-setsize={totalPhrases}
          >
            {/* Outer ring for active phrase */}
            {isActive && (
              <div className="absolute inset-0 rounded-full border-2 border-accent-primary/30 scale-150" aria-hidden="true" />
            )}

            {/* Completed progress ring */}
            {isActive && scriptProgress > 0 && (
              <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 24 24" aria-hidden="true">
                <circle
                  cx="12"
                  cy="12"
                  r="10"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-accent-primary/20"
                />
                <circle
                  cx="12"
                  cy="12"
                  r="10"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeDasharray={`${2 * Math.PI * 10}`}
                  strokeDashoffset={`${2 * Math.PI * 10 * (1 - scriptProgress)}`}
                  className="text-accent-primary transition-all duration-200"
                  strokeLinecap="round"
                />
              </svg>
            )}

            {/* Main dot */}
            <div
              className={cn(
                "h-2.5 w-2.5 sm:h-3 sm:w-3 rounded-full transition-all duration-300 relative z-10",
                isActive && "bg-accent-primary",
                isCompleted && !isActive && "bg-accent-primary/50",
                !isActive && !isCompleted && "bg-rule/40 hover:bg-rule/60"
              )}
              aria-hidden="true"
            />

            {/* Script indicator pill (shown below active dot) */}
            {isActive && (
              <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 flex gap-0.5" aria-hidden="true">
                {[1, 2, 3].map((s) => (
                  <div
                    key={s}
                    className={cn(
                      "w-1 h-1 rounded-full transition-colors duration-200",
                      s < currentScriptIndex ? "bg-accent-primary" :
                      s === currentScriptIndex ? "bg-accent-primary" :
                      "bg-rule/30"
                    )}
                  />
                ))}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
});

export default PhraseNavigationDots;
