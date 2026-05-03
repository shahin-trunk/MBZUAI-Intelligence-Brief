import type { IFMKpi, AcademyNotableParticipant } from "@/lib/types/internal-intelligence";

interface AcademyKpiStripProps {
  kpis: IFMKpi[];
  notableParticipants?: AcademyNotableParticipant[];
}

export function AcademyKpiStrip({ kpis, notableParticipants }: AcademyKpiStripProps) {
  return (
    <div className="space-y-4">
      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-[14px]">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className="bg-bg-tertiary rounded-sm border border-border-primary px-7 py-[22px]"
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              {kpi.label}
            </p>
            <p className="mt-2 font-mono text-3xl font-bold text-text-bright leading-none">
              {kpi.value}
            </p>
            {kpi.note && (
              <p className="mt-1 font-mono text-[12px] text-text-muted">
                {kpi.note}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Notable participants strip */}
      {notableParticipants && notableParticipants.length > 0 && (
        <div className="bg-bg-tertiary rounded-sm border border-border-primary px-5 py-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted shrink-0">
              Notable
            </span>
            {notableParticipants.map((p, i) => (
              <span key={p.name} className="flex items-center gap-1">
                {i > 0 && (
                  <span className="font-mono text-[13px] text-text-muted mr-1">
                    ·
                  </span>
                )}
                <span className="font-mono text-[13px] text-text-secondary">
                  {p.name}
                </span>
                <span className="font-mono text-[12px] text-text-muted">
                  ({p.title})
                </span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
