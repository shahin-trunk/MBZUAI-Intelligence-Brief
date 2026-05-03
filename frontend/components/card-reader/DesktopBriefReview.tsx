"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { Brief, BriefItem } from "@/lib/types/brief";
import { renderAnalysisBlock, renderMarkdown } from "@/lib/rendering/markdown";
import { ExhibitRenderer } from "./ExhibitRenderer";
import { ItemAudioButton } from "./ItemAudioButton";

const SECTION_LABELS: Record<string, string> = {
  UAE: "UAE",
  "Regional Research & Academic Events": "Regional",
  "International Politics & Policy": "Politics",
  "International Business & Technology": "Business",
  "Model Releases & Technical Developments": "Models",
};

interface DesktopBriefReviewProps {
  brief: Brief;
  onSwitchToSwipe?: () => void;
}

function getBullets(item: BriefItem): string[] {
  if (item.key_bullets?.length) {
    return item.key_bullets;
  }
  if (item.main_bullet) {
    return [item.main_bullet];
  }
  return [];
}

function getAnalysis(item: BriefItem): string {
  return item.analysis ?? [item.context, item.implication].filter(Boolean).join(" ");
}

export function DesktopBriefReview({
  brief,
  onSwitchToSwipe,
}: DesktopBriefReviewProps) {
  const allItems = useMemo<BriefItem[]>(
    () =>
      brief.items?.length
        ? brief.items
        : brief.sections.flatMap((section) => section.items),
    [brief],
  );

  const [selectedItemId, setSelectedItemId] = useState<string | null>(
    allItems[0]?.id ?? null,
  );
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const [savingItemId, setSavingItemId] = useState<string | null>(null);

  useEffect(() => {
    if (!allItems.length) {
      setSelectedItemId(null);
      return;
    }

    const stillExists = selectedItemId
      ? allItems.some((item) => item.id === selectedItemId)
      : false;

    if (!stillExists) {
      setSelectedItemId(allItems[0].id);
    }
  }, [allItems, selectedItemId]);

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

  const selectedIndex = allItems.findIndex((item) => item.id === selectedItemId);
  const selectedItem =
    (selectedIndex >= 0 ? allItems[selectedIndex] : null) ?? allItems[0] ?? null;

  const moveSelection = useCallback(
    (delta: number) => {
      if (!allItems.length) return;
      const baseIndex = selectedIndex >= 0 ? selectedIndex : 0;
      const nextIndex = Math.max(0, Math.min(baseIndex + delta, allItems.length - 1));
      setSelectedItemId(allItems[nextIndex].id);
    },
    [allItems, selectedIndex],
  );

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const tagName = target?.tagName;
      if (
        target?.isContentEditable
        || tagName === "INPUT"
        || tagName === "TEXTAREA"
        || tagName === "SELECT"
      ) {
        return;
      }

      if (event.key === "ArrowDown" || event.key === "j") {
        event.preventDefault();
        moveSelection(1);
      } else if (event.key === "ArrowUp" || event.key === "k") {
        event.preventDefault();
        moveSelection(-1);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [moveSelection]);

  const handleSave = useCallback(async () => {
    if (!selectedItem || saved.has(selectedItem.id)) return;

    setSavingItemId(selectedItem.id);
    try {
      const res = await fetch("/api/saved-items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brief_date: brief.brief_date,
          item_id: selectedItem.id,
        }),
      });
      const data = await res.json();
      if (res.ok && data.saved) {
        setSaved((prev) => new Set([...prev, selectedItem.id]));
      }
    } finally {
      setSavingItemId(null);
    }
  }, [brief.brief_date, saved, selectedItem]);

  if (!selectedItem) {
    return null;
  }

  const bullets = getBullets(selectedItem);
  const analysis = getAnalysis(selectedItem);
  const sectionLabel = SECTION_LABELS[selectedItem.section] ?? selectedItem.section;

  return (
    <div className="grid gap-6 px-4 pb-8 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="rounded-2xl border border-border-primary bg-surface-secondary">
        <div className="border-b border-border-primary px-4 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-mono uppercase tracking-[0.14em] text-text-muted">
                Review Mode
              </p>
              <p className="mt-1 text-sm text-text-primary">
                {allItems.length} items in published order
              </p>
            </div>
            {onSwitchToSwipe && (
              <button
                onClick={onSwitchToSwipe}
                className="rounded-lg border border-border-secondary px-3 py-1.5 text-xs text-text-muted hover:text-text-primary"
              >
                Swipe View
              </button>
            )}
          </div>
          <p className="mt-3 text-xs text-text-muted">
            Use the list or press ↑/↓ to move between items.
          </p>
        </div>

        <div className="max-h-[70vh] overflow-y-auto p-2">
          {allItems.map((item, index) => {
            const active = item.id === selectedItem.id;
            const snippet = getBullets(item)[0] ?? item.analysis ?? item.context ?? "";

            return (
              <button
                key={item.id}
                onClick={() => setSelectedItemId(item.id)}
                className={cn(
                  "mb-2 w-full rounded-xl border px-3 py-3 text-left transition-colors",
                  active
                    ? "border-accent-primary bg-accent-primary/10"
                    : "border-border-secondary bg-surface-primary hover:border-accent-primary/30 hover:bg-surface-elevated",
                )}
                aria-current={active ? "true" : undefined}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="text-xs font-mono text-text-muted">
                    {index + 1}
                  </span>
                  <span className="rounded-full bg-bg-tertiary px-2 py-0.5 text-[10px] uppercase tracking-wider text-text-muted">
                    {SECTION_LABELS[item.section] ?? item.section}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium leading-snug text-text-primary">
                  {item.headline}
                </p>
                {snippet && (
                <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-text-muted">
                    {renderMarkdown(snippet)}
                </p>
              )}
              </button>
            );
          })}
        </div>
      </aside>

      <section className="rounded-2xl border border-border-primary bg-surface-secondary">
        <div className="border-b border-border-primary px-5 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-accent-primary/10 px-2.5 py-1 text-[10px] uppercase tracking-wider text-accent-primary">
              {sectionLabel}
            </span>
            {(selectedItem.primary_subject ?? selectedItem.primary_entity) && (
              <span className="rounded-full bg-bg-tertiary px-2.5 py-1 text-[10px] uppercase tracking-wider text-text-muted">
                {selectedItem.primary_subject ?? selectedItem.primary_entity}
              </span>
            )}
            <span className="text-xs text-text-muted">
              {selectedIndex + 1} of {allItems.length}
            </span>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              onClick={() => moveSelection(-1)}
              disabled={selectedIndex <= 0}
              className="rounded-lg border border-border-secondary px-3 py-2 text-sm text-text-muted hover:text-text-primary disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => moveSelection(1)}
              disabled={selectedIndex >= allItems.length - 1}
              className="rounded-lg border border-border-secondary px-3 py-2 text-sm text-text-muted hover:text-text-primary disabled:opacity-50"
            >
              Next
            </button>
            <button
              onClick={() => void handleSave()}
              disabled={savingItemId === selectedItem.id || saved.has(selectedItem.id)}
              className="rounded-lg bg-accent-primary/10 px-3 py-2 text-sm text-accent-primary hover:bg-accent-primary/20 disabled:opacity-50"
            >
              {saved.has(selectedItem.id) ? "Saved" : "Save Item"}
            </button>
            {selectedItem.audio_url && <ItemAudioButton audioUrl={selectedItem.audio_url} />}
            {selectedItem.source_url && (
              <a
                href={selectedItem.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-border-secondary px-3 py-2 text-sm text-text-muted hover:text-text-primary"
              >
                Open Source
              </a>
            )}
          </div>
        </div>

        <div className="px-5 py-5 lg:px-8 lg:py-7">
          <h2
            className="text-3xl leading-tight font-semibold text-text-primary"
            style={{ fontFamily: "var(--font-heading, 'Playfair Display', serif)" }}
          >
            {selectedItem.headline}
          </h2>

          {bullets.length > 0 && (
            <div className="mt-6 grid gap-3">
              {bullets.map((bullet, index) => (
                <div key={`${selectedItem.id}-bullet-${index}`} className="flex gap-3 rounded-xl bg-bg-tertiary px-4 py-3">
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent-primary" />
                  <p className="text-sm leading-relaxed text-text-primary">
                    {renderMarkdown(bullet)}
                  </p>
                </div>
              ))}
            </div>
          )}

          {analysis && (
            <div className="mt-6 rounded-2xl border border-border-secondary bg-surface-primary px-5 py-4">
              <p className="text-xs font-mono uppercase tracking-[0.14em] text-text-muted">
                Analysis
              </p>
              <div className="mt-3 text-sm leading-7 text-text-primary">
                {renderAnalysisBlock(analysis)}
              </div>
            </div>
          )}

          {selectedItem.exhibits?.length ? (
            <div className="mt-6">
              <p className="text-xs font-mono uppercase tracking-[0.14em] text-text-muted">
                Exhibits
              </p>
              <div className="mt-3 space-y-4">
                {selectedItem.exhibits.map((exhibit, index) => (
                  <ExhibitRenderer key={`${selectedItem.id}-exhibit-${index}`} exhibit={exhibit} />
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-text-muted">
            <span>{selectedItem.source_name}</span>
          </div>
        </div>
      </section>
    </div>
  );
}
