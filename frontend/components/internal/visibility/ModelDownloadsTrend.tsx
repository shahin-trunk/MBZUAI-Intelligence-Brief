"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface TrendPoint {
  month: string;
  downloads: number;
}

interface ModelDownloadsTrendProps {
  k2thinkTrend: TrendPoint[];
  jaisTrend: TrendPoint[];
}

const CHART_GOLD = "var(--sig-high)";
const CHART_BLUE = "#3B82F6";
const GRID_COLOR = "var(--border-card)";
const TICK_COLOR = "var(--text-muted)";

const TOOLTIP_STYLE = {
  backgroundColor: "var(--surface-elevated)",
  border: "1px solid var(--border-primary)",
  borderRadius: "4px",
  fontFamily: "monospace",
  fontSize: "11px",
};

function TrendChart({
  title,
  data,
  color,
}: {
  title: string;
  data: TrendPoint[];
  color: string;
}) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
          {title}
        </p>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: 10 }}>
          <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
          <XAxis
            dataKey="month"
            tick={{ fill: TICK_COLOR, fontSize: 9, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: string) => v.replace("20", "'")}
          />
          <YAxis
            tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) =>
              v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)
            }
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={{ color: "var(--text-secondary)" }}
            itemStyle={{ color: "var(--text-primary)" }}
            formatter={(value) =>
              typeof value === "number" ? value.toLocaleString("en-US") : String(value)
            }
          />
          <Bar
            dataKey="downloads"
            name="Downloads"
            fill={color}
            fillOpacity={0.85}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ModelDownloadsTrend({ k2thinkTrend, jaisTrend }: ModelDownloadsTrendProps) {
  return (
    <div className="space-y-2">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
        Total Downloads Since Release
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TrendChart title="K2Think" data={k2thinkTrend} color={CHART_GOLD} />
        <TrendChart title="JAIS" data={jaisTrend} color={CHART_BLUE} />
      </div>
    </div>
  );
}
