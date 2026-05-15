"use client";

import { useRef, useEffect, useCallback } from "react";
import type { LearningSection } from "@/lib/types/brief";
import { cn } from "@/lib/utils";

interface LearningSectionNavProps {
  sections: LearningSection[];
  currentIndex: number;
  completedIndices: Set<number>;
  onSelect: (index: number) => void;
  language: "fr" | "ar";
}

export default function LearningSectionNav({
  sections,
  currentIndex,
  completedIndices,
  onSelect,
  language,
}: LearningSectionNavProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);

  // Scroll active pill into view
  useEffect(() => {
    if (activeRef.current && scrollRef.current) {
      const container = scrollRef.current;
      const pill = activeRef.current;
      const left = pill.offsetLeft - container.offsetWidth / 2 + pill.offsetWidth / 2;
      container.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
    }
  }, [currentIndex]);

  const handleSelect = useCallback(
    (idx: number) => {
      onSelect(idx);
    },
    [onSelect],
  );

  return (
    <div
      ref={scrollRef}
      className="flex gap-2 overflow-x-auto px-4 pb-1 pt-0.5 scrollbar-none sm:px-6 lg:justify-center lg:px-0"
      dir={language === "ar" ? "rtl" : "ltr"}
    >
      {sections.map((section, idx) => {
        const isActive = idx === currentIndex;
        const isCompleted = completedIndices.has(idx);
        return (
          <button
            key={section.id}
            ref={isActive ? activeRef : undefined}
            type="button"
            onClick={() => handleSelect(idx)}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-1.5 font-ui text-[13px] leading-tight transition-colors",
              isActive
                ? "border-accent-primary/40 bg-accent-primary/10 text-accent-primary"
                : isCompleted
                  ? "border-rule/60 bg-bg-surface text-text-secondary"
                  : "border-rule bg-bg-surface text-text-muted hover:text-text-secondary",
            )}
          >
            {isCompleted && !isActive && (
              <svg className="h-3 w-3 shrink-0 text-accent-primary/60" viewBox="0 0 12 12" fill="none">
                <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
            <span className="whitespace-nowrap">{section.title}</span>
          </button>
        );
      })}
    </div>
  );
}
