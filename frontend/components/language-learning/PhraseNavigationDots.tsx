"use client";

import { memo } from "react";
import { Check } from "lucide-react";
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
    <div className="flex items-center gap-3 sm:gap-4" role="navigation" aria-label="Phrase navigation">
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
            className="group relative flex flex-col items-center justify-center transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent-primary/50 focus:ring-offset-2 rounded-full"
            aria-label={`Phrase ${i + 1} of ${totalPhrases}${isCompleted ? ", completed" : ""}${isActive ? ", currently playing" : ""}`}
            aria-current={isActive ? "step" : undefined}
            aria-posinset={i + 1}
            aria-setsize={totalPhrases}
          >
            {/* Completed state: checkmark circle */}
            {isCompleted && !isActive ? (
              <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-accent-primary/15 border border-accent-primary/30 flex items-center justify-center transition-all duration-300 group-hover:bg-accent-primary/20 group-hover:scale-110">
                <Check className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-accent-primary" strokeWidth={2.5} />
              </div>
            ) : isActive ? (
              /* Active state: animated progress ring */
              <div className="relative">
                {/* Outer glow */}
                <div className="absolute inset-0 rounded-full bg-accent-primary/10 blur-md scale-125" aria-hidden="true" />

                {/* Progress ring */}
                <svg className="relative h-8 w-8 sm:h-9 sm:w-9 -rotate-90" viewBox="0 0 32 32" aria-hidden="true">
                  <circle
                    cx="16"
                    cy="16"
                    r="13"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-accent-primary/15"
                  />
                  <circle
                    cx="16"
                    cy="16"
                    r="13"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeDasharray={`${2 * Math.PI * 13}`}
                    strokeDashoffset={`${2 * Math.PI * 13 * (1 - scriptProgress)}`}
                    className="text-accent-primary transition-all duration-200"
                    strokeLinecap="round"
                  />
                </svg>
                {/* Center dot */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="h-2.5 w-2.5 sm:h-3 sm:w-3 rounded-full bg-accent-primary" />
                </div>
              </div>
            ) : (
              /* Inactive/pending state */
              <div className="h-2.5 w-2.5 sm:h-3 sm:w-3 rounded-full bg-rule/35 transition-all duration-300 group-hover:bg-rule/55 group-hover:scale-125" aria-hidden="true" />
            )}

            {/* Phrase number label (below dot) */}
            <span className={cn(
              "mt-1.5 font-ui text-[9px] sm:text-[10px] transition-colors duration-300",
              isActive && "text-accent-primary font-semibold",
              isCompleted && !isActive && "text-accent-primary/50",
              !isActive && !isCompleted && "text-text-muted/50"
            )}>
              {i + 1}
            </span>
          </button>
        );
      })}
    </div>
  );
});

export default PhraseNavigationDots;
