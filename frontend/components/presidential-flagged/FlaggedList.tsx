"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";
import { formatBriefDate } from "@/lib/utils";

export interface FlaggedArchiveItem {
  id: string;
  item_id: string;
  brief_date: string;
  headline: string | null;
  source_name: string | null;
  section: string | null;
  main_bullet: string | null;
}

interface FlaggedListProps {
  items: FlaggedArchiveItem[];
  isLoading: boolean;
  onUnflag: (flagId: string, itemId: string, briefDate: string) => void;
  onBack: () => void;
}

function groupByDate(items: FlaggedArchiveItem[]) {
  const map = new Map<string, FlaggedArchiveItem[]>();

  for (const item of items) {
    const existing = map.get(item.brief_date);
    if (existing) {
      existing.push(item);
    } else {
      map.set(item.brief_date, [item]);
    }
  }

  return Array.from(map.entries()).sort(([a], [b]) => b.localeCompare(a));
}

export function FlaggedList({
  items,
  isLoading,
  onUnflag,
  onBack,
}: FlaggedListProps) {
  const grouped = groupByDate(items);

  return (
    <div className="mx-auto max-w-lg px-5 py-6">
      <button
        type="button"
        onClick={onBack}
        className="mb-5 text-sm text-accent"
        aria-label="Back to brief"
      >
        ← Back to brief
      </button>

      <h1 className="font-display text-xl font-bold text-text-primary">Flagged Items</h1>
      <p className="mt-1.5 text-[12px] text-text-muted">
        Flags are saved while you read. Saved items from recent briefs appear here.
      </p>

      {isLoading ? (
        <div className="mt-6 flex items-center justify-center rounded-[4px] border border-border-divider bg-bg-surface px-5 py-6 text-center">
          <div className="inline-flex items-center gap-2 font-body text-[12.5px] text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading flagged items
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="mt-6 rounded-[4px] border border-border-divider bg-bg-surface px-5 py-6 text-center">
          <p className="font-display text-[15px] font-semibold text-text-primary">
            No flagged items yet
          </p>
          <p className="mt-1 font-body text-[12.5px] text-text-muted">
            Swipe left on any story to flag it.
          </p>
        </div>
      ) : (
        <div className="mt-8">
          <p className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[2px] text-accent">
            Flagged archive
          </p>
          {grouped.map(([date, dateItems]) => (
            <section key={date} className="mb-5">
              <p className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-text-muted">
                {formatBriefDate(date)}
              </p>
              <div>
                {dateItems.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-start justify-between gap-3 border-b border-border-divider py-3 last:border-b-0"
                  >
                    <Link
                      href={`/brief/${item.brief_date}`}
                      className="flex min-w-0 flex-1 items-start gap-2.5 text-left"
                    >
                      <span className="mt-0.5 shrink-0 text-accent" aria-hidden>
                        ⚑
                      </span>
                      <div className="min-w-0">
                        <p className="font-display text-sm font-semibold leading-snug text-text-primary">
                          {item.headline ?? "Untitled item"}
                        </p>
                        <p className="mt-0.5 font-mono text-[11px] text-text-muted">
                          {item.source_name ?? formatBriefDate(item.brief_date)}
                        </p>
                      </div>
                    </Link>
                    <button
                      type="button"
                      onClick={() => onUnflag(item.id, item.item_id, item.brief_date)}
                      className="shrink-0 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-text-muted transition-colors hover:text-accent"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
