"use client";

import { ChevronDown, GalleryVertical, List } from "lucide-react";
import { cn, formatBriefDateShort } from "@/lib/utils";

export type BriefChromeViewMode = "cards" | "list";

export interface CardTopChromeProps {
  briefDate: string;
  /** Current position among story cards in the unified feed (0-based). */
  storyProgressIndex: number;
  storyProgressTotal: number;
  /** When false, hide the story progress fill (e.g. list view). */
  showReadingProgress?: boolean;
  /** Open calendar when the date row is tapped. */
  onDateOpenCalendar: () => void;
  calendarOpen: boolean;
  viewMode: BriefChromeViewMode;
  onViewModeChange: (mode: BriefChromeViewMode) => void;
}

/** Brief chrome: hairline progress → date + menu chevron (opens calendar). */
export function CardTopChrome({
  briefDate,
  storyProgressIndex,
  storyProgressTotal,
  showReadingProgress = true,
  onDateOpenCalendar,
  calendarOpen,
  viewMode,
  onViewModeChange,
}: CardTopChromeProps) {
  const dateLabel = formatBriefDateShort(briefDate);

  const safeTotal = Math.max(storyProgressTotal, 1);
  const progressIdx =
    storyProgressTotal > 0
      ? Math.min(Math.max(storyProgressIndex, 0), safeTotal - 1)
      : 0;
  const fillPercent =
    storyProgressTotal > 0 ? ((progressIdx + 1) / safeTotal) * 100 : 0;

  /** Track + thumb: same pill/stadium geometry; ~36px-tall segments inside 44px-tall capsule */
  const viewTabIcon = "size-4 shrink-0";

  return (
    <header
      className="shrink-0 bg-bg-primary"
      style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
    >
      {/* 1. Reading progress — cards mode only (hidden in list view) */}
      {showReadingProgress ? (
        <div className="px-0 pb-1 pt-0">
          {storyProgressTotal > 0 ? (
            <div
              className="relative h-0.5 w-full overflow-hidden bg-text-muted/15"
              role="progressbar"
              aria-valuenow={progressIdx + 1}
              aria-valuemin={1}
              aria-valuemax={storyProgressTotal}
              aria-label="Story progress"
            >
              <div
                className="h-full bg-accent transition-[width] duration-200 ease-out"
                style={{ width: `${fillPercent}%` }}
              />
            </div>
          ) : (
            <div className="h-0.5 w-full bg-text-muted/10" aria-hidden="true" />
          )}
        </div>
      ) : null}

      {/* 2. Date row + view tabs */}
      <div className="flex items-center justify-between gap-2 px-4 py-1 sm:py-2">
        <button
          type="button"
          onClick={onDateOpenCalendar}
          className="flex min-h-[40px] min-w-0 flex-1 items-center gap-1 rounded-[2px] py-1 pl-0 pr-1.5 text-left font-display text-[17px] font-normal tracking-[-0.01em] text-text-primary transition-opacity hover:opacity-80 sm:text-[18px]"
          aria-label="Choose brief date"
          aria-haspopup="dialog"
          aria-expanded={calendarOpen}
        >
          <time
            className="min-w-0 truncate leading-snug"
            dateTime={briefDate}
            title={dateLabel}
          >
            {dateLabel}
          </time>
          <ChevronDown
            className={cn(
              "size-[1.125em] shrink-0 translate-y-[0.04em] text-text-primary transition-transform duration-200",
              calendarOpen && "rotate-180"
            )}
            strokeWidth={2}
            aria-hidden
          />
        </button>

        <div
          className="relative isolate inline-flex h-11 shrink-0 items-center gap-1 rounded-full border border-rule-light bg-bg-surface px-1"
          role="tablist"
          aria-label="Brief view"
        >
          <div
            className={cn(
              "pointer-events-none absolute bottom-1 left-1 top-1 z-0 w-10 rounded-full bg-bg-primary shadow-sm ring-1 ring-rule-light/70",
              "transition-transform duration-[280ms] ease-[cubic-bezier(0.32,0.72,0,1)] motion-reduce:transition-none"
            )}
            style={{
              transform:
                viewMode === "list"
                  ? "translateX(calc(100% + 0.25rem))"
                  : "translateX(0)",
            }}
            aria-hidden
          />
          <button
            type="button"
            role="tab"
            aria-label="Card view"
            aria-selected={viewMode === "cards"}
            tabIndex={viewMode === "cards" ? 0 : -1}
            className={cn(
              "relative z-10 flex h-9 w-10 shrink-0 flex-col items-center justify-center rounded-full transition-colors duration-200 motion-reduce:transition-none",
              viewMode === "cards"
                ? "text-text-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
            onClick={() => onViewModeChange("cards")}
          >
            <GalleryVertical
              className={viewTabIcon}
              strokeWidth={viewMode === "cards" ? 2.25 : 2}
              aria-hidden
            />
          </button>
          <button
            type="button"
            role="tab"
            aria-label="List view"
            aria-selected={viewMode === "list"}
            tabIndex={viewMode === "list" ? 0 : -1}
            className={cn(
              "relative z-10 flex h-9 w-10 shrink-0 flex-col items-center justify-center rounded-full transition-colors duration-200 motion-reduce:transition-none",
              viewMode === "list"
                ? "text-text-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
            onClick={() => onViewModeChange("list")}
          >
            <List
              className={viewTabIcon}
              strokeWidth={viewMode === "list" ? 2.25 : 2}
              aria-hidden
            />
          </button>
        </div>
      </div>
    </header>
  );
}
