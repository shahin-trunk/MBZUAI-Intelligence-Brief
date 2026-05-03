"use client";

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { FundingTrendPoint } from "@/lib/types/internal-intelligence";

interface FundingTrendProps {
  data: FundingTrendPoint[];
}

const CHART_BLUE = "#3B82F6";
const CHART_GOLD = "var(--sig-high)";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";

export function FundingTrend({ data }: FundingTrendProps) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
        Funding Portfolio Trend
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart
          data={data}
          margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
        >
          <CartesianGrid
            stroke={GRID_COLOR}
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            dataKey="month"
            tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="left"
            tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            label={{
              value: "Projects",
              angle: -90,
              position: "insideLeft",
              style: { fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" },
            }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            label={{
              value: "AED (M)",
              angle: 90,
              position: "insideRight",
              style: { fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" },
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, fontFamily: "monospace" }}
            iconType="square"
            iconSize={10}
          />
          <Bar
            yAxisId="left"
            dataKey="projects"
            name="Projects"
            fill={CHART_BLUE}
            radius={[2, 2, 0, 0]}
            barSize={24}
            fillOpacity={0.7}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="totalValueM"
            name="Total Value (AED M)"
            stroke={CHART_GOLD}
            strokeWidth={2.5}
            dot={{ fill: CHART_GOLD, r: 4 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
