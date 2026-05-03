"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { SECTION_ORDER, type Brief, type BriefItem } from "@/lib/types/brief";
import { SwipeableCard } from "./SwipeableCard";
import { useEntityLogos } from "@/lib/hooks/useEntityLogos";
import { entityLogoLookupNames } from "@/lib/entity-badge";

const SECTION_LABELS: Record<string, string> = {
  UAE: "UAE",
  "Regional Research & Academic Events": "Regional",
  "International Politics & Policy": "Politics",
  "International Business & Technology": "Business",
  "Model Releases & Technical Developments": "Models",
};

interface CardReaderProps {
  brief: Brief;
  onSwitchToList?: () => void;
}

export function CardReader({ brief, onSwitchToList }: CardReaderProps) {
  const allItems = useMemo<BriefItem[]>(
    () =>
      brief.items?.length
        ? brief.items
        : brief.sections.flatMap((section) => section.items),
    [brief]
  );

  const [currentIndex, setCurrentIndex] = useState(0);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const [savingItemId, setSavingItemId] = useState<string | null>(null);
  const { resolve: resolveEntityLogo } = useEntityLogos();

  const logInteraction = useCallback(
    async (itemId: string, action: "dismissed" | "saved" | "expanded") => {
      try {
        await fetch("/api/reader-interactions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            brief_date: brief.brief_date,
            item_id: itemId,
            action,
          }),
        });
      } catch {
        // Logging should never interrupt the reading flow.
      }
    },
    [brief.brief_date],
  );

  const currentItem = allItems[currentIndex];
  const totalItems = allItems.length;
  const isComplete = currentIndex >= totalItems;

  // Current section label
  const currentSection = currentItem?.section ?? "";

  const advance = useCallback(() => {
    setCurrentIndex((prev) => Math.min(prev + 1, totalItems));
  }, [totalItems]);

  useEffect(() => {
    let cancelled = false;

    async function loadSavedItems() {
      const res = await fetch(`/api/saved-items?brief_date=${brief.brief_date}`);
      if (!res.ok) return;
      const data = await res.json();
      if (cancelled) return;
      setSaved(new Set((data.items ?? []).map((item: { item_id: string }) => item.item_id)));
    }

    void loadSavedItems();
    return () => {
      cancelled = true;
    };
  }, [brief.brief_date]);

  function handleDismiss() {
    if (currentItem) {
      setDismissed((prev) => new Set([...prev, currentItem.id]));
      void logInteraction(currentItem.id, "dismissed");
    }
    advance();
  }

  async function handleSave() {
    const item = currentItem;
    if (!item) {
      advance();
      return;
    }
    if (saved.has(item.id)) {
      advance();
      return;
    }

    setSavingItemId(item.id);
    try {
      const res = await fetch("/api/saved-items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brief_date: brief.brief_date,
          item_id: item.id,
        }),
      });
      const data = await res.json();
      if (res.ok && data.saved) {
        setSaved((prev) => new Set([...prev, item.id]));
        void logInteraction(item.id, "saved");
      }
    } finally {
      setSavingItemId(null);
      advance();
    }
  }

  function handleExpand() {
    if (currentItem) {
      void logInteraction(currentItem.id, "expanded");
    }
  }

  // Jump to section
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
          Brief Complete
        </h2>
        <p className="text-text-muted mb-6">
          {saved.size} saved, {dismissed.size} dismissed
        </p>
        <div className="flex gap-3">
          {saved.size > 0 && (
            <button
              onClick={() => {
                setCurrentIndex(0);
                setDismissed(new Set());
              }}
              className="px-4 py-2 rounded-lg bg-accent-primary/10 text-accent-primary text-sm hover:bg-accent-primary/20"
            >
              Read Again
            </button>
          )}
          {!saved.size && (
            <button
              onClick={() => {
                setCurrentIndex(0);
                setDismissed(new Set());
              }}
              className="px-4 py-2 rounded-lg bg-accent-primary/10 text-accent-primary text-sm hover:bg-accent-primary/20"
            >
              Restart
            </button>
          )}
          {onSwitchToList && (
            <button
              onClick={onSwitchToList}
              className="px-4 py-2 rounded-lg border border-border-secondary text-text-muted text-sm hover:text-text-primary"
            >
              Switch to List View
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header: progress + section */}
      <div className="px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          {/* Section label (tappable for picker) */}
          <button
            onClick={() => {
              // Simple section picker: cycle to next section
              const currentSectionIdx = SECTION_ORDER.indexOf(currentSection as typeof SECTION_ORDER[number]);
              const nextSection = SECTION_ORDER[(currentSectionIdx + 1) % SECTION_ORDER.length];
              jumpToSection(nextSection);
            }}
            className="text-[10px] uppercase tracking-wider text-accent-primary font-medium hover:text-accent-primary/80"
          >
            {SECTION_LABELS[currentSection] ?? currentSection}
          </button>
        </div>

        <div className="flex items-center gap-3">
          {/* Progress counter */}
          <span className="text-xs tabular-nums text-text-muted">
            {currentIndex + 1}/{totalItems}
          </span>
          {onSwitchToList && (
            <button
              onClick={onSwitchToList}
              className="text-[10px] text-text-muted hover:text-text-primary uppercase tracking-wider"
            >
              List
            </button>
          )}
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
        {/* Render top 3 cards for depth effect */}
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

      {/* Bottom controls (for non-touch / accessibility) */}
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
          onClick={() => void handleSave()}
          disabled={savingItemId === currentItem?.id}
          className="w-12 h-12 rounded-full border-2 border-amber-400/30 flex items-center justify-center text-amber-400 hover:bg-amber-400/10 transition-colors disabled:opacity-50"
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
