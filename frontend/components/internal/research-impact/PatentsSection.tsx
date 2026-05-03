"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { cn } from "@/lib/utils";
import { MetricCard } from "@/components/internal/shared/MetricCard";
import { PatentModal } from "./PatentModal";
import { PatentCumulativeTrend } from "./PatentCumulativeTrend";
import type {
  EvidenceMetric,
  PatentStatusBreakdown,
  PatentTrendPoint,
  FlagshipPatent,
} from "@/lib/types/internal-intelligence";

interface PatentsSectionProps {
  metrics: EvidenceMetric[];
  statusBreakdown: PatentStatusBreakdown[];
  studentCoInventorshipNote: string;
  cumulativeTrend: PatentTrendPoint[];
  flagshipPatents: FlagshipPatent[];
}

const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

const STATUS_COLORS: Record<string, string> = {
  "Granted": "#22C55E",
  "Filed — under examination": "#3B82F6",
  "Filed — pending review": "var(--sig-high)",
};

function PatentStatusBadge({ status }: { status: string }) {
  let style: string;
  if (status.includes("under examination")) {
    style = "bg-accent-primary/15 text-accent-primary border-accent-primary/30";
  } else if (status.includes("pending review")) {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
  } else if (status.includes("Granted")) {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
  } else {
    style = "bg-bg-tertiary text-text-muted border-border-primary";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
        style
      )}
    >
      {status}
    </span>
  );
}

export function PatentsSection({
  metrics,
  statusBreakdown,
  studentCoInventorshipNote,
  cumulativeTrend,
  flagshipPatents,
}: PatentsSectionProps) {
  const [selected, setSelected] = useState<FlagshipPatent | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleClick(patent: FlagshipPatent) {
    setSelected(patent);
    setModalOpen(true);
  }

  return (
    <div className="space-y-6">
      {/* Metrics — 3 per row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-[14px]">
        {metrics.map((metric) => (
          <MetricCard key={metric.id} metric={metric} />
        ))}
      </div>

      {/* Status breakdown chart */}
      <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
          Patent Status Breakdown
        </p>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart
            data={statusBreakdown}
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
            />
            <YAxis
              type="category"
              dataKey="status"
              tick={{ fill: LABEL_COLOR, fontSize: 10, fontFamily: "monospace" }}
              width={190}
              axisLine={false}
              tickLine={false}
            />
            <Bar dataKey="count" radius={[0, 2, 2, 0]} barSize={16}>
              {statusBreakdown.map((entry) => (
                <Cell
                  key={entry.status}
                  fill={STATUS_COLORS[entry.status] || "#3B82F6"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {/* Student co-inventorship stat line */}
        <p className="font-mono text-[14px] leading-[1.6] text-text-muted mt-3 italic">
          {studentCoInventorshipNote}
        </p>
      </div>

      {/* Cumulative trend chart */}
      <PatentCumulativeTrend data={cumulativeTrend} />

      {/* Flagship patent cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {flagshipPatents.map((patent) => (
          <button
            key={patent.id}
            type="button"
            onClick={() => handleClick(patent)}
            className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
          >
            {/* Title */}
            <p className="font-serif text-base text-text-bright leading-snug line-clamp-2">
              {patent.title}
            </p>

            {/* Inventors */}
            <p className="mt-2 font-sans text-[14px] text-text-muted truncate">
              {patent.inventors[0]}
              {patent.inventors.length > 1
                ? ` + ${patent.inventors.length - 1} more`
                : ""}
            </p>

            {/* Status + Division + Date */}
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <PatentStatusBadge status={patent.status} />
              <span className="font-mono text-[12px] text-text-muted">
                {patent.division}
              </span>
            </div>

            <p className="mt-2 font-mono text-[12px] text-text-muted">
              Filed{" "}
              {new Date(patent.filingDate).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          </button>
        ))}
      </div>

      <PatentModal
        patent={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
