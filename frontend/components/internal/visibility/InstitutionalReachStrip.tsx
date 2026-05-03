import type { IFMKpi } from "@/lib/types/internal-intelligence";

interface InstitutionalReachStripProps {
  metrics: IFMKpi[];
}

export function InstitutionalReachStrip({ metrics }: InstitutionalReachStripProps) {
  return (
    <div className="grid grid-cols-3 gap-[14px]">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="bg-bg-tertiary rounded-sm border border-border-primary px-4 py-3"
        >
          <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
            {metric.label}
          </p>
          <p className="mt-1 font-mono text-lg font-bold text-text-muted">
            {metric.value}
          </p>
          {metric.note && (
            <p className="mt-0.5 font-mono text-[11px] text-text-muted">
              {metric.note}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
