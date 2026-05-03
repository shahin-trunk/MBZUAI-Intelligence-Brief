"use client";

import { cn } from "@/lib/utils";

export type HorizontalBarChartRow = {
  label: string;
  /** Bar width as percentage of the row (0–100). */
  value: number;
};

export interface HorizontalBarChartProps {
  title: string;
  rows: readonly HorizontalBarChartRow[];
  barFillClassName: string;
  className?: string;
}

/**
 * Horizontal bar chart — DOM only, same chrome as the sample table / vertical chart.
 * Thin track shows full scale; bar segment is interactive.
 */
export default function HorizontalBarChart({
  title,
  rows,
  barFillClassName,
  className,
}: HorizontalBarChartProps) {
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
      <div className="space-y-3.5 bg-bg-surface-2/40 px-4 py-4">
        {rows.map((row) => {
          const w = Math.min(100, Math.max(0, row.value));
          const tip = `${row.label}: ${w}%`;

          return (
            <div key={row.label}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 font-body text-[14px] leading-snug text-text-primary">
                  {row.label}
                </span>
                <span className="shrink-0 font-mono text-[14px] tabular-nums text-text-muted">
                  {w}%
                </span>
              </div>
              <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-text-muted/15">
                <button
                  type="button"
                  title={tip}
                  aria-label={tip}
                  className={cn(
                    "h-full min-w-[6px] rounded-full transition-[opacity,transform] duration-150 ease-out",
                    "hover:opacity-90 active:scale-[0.99]",
                    "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-surface",
                    barFillClassName
                  )}
                  style={{ width: `${w}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </figure>
  );
}
