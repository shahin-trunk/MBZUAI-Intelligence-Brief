"use client";

import {
  useMemo,
  useRef,
  useCallback,
  useLayoutEffect,
  useEffect,
} from "react";
import type { FeedCard } from "@/lib/types/brief";
import {
  cn,
  formatBriefDateShort,
  formatSectionTagLabel,
} from "@/lib/utils";
import { sectionTagPaletteClasses } from "@/lib/presidential-brief/sectionTagPalette";
import { hapticImpact } from "@/lib/presidential-brief/haptics";

interface BriefSummaryListViewProps {
  feed: FeedCard[];
  flaggedItems: Set<string>;
  onStoryActivate: (
    card: Extract<FeedCard, { type: "story" }>,
    originRect: DOMRect
  ) => void;
  /** 0-based story index whose row is nearest the reading line while scrolling */
  onListScrollStoryIndexChange?: (storyIndex: number) => void;
}

export default function BriefSummaryListView({
  feed,
  flaggedItems,
  onStoryActivate,
  onListScrollStoryIndexChange,
}: BriefSummaryListViewProps) {
  const rows = useMemo(
    () =>
      feed.filter(
        (c): c is Extract<FeedCard, { type: "story" }> => c.type === "story"
      ),
    [feed]
  );

  const listRef = useRef<HTMLUListElement>(null);
  const rowElementsRef = useRef<(HTMLLIElement | null)[]>([]);
  const scrollRafRef = useRef<number | null>(null);

  const computeReadingStoryIndex = useCallback((): number => {
    const root = listRef.current;
    const n = rows.length;
    if (!root || n === 0) return 0;

    const { scrollTop, scrollHeight, clientHeight } = root;
    const endSlop = 8;
    if (scrollTop <= endSlop) {
      return 0;
    }
    if (scrollTop + clientHeight >= scrollHeight - endSlop) {
      return n - 1;
    }

    const rootRect = root.getBoundingClientRect();
    const readingY = rootRect.top + Math.min(rootRect.height * 0.22, 72);

    const refs = rowElementsRef.current;
    for (let i = 0; i < n; i++) {
      const el = refs[i];
      if (!el) continue;
      const r = el.getBoundingClientRect();
      if (r.top <= readingY && r.bottom > readingY) {
        return i;
      }
    }

    const last = refs[n - 1];
    if (last) {
      const r = last.getBoundingClientRect();
      if (readingY >= r.bottom) return n - 1;
    }
    const first = refs[0];
    if (first) {
      const r = first.getBoundingClientRect();
      if (readingY < r.top) return 0;
    }

    let best = 0;
    let bestDist = Number.POSITIVE_INFINITY;
    for (let i = 0; i < n; i++) {
      const el = refs[i];
      if (!el) continue;
      const r = el.getBoundingClientRect();
      const mid = (r.top + r.bottom) / 2;
      const d = Math.abs(mid - readingY);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    }
    return best;
  }, [rows.length]);

  const reportScrollIndex = useCallback(() => {
    if (!onListScrollStoryIndexChange) return;
    onListScrollStoryIndexChange(computeReadingStoryIndex());
  }, [computeReadingStoryIndex, onListScrollStoryIndexChange]);

  const scheduleReport = useCallback(() => {
    if (!onListScrollStoryIndexChange) return;
    if (scrollRafRef.current != null) return;
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null;
      reportScrollIndex();
    });
  }, [onListScrollStoryIndexChange, reportScrollIndex]);

  useLayoutEffect(() => {
    rowElementsRef.current.length = rows.length;
  }, [rows.length]);

  useLayoutEffect(() => {
    reportScrollIndex();
  }, [rows.length, reportScrollIndex]);

  useEffect(() => {
    return () => {
      if (scrollRafRef.current != null) {
        cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!onListScrollStoryIndexChange) return;
    const root = listRef.current;
    if (!root || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => scheduleReport());
    ro.observe(root);
    return () => ro.disconnect();
  }, [onListScrollStoryIndexChange, scheduleReport]);

  return (
    <ul
      ref={listRef}
      onScroll={scheduleReport}
      className="mx-auto min-h-0 w-full max-w-2xl list-none flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain bg-bg-primary px-4 pb-8 pt-5 sm:pb-10 sm:pt-7 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      aria-label="Briefing list"
    >
      {rows.map((card, index) => (
        <SummaryRow
          key={card.item.id}
          rowRef={(el) => {
            rowElementsRef.current[index] = el;
          }}
          card={card}
          isFirst={index === 0}
          isFlagged={flaggedItems.has(card.item.id)}
          onActivate={onStoryActivate}
        />
      ))}
    </ul>
  );
}

function SummaryRow({
  rowRef: setLiRef,
  card,
  isFirst,
  isFlagged,
  onActivate,
}: {
  rowRef: (el: HTMLLIElement | null) => void;
  card: Extract<FeedCard, { type: "story" }>;
  isFirst: boolean;
  isFlagged: boolean;
  onActivate: (
    card: Extract<FeedCard, { type: "story" }>,
    originRect: DOMRect
  ) => void;
}) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const { item } = card;
  const section = item.section?.trim() ?? "";

  return (
    <li
      ref={setLiRef}
      className="border-b border-rule-light/80 last:border-b-0"
    >
      <button
        ref={buttonRef}
        type="button"
        className={cn(
          "flex w-full flex-col items-stretch gap-2 text-left transition-opacity hover:opacity-85 active:opacity-70",
          isFirst
            ? "pb-6 pt-0 sm:pb-8"
            : "py-6 sm:py-8"
        )}
        onClick={() => {
          void hapticImpact("light");
          const el = buttonRef.current;
          if (el) {
            onActivate(card, el.getBoundingClientRect());
          }
        }}
      >
        {card.followUp ? (
          <div className="mb-4 min-w-0 text-left">
            <p className="mb-1.5 font-ui text-[12px] font-medium uppercase tracking-wider text-text-muted">
              Research request
            </p>
            {card.followUp.request_note?.trim() ? (
              <p className="border-l-2 border-accent pl-3 font-body text-[14px] leading-snug text-text-secondary">
                {card.followUp.request_note.trim()}
              </p>
            ) : (
              <p className="border-l-2 border-accent pl-3 font-body text-[13px] leading-snug text-text-muted">
                You requested a follow-up from the{" "}
                {formatBriefDateShort(card.followUp.brief_date)} brief.
              </p>
            )}
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          {section ? (
            <span
              className={cn(
                "inline-flex max-w-full shrink-0 items-center rounded-full px-2.5 py-0.5 font-ui text-[12px] font-semibold sm:text-[13px]",
                sectionTagPaletteClasses(section)
              )}
            >
              {formatSectionTagLabel(section)}
            </span>
          ) : null}
          {isFlagged ? (
            <span className="font-ui text-[10px] font-medium uppercase tracking-wider text-accent">
              Flagged
            </span>
          ) : null}
        </div>
        <span className="font-display text-[16px] font-normal leading-snug tracking-[-0.01em] text-text-primary sm:text-[17px]">
          {item.headline}
        </span>
      </button>
    </li>
  );
}
