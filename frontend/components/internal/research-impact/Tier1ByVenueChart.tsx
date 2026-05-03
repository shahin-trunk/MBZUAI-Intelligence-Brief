"use client";

import type { Tier1VenueCount } from "@/lib/types/internal-intelligence";

interface Tier1ByVenueChartProps {
  data: Tier1VenueCount[];
  tier1Definition: string;
}

export function Tier1ByVenueChart({ data, tier1Definition }: Tier1ByVenueChartProps) {
  const sorted = [...data].sort((a, b) => b.count - a.count);
  const maxCount = sorted[0]?.count ?? 1;
  const totalCount = sorted.reduce((sum, item) => sum + item.count, 0);

  function shareLabel(count: number) {
    if (!totalCount) return "0% of total";
    return `${Math.round((count / totalCount) * 100)}% of tier 1`;
  }

  return (
    <div className="rounded-sm border border-border-primary bg-bg-tertiary p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Tier 1 Publications by Venue (YTD)
          </p>
          <p className="mt-2 max-w-md text-[14px] leading-relaxed text-text-secondary">
            Distribution of tier 1 publications across priority venues.
          </p>
        </div>
        <div className="shrink-0 rounded-sm border border-border-primary bg-bg-primary/60 px-2.5 py-1">
          <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-muted">
            Venues
          </p>
          <p className="mt-0.5 text-right font-mono text-sm font-semibold text-text-bright">
            {sorted.length}
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-[14px]">
        {sorted.map((item) => {
          const width = Math.max((item.count / maxCount) * 100, item.count > 0 ? 8 : 0);

          return (
            <div
              key={item.venue}
              className="rounded-sm border border-border-primary/70 bg-bg-primary/35 px-3 py-2.5"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[14px] leading-snug text-text-primary">
                    {item.venue}
                  </p>
                  <p className="mt-0.5 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                    {shareLabel(item.count)}
                  </p>
                </div>
                <p className="shrink-0 font-mono text-base font-semibold text-text-bright tabular-nums">
                  {item.count}
                </p>
              </div>
              <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-bg-primary">
                <div
                  className="h-full rounded-full bg-sig-high"
                  style={{ width: `${width}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-4 border-t border-border-primary pt-3 font-mono text-[14px] italic leading-[1.6] text-text-muted">
        {tier1Definition}
      </p>
    </div>
  );
}
