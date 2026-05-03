"use client";

import type { IFMExecutiveData } from "@/lib/types/internal-intelligence";
import { IFMDailyUsersTrend } from "./IFMDailyUsersTrend";
import { IFMDownloadMomentum } from "./IFMDownloadMomentum";

interface IFMExecutiveViewProps {
  data: IFMExecutiveData;
}

export function IFMExecutiveView({ data }: IFMExecutiveViewProps) {
  return (
    <div className="space-y-6">
      {/* Executive insight */}
      <p className="font-serif text-base font-medium leading-[1.6] text-sig-high">
        {data.executiveSummary}
      </p>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-[14px]">
        {data.kpis.map((kpi) => (
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

      {/* Daily users trend */}
      <IFMDailyUsersTrend data={data.dailyUsersTrend} />

      {/* Download momentum */}
      <IFMDownloadMomentum data={data.recentDownloadsByModel} />
    </div>
  );
}
