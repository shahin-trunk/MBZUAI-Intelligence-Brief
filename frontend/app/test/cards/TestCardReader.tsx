"use client";

import { useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import { SECTION_ORDER, type Brief, type BriefItem } from "@/lib/types/brief";
import { SwipeableCard } from "@/components/card-reader/SwipeableCard";
import { useEntityLogos } from "@/lib/hooks/useEntityLogos";
import { entityLogoLookupNames } from "@/lib/entity-badge";

/**
 * Fork of CardReader with console.log instrumentation for testing.
 * Logs every interaction event as structured JSON to the browser console.
 */

const SECTION_LABELS: Record<string, string> = {
  UAE: "UAE",
  "Regional Research & Academic Events": "Regional",
  "International Politics & Policy": "Politics",
  "International Business & Technology": "Business",
  "Model Releases & Technical Developments": "Models",
};

function logEvent(item: BriefItem, action: string) {
  console.log(
    JSON.stringify({
      item_id: item.id,
      headline: item.headline,
      action,
      section: item.section,
      timestamp: new Date().toISOString(),
    }),
  );
}

interface TestCardReaderProps {
  brief: Brief;
}

export function TestCardReader({ brief }: TestCardReaderProps) {
  // Flatten all items in section order
  const allItems: BriefItem[] = [];
  for (const section of brief.sections) {
    allItems.push(...section.items);
  }

  const [currentIndex, setCurrentIndex] = useState(0);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const { resolve: resolveEntityLogo } = useEntityLogos();

  const currentItem = allItems[currentIndex];
  const totalItems = allItems.length;
  const isComplete = currentIndex >= totalItems;

  const currentSection = currentItem?.section ?? "";

  const advance = useCallback(() => {
    setCurrentIndex((prev) => Math.min(prev + 1, totalItems));
  }, [totalItems]);

  function handleDismiss() {
    if (currentItem) {
      logEvent(currentItem, "dismiss");
      setDismissed((prev) => new Set([...prev, currentItem.id]));
    }
    advance();
  }

  function handleSave() {
    if (currentItem) {
      logEvent(currentItem, "save");
      setSaved((prev) => new Set([...prev, currentItem.id]));
    }
    advance();
  }

  function handleExpand() {
    if (currentItem) {
      logEvent(currentItem, "expand");
    }
  }

  function jumpToSection(sectionName: string) {
    const idx = allItems.findIndex((item) => item.section === sectionName);
    if (idx !== -1) setCurrentIndex(idx);
  }

  if (isComplete) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[80vh] text-center px-8">
        <h2
          className="text-2xl font-semibold mb-4"
          style={{ fontFamily: "var(--font-heading, 'Playfair Display', serif)" }}
        >
          Test Complete
        </h2>
        <p className="text-text-muted mb-4">
          {saved.size} saved, {dismissed.size} dismissed
        </p>
        <p className="text-xs text-text-muted mb-6">
          Check browser console for interaction logs
        </p>
        <button
          onClick={() => {
            setCurrentIndex(0);
            setDismissed(new Set());
            setSaved(new Set());
          }}
          className="px-4 py-2 rounded-lg border border-border-secondary text-text-muted text-sm hover:text-text-primary"
        >
          Restart
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100dvh)]">
      {/* Header: progress + section */}
      <div className="px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const currentSectionIdx = SECTION_ORDER.indexOf(
                currentSection as (typeof SECTION_ORDER)[number],
              );
              const nextSection =
                SECTION_ORDER[(currentSectionIdx + 1) % SECTION_ORDER.length];
              jumpToSection(nextSection);
            }}
            className="text-[10px] uppercase tracking-wider text-accent-primary font-medium hover:text-accent-primary/80"
          >
            {SECTION_LABELS[currentSection] ?? currentSection}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs tabular-nums text-text-muted">
            {currentIndex + 1}/{totalItems}
          </span>
          <span className="text-[10px] text-accent-primary/50 uppercase tracking-wider">
            Test Mode
          </span>
        </div>
      </div>

      {/* Progress dots */}
      <div className="px-4 pb-2 flex gap-0.5 shrink-0">
        {allItems.map((item, i) => (
          <div
            key={item.id}
            className={cn(
              "h-0.5 flex-1 rounded-full transition-colors",
              i < currentIndex
                ? saved.has(item.id)
                  ? "bg-accent-primary"
                  : "bg-text-muted/30"
                : i === currentIndex
                  ? "bg-text-primary"
                  : "bg-border-secondary",
            )}
          />
        ))}
      </div>

      {/* Card stack */}
      <div className="flex-1 relative mx-4 mb-4">
        {allItems.slice(currentIndex, currentIndex + 3).map((item, offset) => (
          <SwipeableCard
            key={item.id}
            item={item}
            entityLogo={entityLogoLookupNames(item).map(resolveEntityLogo).find(Boolean) ?? null}
            isTop={offset === 0}
            stackOffset={offset}
            onDismiss={handleDismiss}
            onSave={handleSave}
            onExpand={handleExpand}
          />
        ))}
      </div>

      {/* Bottom controls */}
      <div className="px-4 py-3 flex items-center justify-center gap-6 shrink-0">
        <button
          onClick={handleDismiss}
          className="w-12 h-12 rounded-full border-2 border-red-400/30 flex items-center justify-center text-red-400 hover:bg-red-400/10 transition-colors"
          aria-label="Dismiss"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 5l10 10M15 5L5 15" />
          </svg>
        </button>
        <button
          onClick={handleExpand}
          className="w-10 h-10 rounded-full border border-border-secondary flex items-center justify-center text-text-muted hover:text-text-primary transition-colors"
          aria-label="Read more"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 10l4-4 4 4" />
          </svg>
        </button>
        <button
          onClick={handleSave}
          className="w-12 h-12 rounded-full border-2 border-amber-400/30 flex items-center justify-center text-amber-400 hover:bg-amber-400/10 transition-colors"
          aria-label="Save"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 3h14v14l-7-4-7 4V3z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
