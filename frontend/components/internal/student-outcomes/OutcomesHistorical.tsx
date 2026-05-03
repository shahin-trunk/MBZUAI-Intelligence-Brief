"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { OutcomesCohort } from "@/lib/types/internal-intelligence";

interface OutcomesHistoricalProps {
  cohorts: OutcomesCohort[];
}

const CHART_BLUE = "#3B82F6";
const CHART_GOLD = "var(--sig-high)";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

type RowConfig = {
  key: keyof OutcomesCohort;
  label: string;
  format?: "number" | "percentage" | "months" | "text";
};

const TABLE_ROWS: RowConfig[] = [
  { key: "graduates", label: "Graduates", format: "number" },
  { key: "employmentRate", label: "Employment Rate", format: "percentage" },
  { key: "uaeRetention", label: "UAE Retention", format: "percentage" },
  { key: "topEmployer", label: "Top Employer", format: "text" },
  { key: "pctAITech", label: "% AI/Tech Roles", format: "percentage" },
];

function formatCell(
  value: string | number | null | undefined,
  format?: string
): string {
  if (value == null) return "—";
  if (format === "percentage") return `${value}%`;
  if (format === "months") return `${value} mo`;
  if (format === "number" && typeof value === "number")
    return value.toLocaleString();
  return String(value);
}

const TOOLTIP_STYLE = {
  backgroundColor: "var(--surface-primary)",
  border: "1px solid var(--border-primary)",
  borderRadius: "4px",
  color: "var(--text-primary)",
  fontFamily: "monospace",
  fontSize: "12px",
};

function TrendChart({
  title,
  data,
  color,
  suffix,
}: {
  title: string;
  data: { cohort: string; value: number }[];
  color: string;
  suffix?: string;
}) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
        {title}
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
          <XAxis
            dataKey="cohort"
            tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => (suffix ? `${v}${suffix}` : String(v))}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={{ color: LABEL_COLOR }}
            formatter={(v) => [suffix ? `${v}${suffix}` : v, title]}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={{ fill: color, r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function OutcomesHistorical({ cohorts }: OutcomesHistoricalProps) {
  // Filter to cohorts with valid data for trend lines
  const validCohorts = cohorts.filter((c) => c.employmentRate != null);

  const employmentTrend = validCohorts.map((c) => ({
    cohort: c.cohort.replace("Class of ", "'"),
    value: c.employmentRate as number,
  }));

  const retentionTrend = validCohorts.map((c) => ({
    cohort: c.cohort.replace("Class of ", "'"),
    value: c.uaeRetention as number,
  }));

  // Find pending cohort note
  const pendingCohort = cohorts.find((c) => c.note);

  return (
    <div className="space-y-6">
      {/* Comparison table */}
      <div className="bg-bg-tertiary rounded-sm border border-border-primary overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-border-primary">
              <th className="px-4 py-3 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium">
                Metric
              </th>
              {cohorts.map((c) => (
                <th
                  key={c.cohort}
                  className="px-4 py-3 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium text-right"
                >
                  {c.cohort}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {TABLE_ROWS.map((row) => (
              <tr
                key={row.key}
                className="border-b border-border-primary last:border-b-0"
              >
                <td className="px-4 py-3 font-mono text-[14px] text-text-secondary">
                  {row.label}
                </td>
                {cohorts.map((c) => {
                  const val = c[row.key] as string | number | null;
                  const isNull = val == null;
                  return (
                    <td
                      key={c.cohort}
                      className={`px-4 py-3 font-mono text-[14px] text-right ${
                        isNull
                          ? "text-text-muted italic"
                          : "text-text-bright font-medium"
                      }`}
                    >
                      {formatCell(val, row.format)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pending cohort note */}
      {pendingCohort?.note && (
        <p className="font-mono text-[14px] leading-[1.6] text-text-muted italic">
          {pendingCohort.cohort}: {pendingCohort.note}
        </p>
      )}

      {/* Trend line charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrendChart
          title="Employment Rate"
          data={employmentTrend}
          color={CHART_BLUE}
          suffix="%"
        />
        <TrendChart
          title="UAE Retention"
          data={retentionTrend}
          color={CHART_GOLD}
          suffix="%"
        />
      </div>
    </div>
  );
}
