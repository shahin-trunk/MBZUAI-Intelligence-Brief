"use client";

import { Telescope, BookOpen } from "lucide-react";
import { BRIEF_STORY_CARD_MAX_WIDTH_CLASS } from "@/lib/presidential-brief/briefCardLayout";

const railBtn =
  "border border-rule bg-bg-surface-2 text-text-primary transition-[transform,opacity,background-color] duration-200 ease-out hover:bg-bg-primary disabled:pointer-events-none disabled:opacity-35 dark:border-rule dark:bg-bg-surface-2 dark:hover:bg-bg-surface";

const centerPill =
  "flex h-12 min-h-[48px] shrink-0 items-center justify-center gap-2 rounded-full px-5 font-ui text-[14px] font-medium tracking-tight sm:h-[52px] sm:min-h-[52px] sm:px-6 sm:text-[15px]";

interface CardSwipeActionRailProps {
  canAct: boolean;
  onRequestResearch: () => void;
  onOpenLearn?: () => void;
  /** Inside story card footer (not deck overlay). */
  embedded?: boolean;
}

/**
 * Two action buttons: open language learning page, then research request.
 */
export default function CardSwipeActionRail({
  canAct,
  onRequestResearch,
  onOpenLearn,
  embedded = true,
}: CardSwipeActionRailProps) {
  const outer = embedded
    ? "relative z-[2] flex w-full justify-center px-1 pt-1"
    : "pointer-events-none absolute inset-x-0 bottom-0 z-[55] flex translate-y-[40%] justify-center px-2 sm:translate-y-[42%]";

  return (
    <div className={outer} aria-hidden={!canAct}>
      <div
        className={`pointer-events-auto flex w-full items-end justify-center gap-3 ${BRIEF_STORY_CARD_MAX_WIDTH_CLASS}`}
      >
        {onOpenLearn && (
          <button
            type="button"
            disabled={!canAct}
            onClick={(e) => {
              e.stopPropagation();
              onOpenLearn();
            }}
            className={`${centerPill} min-w-[6.5rem] sm:min-w-[7.5rem] ${railBtn}`}
            aria-label="Learn languages"
          >
            <BookOpen
              className="h-5 w-5 shrink-0 sm:h-[22px] sm:w-[22px]"
              strokeWidth={1.75}
              aria-hidden
            />
            <span className="hidden sm:inline">Learn</span>
          </button>
        )}
        <button
          type="button"
          disabled={!canAct}
          onClick={(e) => {
            e.stopPropagation();
            onRequestResearch();
          }}
          className={`${centerPill} min-w-[6.5rem] sm:min-w-[8.5rem] ${railBtn}`}
          aria-label="Request research"
        >
          <Telescope
            className="h-5 w-5 shrink-0 sm:h-[22px] sm:w-[22px]"
            strokeWidth={1.75}
            aria-hidden
          />
          <span className="hidden sm:inline">Request research</span>
        </button>
      </div>
    </div>
  );
}
