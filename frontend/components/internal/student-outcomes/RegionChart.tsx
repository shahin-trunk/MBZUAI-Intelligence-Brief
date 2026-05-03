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
import type { EmploymentRegion } from "@/lib/types/internal-intelligence";

interface RegionChartProps {
  data: EmploymentRegion[];
}

const CHART_BLUE = "#3B82F6";
const CHART_GOLD = "var(--sig-high)";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

export function RegionChart({ data }: RegionChartProps) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
        Employment by Region
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          data={data}
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
            tickFormatter={(v: number) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="region"
            tick={{ fill: LABEL_COLOR, fontSize: 11, fontFamily: "monospace" }}
            width={110}
            axisLine={false}
            tickLine={false}
          />
          <Bar dataKey="percentage" radius={[0, 2, 2, 0]} barSize={16}>
            {data.map((entry) => (
              <Cell
                key={entry.region}
                fill={entry.region === "UAE" ? CHART_GOLD : CHART_BLUE}
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
          <span className="font-mono text-[12px] text-text-muted">UAE</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: CHART_BLUE }}
          />
          <span className="font-mono text-[12px] text-text-muted">
            Other regions
          </span>
        </div>
      </div>
    </div>
  );
}
