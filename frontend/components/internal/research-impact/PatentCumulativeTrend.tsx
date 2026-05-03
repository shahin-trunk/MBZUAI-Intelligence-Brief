"use client";

import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { PatentTrendPoint } from "@/lib/types/internal-intelligence";

interface PatentCumulativeTrendProps {
  data: PatentTrendPoint[];
}

const CHART_BLUE = "#3B82F6";
const CHART_GREEN = "#22C55E";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";

export function PatentCumulativeTrend({ data }: PatentCumulativeTrendProps) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
        Cumulative Patent Activity
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
            dataKey="quarter"
            tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            label={{
              value: "Patents",
              angle: -90,
              position: "insideLeft",
              style: { fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" },
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, fontFamily: "monospace" }}
            iconType="square"
            iconSize={10}
          />
          <Area
            type="monotone"
            dataKey="filed"
            name="Filed"
            fill={CHART_BLUE}
            fillOpacity={0.15}
            stroke={CHART_BLUE}
            strokeWidth={2}
          />
          <Line
            type="monotone"
            dataKey="granted"
            name="Granted"
            stroke={CHART_GREEN}
            strokeWidth={2.5}
            dot={{ fill: CHART_GREEN, r: 3 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
