"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

import type { AdminPipelineRun } from "@/lib/types/admin";

/* ─── Types ──────────────────────────────────────────────────────────── */

interface PipelineChartsProps {
  runs: AdminPipelineRun[];
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
        <p key={entry.name} className="font-mono text-xs" style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}

/* ─── Items Collected vs Published ───────────────────────────────────── */

function ItemsChart({ runs }: { runs: AdminPipelineRun[] }) {
  const data = [...runs]
    .sort((a, b) => a.run_date.localeCompare(b.run_date))
    .map((r) => ({
      date: shortDate(r.run_date),
      collected: r.items_collected ?? 0,
      published: r.items_in_final_brief ?? 0,
    }));

  return (
    <div>
      <h4 className="mb-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
        Items Collected vs Published
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
            dataKey="collected"
            name="Collected"
            stroke="var(--text-muted)"
            fill="var(--text-muted)"
            fillOpacity={0.2}
            strokeWidth={1.5}
          />
          <Area
            type="monotone"
            dataKey="published"
            name="Published"
            stroke="#3B82F6"
            fill="#3B82F6"
            fillOpacity={0.2}
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── Source Health Heatmap (custom div grid, not Recharts) ──────────── */

function SourceHeatmap({ runs }: { runs: AdminPipelineRun[] }) {
  const sorted = [...runs].sort((a, b) =>
    a.run_date.localeCompare(b.run_date)
  );

  // Extract unique source names across all runs
  const sourceSet = new Set<string>();
  for (const r of sorted) {
    if (r.items_per_source && typeof r.items_per_source === "object") {
      for (const key of Object.keys(r.items_per_source)) {
        sourceSet.add(key);
      }
    }
  }
  const sources = [...sourceSet].sort();

  if (sources.length === 0 || sorted.length === 0) {
    return (
      <p className="font-mono text-xs text-text-muted">
        No source data available for heatmap.
      </p>
    );
  }

  return (
    <div>
      <h4 className="mb-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
        Source Health Heatmap
      </h4>
      <div className="overflow-x-auto">
        <div
          className="inline-grid gap-px"
          style={{
            gridTemplateColumns: `80px repeat(${sorted.length}, minmax(32px, 1fr))`,
          }}
        >
          {/* Header row: empty corner + dates */}
          <div />
          {sorted.map((r) => (
            <div
              key={r.run_date}
              className="text-center font-mono text-[11px] text-text-muted pb-1"
            >
              {shortDate(r.run_date)}
            </div>
          ))}

          {/* Source rows */}
          {sources.map((source) => (
            <div key={source} className="contents">
              <div className="flex items-center font-mono text-[12px] text-text-secondary uppercase pr-2 truncate">
                {source}
              </div>
              {sorted.map((r) => {
                const count =
                  r.items_per_source &&
                  typeof r.items_per_source === "object"
                    ? (r.items_per_source[source] ?? 0)
                    : 0;

                let bgClass = "bg-bg-tertiary";
                if (count >= 4) bgClass = "bg-accent-success/40";
                else if (count >= 1) bgClass = "bg-sig-medium/30";

                return (
                  <div
                    key={`${source}-${r.run_date}`}
                    className={`${bgClass} flex items-center justify-center rounded-[2px] h-6 min-w-[32px]`}
                  >
                    <span className="font-mono text-[12px] text-text-secondary">
                      {count}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Pipeline Duration Chart ────────────────────────────────────────── */

function DurationChart({ runs }: { runs: AdminPipelineRun[] }) {
  const data = [...runs]
    .sort((a, b) => a.run_date.localeCompare(b.run_date))
    .map((r) => ({
      date: shortDate(r.run_date),
      duration: r.duration_seconds ?? 0,
    }));

  return (
    <div>
      <h4 className="mb-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
        Pipeline Duration (seconds)
      </h4>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
          <XAxis dataKey="date" tick={AXIS_STYLE} tickLine={false} />
          <YAxis tick={AXIS_STYLE} tickLine={false} width={32} />
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <Tooltip content={<DarkTooltip /> as any} />
          <Line
            type="monotone"
            dataKey="duration"
            name="Duration (s)"
            stroke="#3B82F6"
            strokeWidth={1.5}
            dot={{ r: 2, fill: "#3B82F6" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── Main Export ─────────────────────────────────────────────────────── */

export default function PipelineCharts({ runs }: PipelineChartsProps) {
  if (!runs || runs.length === 0) {
    return (
      <p className="font-mono text-xs text-text-muted">
        No pipeline data to chart.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <ItemsChart runs={runs} />
      <SourceHeatmap runs={runs} />
      <DurationChart runs={runs} />
    </div>
  );
}
