import { cn } from "@/lib/utils";
import type { Ranking } from "@/lib/types/internal-intelligence";

interface RankingsDisplayProps {
  rankings: Ranking[];
}

function MovementIndicator({ change, changeLabel }: { change: string; changeLabel: string }) {
  let colorClass: string;
  if (change === "up") {
    colorClass = "text-accent-success";
  } else if (change === "down") {
    colorClass = "text-accent-danger";
  } else {
    colorClass = "text-text-muted";
  }

  return (
    <p className={cn("font-mono text-[14px] font-medium", colorClass)}>
      {changeLabel}
    </p>
  );
}

export function RankingsDisplay({ rankings }: RankingsDisplayProps) {
  return (
    <div className="space-y-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
        Global Rankings
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {rankings.map((ranking) => {
          const isFlagship = (ranking as Ranking & { flagship?: boolean }).flagship === true;

          return (
            <div
              key={ranking.source}
              className={cn(
                "bg-bg-tertiary rounded-sm border border-border-primary px-5 py-5",
                isFlagship && "border-l-4 border-l-sig-high"
              )}
            >
              {/* Source */}
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted leading-snug">
                {ranking.source}
              </p>

              {/* Position */}
              <div className="mt-3 flex items-baseline gap-2">
                <span
                  className={cn(
                    "font-mono text-4xl font-bold leading-none",
                    isFlagship ? "text-sig-high" : "text-text-bright"
                  )}
                >
                  #{ranking.currentPosition}
                </span>
                {isFlagship && (
                  <span className="font-mono text-[12px] text-sig-high font-medium">
                    CORE AI
                  </span>
                )}
              </div>

              {/* Movement */}
              <div className="mt-2">
                <MovementIndicator
                  change={ranking.change}
                  changeLabel={ranking.changeLabel}
                />
              </div>

              {/* Year */}
              <p className="mt-1 font-mono text-[12px] text-text-muted">
                {ranking.year}
              </p>

              {/* Note */}
              {ranking.note && (
                <p className="mt-2 font-sans text-[14px] text-text-muted italic leading-[1.6]">
                  {ranking.note}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
