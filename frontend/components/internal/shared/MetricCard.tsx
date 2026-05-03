import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { EvidenceMetric } from "@/lib/types/internal-intelligence";

interface MetricCardProps {
  metric: EvidenceMetric;
}

function formatValue(value: string | number, format?: string): string {
  if (typeof value === "string") return value;

  switch (format) {
    case "percentage":
      return `${value}%`;
    case "currency":
      return `$${value.toLocaleString()}`;
    case "number":
      return value.toLocaleString();
    default:
      return String(value);
  }
}

export function MetricCard({ metric }: MetricCardProps) {
  const flagBorder =
    metric.flagLevel === "amber"
      ? "border-l-2 border-l-accent-warning"
      : metric.flagLevel === "red"
        ? "border-l-2 border-l-accent-danger"
        : "";

  return (
    <div
      className={cn(
        "bg-bg-tertiary rounded-sm border border-border-primary px-4 py-3",
        flagBorder
      )}
    >
      {/* Label */}
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
        {metric.label}
      </p>

      {/* Value */}
      <p className="mt-1 font-mono text-xl font-bold text-text-bright">
        {formatValue(metric.value, metric.format)}
      </p>

      {/* Trend */}
      <div className="mt-1.5 flex items-center gap-1.5">
        {metric.trend === "up" && (
          <TrendingUp className="h-3 w-3 text-accent-success" />
        )}
        {metric.trend === "down" && (
          <TrendingDown className="h-3 w-3 text-accent-warning" />
        )}
        {metric.trend === "stable" && (
          <Minus className="h-3 w-3 text-text-muted" />
        )}
        {metric.trend === "new" && (
          <span className="rounded-sm bg-sig-high/15 px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase text-sig-high border border-sig-high/30">
            New
          </span>
        )}
        {metric.trendLabel && (
          <span className="font-mono text-[12px] text-text-muted">
            {metric.trendLabel}
          </span>
        )}
      </div>
    </div>
  );
}
