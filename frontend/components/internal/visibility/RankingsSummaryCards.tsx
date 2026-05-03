import { cn } from "@/lib/utils";
import type { RankingSummary } from "@/lib/types/internal-intelligence";

interface RankingsSummaryCardsProps {
  summaries: RankingSummary[];
}

function directionArrow(direction: "up" | "down" | "flat"): string {
  if (direction === "up") return "\u2191";
  if (direction === "down") return "\u2193";
  return "\u2192";
}

export function RankingsSummaryCards({ summaries }: RankingsSummaryCardsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
      {summaries.map((summary) => {
        const hasFields = summary.fields && summary.fields.length > 0;

        return (
          <div
            key={summary.id}
            className={cn(
              "bg-bg-tertiary rounded-sm border border-border-primary px-5 py-5",
              hasFields && "border-l-4 border-l-sig-high"
            )}
          >
            {/* Title */}
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              {summary.title}
            </p>

            {/* Big rank number */}
            <p
              className={cn(
                "mt-3 font-mono text-4xl font-bold leading-none",
                hasFields ? "text-sig-high" : "text-text-bright"
              )}
            >
              #{summary.currentRank}
            </p>

            {/* Monthly movement */}
            <p className="mt-3 font-mono text-[14px] font-medium text-accent-success">
              {directionArrow(summary.monthlyMovement.direction)}
              {summary.monthlyMovement.positions} this month
            </p>
            {summary.monthlyMovement.note && (
              <p className="font-mono text-[12px] text-text-muted">
                {summary.monthlyMovement.note}
              </p>
            )}

            {/* YTD movement */}
            <p className="mt-2 font-mono text-[14px] font-medium text-accent-success">
              {directionArrow(summary.ytdMovement.direction)}
              {summary.ytdMovement.positions} positions YTD (from {summary.ytdMovement.from} to {summary.ytdMovement.to})
            </p>

            {/* Fields list */}
            {hasFields && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {summary.fields!.map((field) => (
                  <span
                    key={field}
                    className="inline-flex items-center rounded-full border border-sig-high/30 bg-sig-high/10 px-2 py-0.5 font-mono text-[12px] text-sig-high"
                  >
                    {field}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
