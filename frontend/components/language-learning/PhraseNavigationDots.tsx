"use client";

import { cn } from "@/lib/utils";

interface PhraseNavigationDotsProps {
  totalPhrases: number;
  currentPhraseIndex: number;
  completedPhrases: Set<number>;
  onPhraseSelect: (index: number) => void;
}

export default function PhraseNavigationDots({
  totalPhrases,
  currentPhraseIndex,
  completedPhrases,
  onPhraseSelect,
}: PhraseNavigationDotsProps) {
  if (totalPhrases <= 1) return null;

  return (
    <div className="flex items-center gap-2" role="navigation" aria-label="Phrase navigation">
      {Array.from({ length: totalPhrases }, (_, i) => {
        const isActive = i === currentPhraseIndex;
        const isCompleted = completedPhrases.has(i);

        return (
          <button
            key={i}
            type="button"
            onClick={() => onPhraseSelect(i)}
            className={cn(
              "h-2.5 w-2.5 rounded-full transition-all duration-300",
              isActive && "bg-accent-primary scale-125",
              isCompleted && !isActive && "bg-accent-primary/50",
              !isActive && !isCompleted && "bg-rule/40 hover:bg-rule/60"
            )}
            aria-label={`Phrase ${i + 1}`}
            aria-current={isActive ? "step" : undefined}
          />
        );
      })}
    </div>
  );
}
