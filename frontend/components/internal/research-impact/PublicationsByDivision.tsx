import type { DivisionPublications } from "@/lib/types/internal-intelligence";

interface PublicationsByDivisionProps {
  data: DivisionPublications[];
}

export function PublicationsByDivision({ data }: PublicationsByDivisionProps) {
  const sortedData = [...data].sort((a, b) => b.tier1 - a.tier1);
  const maxCount = sortedData[0]?.tier1 ?? 1;
  const totalTier1 = sortedData.reduce((sum, item) => sum + item.tier1, 0);

  function shareLabel(count: number) {
    if (!totalTier1) return "0% of total";
    return `${Math.round((count / totalTier1) * 100)}% of tier 1`;
  }

  return (
    <div className="rounded-sm border border-border-primary bg-bg-tertiary p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Tier 1 Publications by Division (YTD)
          </p>
          <p className="mt-2 max-w-md text-[14px] leading-relaxed text-text-secondary">
            Distribution of tier 1 publications across academic divisions.
          </p>
        </div>
        <div className="shrink-0 rounded-sm border border-border-primary bg-bg-primary/60 px-2.5 py-1">
          <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-muted">
            Total Tier 1
          </p>
          <p className="mt-0.5 text-right font-mono text-sm font-semibold text-text-bright">
            {totalTier1}
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {sortedData.map((item) => {
          const width = Math.max((item.tier1 / maxCount) * 100, item.tier1 > 0 ? 8 : 0);

          return (
            <div
              key={item.division}
              className="rounded-sm border border-border-primary/70 bg-bg-primary/35 px-3 py-3"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-[14px] leading-snug text-text-primary">
                    {item.division}
                  </p>
                  <p className="mt-0.5 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                    {shareLabel(item.tier1)}
                  </p>
                </div>
                <p className="shrink-0 font-mono text-[18px] font-semibold text-text-bright tabular-nums">
                  {item.tier1}
                </p>
              </div>

              <div className="mt-3 h-2 overflow-hidden rounded-full bg-bg-primary">
                <div
                  className="h-full rounded-full bg-sig-high"
                  style={{ width: `${width}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
