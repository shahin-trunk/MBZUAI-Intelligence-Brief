"use client";

import { cn } from "@/lib/utils";

export type VerticalBarChartRow = {
  /** Category below the column (x-axis). */
  xLabel: string;
  /** Relative height; scaled to max(row.value). */
  value: number;
  /** Label above the bar (e.g. "68%"). */
  valueLabel: string;
  emphasize?: boolean;
};

export interface VerticalBarChartProps {
  /** Header strip — same chrome as `StoryDetailMockTable` figcaption. */
  title: string;
  rows: readonly VerticalBarChartRow[];
  /** Bar fill (e.g. `bg-accent/75`, `bg-sig-medium/75`). */
  barFillClassName: string;
  chartHeightPx?: number;
  minHeightPercent?: number;
  className?: string;
}

/**
 * Vertical column chart built from DOM + Tailwind (no images).
 * Styling aligned with the in-app sample table; bars are focusable buttons with hover/title.
 */
export default function VerticalBarChart({
  title,
  rows,
  barFillClassName,
  chartHeightPx = 148,
  minHeightPercent = 8,
  className,
}: VerticalBarChartProps) {
  const maxValue = Math.max(1, ...rows.map((r) => r.value));

  return (
    <figure
      className={cn(
        "w-full min-w-0 overflow-hidden rounded-xl border border-rule-light",
        className
      )}
    >
      <figcaption className="border-b border-rule-light bg-bg-surface-2/50 px-4 py-2.5 text-left font-serif text-[14px] font-medium normal-case tracking-normal text-text-muted">
        {title}
      </figcaption>
      <div className="bg-bg-surface-2/40 px-4 pb-5 pt-4">
        <div
          className="flex gap-2 sm:gap-3"
          role="list"
          aria-label={title}
        >
          {rows.map((row) => {
            const pct = Math.max(
              minHeightPercent,
              (row.value / maxValue) * 100
            );
            const tip = `${row.xLabel}: ${row.valueLabel}`;

            return (
              <div
                key={row.xLabel}
                role="listitem"
                className="flex min-w-0 flex-1 flex-col items-center"
              >
                <span
                  className={cn(
                    "mb-2 flex h-[22px] shrink-0 items-end justify-center font-mono text-[14px] tabular-nums leading-none",
                    row.emphasize
                      ? "font-semibold text-accent"
                      : "text-text-secondary"
                  )}
                >
                  {row.valueLabel}
                </span>
                <div
                  className="flex w-full flex-col justify-end"
                  style={{ height: chartHeightPx }}
                >
                  <button
                    type="button"
                    title={tip}
                    aria-label={tip}
                    className={cn(
                      "mx-auto w-[min(100%,3.5rem)] min-h-[6px] rounded-t-lg transition-[opacity,transform] duration-150 ease-out",
                      "hover:opacity-90 active:scale-[0.98]",
                      "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-surface",
                      barFillClassName
                    )}
                    style={{ height: `${pct}%` }}
                  />
                </div>
                <p className="mt-3 text-center font-body text-[14px] leading-tight text-text-secondary">
                  {row.xLabel}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </figure>
  );
}
