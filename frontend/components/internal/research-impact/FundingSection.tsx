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
import { MetricCard } from "@/components/internal/shared/MetricCard";
import { SectionHeader } from "@/components/internal/shared/SectionHeader";
import { FundingTrend } from "./FundingTrend";
import { GrantModal } from "./GrantModal";
import type {
  EvidenceMetric,
  FundingTrendPoint,
  FundingPartner,
  FlagshipGrant,
} from "@/lib/types/internal-intelligence";

interface FundingSectionProps {
  metrics: EvidenceMetric[];
  portfolioTrend: FundingTrendPoint[];
  keyPartners: FundingPartner[];
  flagshipGrants: FlagshipGrant[];
}

const CHART_BLUE = "#3B82F6";
const CHART_GOLD = "var(--sig-high)";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

// UAE government-linked partners to highlight
const UAE_GOV_PARTNERS = new Set([
  "ASPIRE (ATRC)",
  "ADNOC",
  "Mubadala",
  "Abu Dhabi Department of Health",
  "TII",
]);

export function FundingSection({
  metrics,
  portfolioTrend,
  keyPartners,
  flagshipGrants,
}: FundingSectionProps) {
  const [selected, setSelected] = useState<FlagshipGrant | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleClick(grant: FlagshipGrant) {
    setSelected(grant);
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

      {/* Portfolio trend */}
      <FundingTrend data={portfolioTrend} />

      {/* Key partners chart */}
      <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
          Funding by Partner (AED M)
        </p>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart
            data={keyPartners}
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
              dataKey="partner"
              tick={{ fill: LABEL_COLOR, fontSize: 10, fontFamily: "monospace" }}
              width={200}
              axisLine={false}
              tickLine={false}
            />
            <Bar dataKey="totalValueM" radius={[0, 2, 2, 0]} barSize={16}>
              {keyPartners.map((entry) => (
                <Cell
                  key={entry.partner}
                  fill={
                    UAE_GOV_PARTNERS.has(entry.partner)
                      ? CHART_GOLD
                      : CHART_BLUE
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {/* Legend */}
        <div className="flex items-center gap-4 mt-3">
          <div className="flex items-center gap-1.5">
            <div
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: CHART_GOLD }}
            />
            <span className="font-mono text-[12px] text-text-muted">
              UAE / Government-linked
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: CHART_BLUE }}
            />
            <span className="font-mono text-[12px] text-text-muted">
              International
            </span>
          </div>
        </div>
      </div>

      {/* Flagship grant cards */}
      <div>
        <SectionHeader title="Notable Grants" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
          {flagshipGrants.map((grant) => (
            <button
              key={grant.id}
              type="button"
              onClick={() => handleClick(grant)}
              className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
            >
              {/* Title */}
              <p className="font-serif text-base text-text-bright leading-snug line-clamp-2">
                {grant.title}
              </p>

              {/* Funder + Amount */}
              <div className="mt-2 flex items-center gap-3">
                <span className="font-mono text-[14px] text-text-secondary">
                  {grant.funder}
                </span>
                <span className="font-mono text-sm font-bold text-sig-high">
                  {grant.amount}
                </span>
              </div>

              {/* PI + Duration */}
              <p className="mt-2 font-sans text-[14px] text-text-muted">
                PI: {grant.pi}
              </p>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="font-mono text-[12px] text-text-muted">
                  {grant.division}
                </span>
                <span className="font-mono text-[12px] text-text-muted">
                  {grant.duration}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      <GrantModal
        grant={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
