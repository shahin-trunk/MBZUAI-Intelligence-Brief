"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

import type { EnrichmentSummary } from "@/lib/types/enrichment";

/* ─── Types ──────────────────────────────────────────────────────────── */

interface EnrichmentChartsProps {
  history: Array<{ date: string; summary: EnrichmentSummary }>;
}

/* ─── Helpers ────────────────────────────────────────────────────────── */

function shortDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}

const AXIS_STYLE = {
  fontSize: 10,
  fontFamily: "var(--font-mono)",
  fill: "var(--text-muted)",
};

const GRID_STROKE = "var(--border-card)";

function DarkTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-2 shadow-lg">
      <p className="font-mono text-[12px] text-text-muted">{label}</p>
      {payload.map((entry) => (
        <p
          key={entry.name}
          className="font-mono text-xs"
          style={{ color: entry.color }}
        >
          {entry.name}: {entry.value.toLocaleString()}
        </p>
      ))}
    </div>
  );
}

/* ─── Enrichment Rate Chart ──────────────────────────────────────────── */

function EnrichmentRateChart({
  history,
}: {
  history: EnrichmentChartsProps["history"];
}) {
  const data = history.map((h) => ({
    date: shortDate(h.date),
    total: h.summary.total_items,
    enriched: h.summary.enriched_successfully,
    thin: h.summary.thin_items,
  }));

  return (
    <div>
      <h4 className="mb-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
        Enrichment Rate Over Time
      </h4>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
          <XAxis dataKey="date" tick={AXIS_STYLE} tickLine={false} />
          <YAxis tick={AXIS_STYLE} tickLine={false} width={32} />
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <Tooltip content={<DarkTooltip /> as any} />
          <Area
            type="monotone"
            dataKey="total"
            name="Total Items"
            stroke="var(--text-muted)"
            fill="var(--text-muted)"
            fillOpacity={0.15}
            strokeWidth={1.5}
          />
          <Area
            type="monotone"
            dataKey="thin"
            name="Thin Items"
            stroke="#EAB308"
            fill="#EAB308"
            fillOpacity={0.15}
            strokeWidth={1.5}
          />
          <Area
            type="monotone"
            dataKey="enriched"
            name="Enriched OK"
            stroke="#22C55E"
            fill="#22C55E"
            fillOpacity={0.2}
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── Token Usage Chart ──────────────────────────────────────────────── */

function TokenUsageChart({
  history,
}: {
  history: EnrichmentChartsProps["history"];
}) {
  const data = history.map((h) => ({
    date: shortDate(h.date),
    input: h.summary.total_tokens_input,
    output: h.summary.total_tokens_output,
  }));

  return (
    <div>
      <h4 className="mb-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
        Token Usage Over Time
      </h4>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
          <XAxis dataKey="date" tick={AXIS_STYLE} tickLine={false} />
          <YAxis tick={AXIS_STYLE} tickLine={false} width={40} />
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <Tooltip content={<DarkTooltip /> as any} />
          <Line
            type="monotone"
            dataKey="input"
            name="Input Tokens"
            stroke="#3B82F6"
            strokeWidth={1.5}
            dot={{ r: 2, fill: "#3B82F6" }}
          />
          <Line
            type="monotone"
            dataKey="output"
            name="Output Tokens"
            stroke="#8B5CF6"
            strokeWidth={1.5}
            dot={{ r: 2, fill: "#8B5CF6" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── Content Growth Chart ───────────────────────────────────────────── */

function ContentGrowthChart({
  history,
}: {
  history: EnrichmentChartsProps["history"];
}) {
  const data = history.map((h) => ({
    date: shortDate(h.date),
    original: h.summary.avg_original_word_count,
    enriched: h.summary.avg_enriched_word_count,
  }));

  return (
    <div>
      <h4 className="mb-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
        Avg Content Growth (words)
      </h4>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
          <XAxis dataKey="date" tick={AXIS_STYLE} tickLine={false} />
          <YAxis tick={AXIS_STYLE} tickLine={false} width={40} />
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <Tooltip content={<DarkTooltip /> as any} />
          <Bar
            dataKey="original"
            name="Avg Original"
            fill="var(--text-muted)"
            fillOpacity={0.6}
            radius={[2, 2, 0, 0]}
          />
          <Bar
            dataKey="enriched"
            name="Avg Enriched"
            fill="#3B82F6"
            fillOpacity={0.6}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── Main Export ─────────────────────────────────────────────────────── */

export default function EnrichmentCharts({ history }: EnrichmentChartsProps) {
  if (!history || history.length === 0) {
    return (
      <p className="font-mono text-xs text-text-muted">
        No enrichment history to chart.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <EnrichmentRateChart history={history} />
      <TokenUsageChart history={history} />
      <ContentGrowthChart history={history} />
    </div>
  );
}
