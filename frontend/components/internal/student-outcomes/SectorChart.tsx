"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import type { EmploymentSector } from "@/lib/types/internal-intelligence";

interface SectorChartProps {
  data: EmploymentSector[];
}

const CHART_BLUE = "#3B82F6";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

export function SectorChart({ data }: SectorChartProps) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
        Employment by Sector
      </p>
      <ResponsiveContainer width="100%" height={200}>
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
            dataKey="sector"
            tick={{ fill: LABEL_COLOR, fontSize: 10, fontFamily: "monospace" }}
            width={170}
            axisLine={false}
            tickLine={false}
          />
          <Bar
            dataKey="percentage"
            fill={CHART_BLUE}
            radius={[0, 2, 2, 0]}
            barSize={16}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
