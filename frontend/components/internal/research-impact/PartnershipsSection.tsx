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
import { PartnershipModal } from "./PartnershipModal";
import type {
  EvidenceMetric,
  MOUStatus,
  EnrichedPartnership,
} from "@/lib/types/internal-intelligence";

interface PartnershipsSectionProps {
  metrics: EvidenceMetric[];
  mouStatus: MOUStatus[];
  enrichedPartners: EnrichedPartnership[];
  note: string;
}

const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

const STATUS_COLORS: Record<string, string> = {
  Active: "#22C55E",
  "Signed — dormant": "var(--text-muted)",
  "Under negotiation": "#EAB308",
};

function PartnerStatusBadge({ status }: { status: string }) {
  let style: string;
  if (status === "Active") {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
  } else if (status.includes("dormant")) {
    style = "bg-bg-tertiary text-text-muted border-border-primary";
  } else {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
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

function TypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {type}
    </span>
  );
}

function formatActivityDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function PartnershipsSection({
  metrics,
  mouStatus,
  enrichedPartners,
  note,
}: PartnershipsSectionProps) {
  const [selected, setSelected] = useState<EnrichedPartnership | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="space-y-6">
      {/* Metrics — 3 per row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-[14px]">
        {metrics.map((metric) => (
          <MetricCard key={metric.id} metric={metric} />
        ))}
      </div>

      {/* MOU status chart */}
      <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
          MOU Status
        </p>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart
            data={mouStatus}
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
              width={150}
              axisLine={false}
              tickLine={false}
            />
            <Bar dataKey="count" radius={[0, 2, 2, 0]} barSize={14}>
              {mouStatus.map((entry) => (
                <Cell
                  key={entry.status}
                  fill={STATUS_COLORS[entry.status] || "var(--text-muted)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Partnership cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {enrichedPartners.map((partner) => (
          <button
            key={partner.id}
            type="button"
            onClick={() => {
              setSelected(partner);
              setModalOpen(true);
            }}
            className={cn(
              "rounded-sm border border-border-primary bg-bg-secondary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer",
              partner.status.includes("dormant") && "opacity-50"
            )}
          >
            <p className="font-serif text-base text-text-bright leading-snug">
              {partner.name}
            </p>

            <div className="flex items-center gap-2 mt-2">
              <TypeBadge type={partner.type} />
              <PartnerStatusBadge status={partner.status} />
            </div>

            <p className="font-sans text-[14px] text-text-muted mt-2 line-clamp-1">
              {partner.focusArea}
            </p>

            <p className="font-mono text-[12px] text-text-muted mt-1">
              Last activity: {formatActivityDate(partner.lastActivityDate)}
            </p>
          </button>
        ))}
      </div>

      {/* Data note */}
      <p className="font-mono text-[14px] leading-[1.6] text-text-muted italic">
        {note}
      </p>

      {/* Modal */}
      <PartnershipModal
        partner={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
