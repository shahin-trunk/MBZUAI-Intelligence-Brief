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
import type { IFMDailyUserPoint } from "@/lib/types/internal-intelligence";

interface IFMDailyUsersTrendProps {
  data: IFMDailyUserPoint[];
}

const CHART_GOLD = "var(--sig-high)";
const GRID_COLOR = "var(--border-card)";
const TICK_COLOR = "var(--text-muted)";

function formatYAxis(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return String(value);
}

export function IFMDailyUsersTrend({ data }: IFMDailyUsersTrendProps) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
        Daily Users Trend &mdash; K2 Think
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatYAxis}
            width={45}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--surface-elevated)",
              border: "1px solid var(--border-primary)",
              borderRadius: "4px",
              fontFamily: "monospace",
              fontSize: "11px",
            }}
            labelStyle={{ color: TICK_COLOR }}
            itemStyle={{ color: CHART_GOLD }}
            formatter={(value) => [Number(value).toLocaleString("en-US"), "Users"]}
          />
          <Line
            type="monotone"
            dataKey="users"
            stroke={CHART_GOLD}
            strokeWidth={2}
            dot={{ fill: CHART_GOLD, r: 2 }}
            activeDot={{ r: 4, fill: CHART_GOLD }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
