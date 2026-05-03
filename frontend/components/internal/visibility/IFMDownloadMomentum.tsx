"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  LabelList,
} from "recharts";
import type { IFMModelDownload } from "@/lib/types/internal-intelligence";

interface IFMDownloadMomentumProps {
  data: IFMModelDownload[];
}

const CHART_GOLD = "var(--sig-high)";
const TICK_COLOR = "var(--text-muted)";

function formatNumber(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return String(value);
}

export function IFMDownloadMomentum({ data }: IFMDownloadMomentumProps) {
  const sorted = [...data].sort((a, b) => b.downloads - a.downloads);

  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
        Recent Download Momentum by Model
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart
          layout="vertical"
          data={sorted}
          margin={{ top: 0, right: 60, left: 0, bottom: 0 }}
        >
          <XAxis
            type="number"
            tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatNumber}
          />
          <YAxis
            type="category"
            dataKey="model"
            tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={false}
            width={120}
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
            formatter={(value) => [Number(value).toLocaleString("en-US"), "Downloads"]}
          />
          <Bar
            dataKey="downloads"
            fill={CHART_GOLD}
            barSize={24}
            radius={[0, 3, 3, 0]}
          >
            <LabelList
              dataKey="downloads"
              position="right"
              formatter={(value) => Number(value).toLocaleString("en-US")}
              style={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
