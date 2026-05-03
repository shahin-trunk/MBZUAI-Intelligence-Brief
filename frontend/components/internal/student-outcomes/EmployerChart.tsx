"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { OutcomesHiringOrg } from "@/lib/types/internal-intelligence";

interface EmployerChartProps {
  organizations: OutcomesHiringOrg[];
}

const CHART_BLUE = "#3B82F6";
const CHART_GOLD = "var(--sig-high)";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

export function EmployerChart({ organizations }: EmployerChartProps) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
        Top Hiring Organizations
      </p>
      <ResponsiveContainer width="100%" height={340}>
        <BarChart
          data={organizations}
          layout="vertical"
          margin={{ top: 0, right: 30, bottom: 0, left: 0 }}
        >
          <CartesianGrid
            stroke={GRID_COLOR}
            horizontal={false}
            strokeDasharray="3 3"
          />
          <XAxis
            type="number"
            tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="organization"
            tick={{ fill: LABEL_COLOR, fontSize: 11, fontFamily: "monospace" }}
            width={220}
            axisLine={false}
            tickLine={false}
          />
          <Bar dataKey="count" radius={[0, 2, 2, 0]} barSize={16}>
            {organizations.map((entry) => (
              <Cell
                key={entry.organization}
                fill={entry.uaeBased ? CHART_GOLD : CHART_BLUE}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {/* Legend */}
      <div className="flex items-center gap-4 mt-3">
        <div className="flex items-center gap-1.5">
          <div
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: CHART_GOLD }}
          />
          <span className="font-mono text-[12px] text-text-muted">
            UAE-based
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <div
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: CHART_BLUE }}
          />
          <span className="font-mono text-[12px] text-text-muted">
            International
          </span>
        </div>
      </div>
    </div>
  );
}
