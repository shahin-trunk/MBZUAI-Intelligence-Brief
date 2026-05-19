"use client";

import { memo, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";

interface PhraseNavigationDotsProps {
  totalPhrases: number;
  currentPhraseIndex: number;
  completedPhrases: Set<number>;
  scriptProgress: number;
  onPhraseSelect: (index: number) => void;
}

const DEBOUNCE_MS = 300;

const PhraseNavigationDots = memo(function PhraseNavigationDots({
  totalPhrases,
  currentPhraseIndex,
  completedPhrases,
  scriptProgress,
  onPhraseSelect,
}: PhraseNavigationDotsProps) {
  const lastClickRef = useRef(0);

  const handlePhraseSelect = useCallback((index: number) => {
    const now = Date.now();
    if (now - lastClickRef.current < DEBOUNCE_MS) return;
    lastClickRef.current = now;
    onPhraseSelect(index);
  }, [onPhraseSelect]);

  if (totalPhrases <= 1) return null;

  return (
    <div className="flex items-center justify-center gap-2 sm:gap-3" role="navigation" aria-label="Phrase navigation">
      {Array.from({ length: totalPhrases }, (_, i) => {
        const isActive = i === currentPhraseIndex;
        const isCompleted = completedPhrases.has(i);

        return (
          <button
            key={i}
            type="button"
            onClick={() => handlePhraseSelect(i)}
            className={cn(
              "relative transition-all duration-300 focus:outline-none p-2 sm:p-2.5",
              isActive && "scale-110"
            )}
            aria-label={`Phrase ${i + 1}${isCompleted ? ", completed" : ""}${isActive ? ", playing" : ""}`}
            aria-current={isActive ? "step" : undefined}
          >
            {isActive ? (
              /* Active: progress ring */
              <div className="relative h-9 w-9 sm:h-7 sm:w-7">
                <svg className="h-full w-full -rotate-90" viewBox="0 0 28 28">
                  <circle cx="14" cy="14" r="11" fill="none" stroke="currentColor" strokeWidth="2" className="text-accent/15" />
                  <circle
                    cx="14" cy="14" r="11"
                    fill="none" stroke="currentColor" strokeWidth="2.5"
                    strokeDasharray={`${2 * Math.PI * 11}`}
                    strokeDashoffset={`${2 * Math.PI * 11 * (1 - scriptProgress)}`}
                    className="text-accent-primary transition-all duration-300"
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="h-2 w-2 rounded-full bg-accent-primary" />
                </div>
              </div>
            ) : (
              <div
                className={cn(
                  "h-2 w-2 rounded-full transition-all duration-300",
                  isCompleted
                    ? "bg-accent-primary/60"
                    : "bg-rule hover:bg-text-muted/50"
                )}
              />
            )}
          </button>
        );
      })}
    </div>
  );
});

export default PhraseNavigationDots;
