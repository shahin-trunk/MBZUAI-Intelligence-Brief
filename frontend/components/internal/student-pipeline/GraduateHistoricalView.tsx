"use client";

import type { HistoricalYearData } from "@/lib/types/internal-intelligence";

interface GraduateHistoricalViewProps {
  data: HistoricalYearData[];
}

const ROWS: { key: keyof HistoricalYearData; label: string; format?: "number" | "percentage" }[] = [
  { key: "totalApplications", label: "Total Applications", format: "number" },
  { key: "top100Applications", label: "Top 100 Applications", format: "number" },
  { key: "offersIssued", label: "Offers Issued", format: "number" },
  { key: "accepted", label: "Accepted", format: "number" },
  { key: "yieldRate", label: "Yield Rate", format: "percentage" },
  { key: "top100YieldRate", label: "Top 100 Yield Rate", format: "percentage" },
];

function formatValue(value: number | null, format?: "number" | "percentage"): string {
  if (value == null) return "—";
  if (format === "percentage") return `${value}%`;
  return value.toLocaleString();
}

export function GraduateHistoricalView({ data }: GraduateHistoricalViewProps) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-border-primary">
            <th className="px-4 py-3 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium">
              Metric
            </th>
            {data.map((year) => (
              <th
                key={year.academicYear}
                className="px-4 py-3 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium text-right"
              >
                {year.academicYear}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.key} className="border-b border-border-primary last:border-b-0">
              <td className="px-4 py-3 font-mono text-[14px] text-text-secondary">
                {row.label}
              </td>
              {data.map((year) => {
                const val = year[row.key] as number | null;
                const isNull = val == null;
                return (
                  <td
                    key={year.academicYear}
                    className={`px-4 py-3 font-mono text-[14px] text-right ${
                      isNull ? "text-text-muted italic" : "text-text-bright font-medium"
                    }`}
                  >
                    {formatValue(val, row.format)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
