"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  LabelList,
} from "recharts";
import type { MonthlyPublicationTrend } from "@/lib/types/internal-intelligence";

interface PublicationTrendProps {
  data: MonthlyPublicationTrend[];
}

const BRIGHT_GOLD = "var(--sig-high)";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";

/** Map a "Mon YYYY" string to a fiscal quarter label. */
function toQuarterKey(month: string): string {
  const MONTH_MAP: Record<string, number> = {
    Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6,
    Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12,
  };
  const [mon, year] = month.split(" ");
  const m = MONTH_MAP[mon] ?? 1;
  const q = Math.ceil(m / 3);
  return `Q${q} ${year}`;
}

function aggregateQuarterly(data: MonthlyPublicationTrend[]) {
  const map = new Map<string, number>();
  const order: string[] = [];

  for (const d of data) {
    const key = toQuarterKey(d.month);
    map.set(key, (map.get(key) ?? 0) + d.tier1);
    if (!order.includes(key)) order.push(key);
  }

  return order.map((quarter) => ({ quarter, tier1: map.get(quarter) ?? 0 }));
}

export function PublicationTrend({ data }: PublicationTrendProps) {
  const quarterly = aggregateQuarterly(data);

  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
        Tier 1 Publications — Quarterly
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={quarterly}
          margin={{ top: 24, right: 20, bottom: 5, left: 0 }}
        >
          <CartesianGrid
            stroke={GRID_COLOR}
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            dataKey="quarter"
            tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Bar dataKey="tier1" fill={BRIGHT_GOLD} radius={[3, 3, 0, 0]} barSize={56}>
            <LabelList
              dataKey="tier1"
              position="top"
              style={{
                fill: "var(--text-primary)",
                fontSize: 13,
                fontFamily: "monospace",
                fontWeight: 600,
              }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
