"use client";

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
import { StarStudentCards } from "./StarStudentCards";
import type {
  EvidenceMetric,
  NationalityDistribution,
  DiversityTarget,
  TrackDistribution,
  StarStudent,
  CompetingOfferSummary,
} from "@/lib/types/internal-intelligence";

interface UndergraduateEvidenceProps {
  metrics: EvidenceMetric[];
  acceptedNationalities: NationalityDistribution[];
  diversityTargets: DiversityTarget[];
  acceptedByTrack: TrackDistribution[];
  keyAwards: string[];
  competingOffersSummary: CompetingOfferSummary[];
  starStudents: StarStudent[];
}

const CHART_BLUE = "#3B82F6";
const CHART_GOLD = "var(--sig-high)";
const CHART_GREEN = "#22C55E";
const CHART_RED = "#EF4444";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

export function UndergraduateEvidence({
  metrics,
  acceptedNationalities,
  diversityTargets,
  acceptedByTrack,
  keyAwards,
  competingOffersSummary,
  starStudents,
}: UndergraduateEvidenceProps) {
  return (
    <div className="space-y-6">
      {/* Metric cards — 6 items in 3-col grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-[14px]">
        {metrics.map((metric) => (
          <MetricCard key={metric.id} metric={metric} />
        ))}
      </div>

      {/* Accepted Nationalities + Accepted by Track */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Accepted Student Nationalities */}
        <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
            Accepted Student Nationalities
          </p>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart
              data={acceptedNationalities}
              layout="vertical"
              margin={{ top: 0, right: 30, bottom: 0, left: 0 }}
            >
              <CartesianGrid stroke={GRID_COLOR} horizontal={false} strokeDasharray="3 3" />
              <XAxis
                type="number"
                tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="nationality"
                tick={{ fill: LABEL_COLOR, fontSize: 11, fontFamily: "monospace" }}
                width={90}
                axisLine={false}
                tickLine={false}
              />
              <Bar dataKey="count" radius={[0, 2, 2, 0]} barSize={16}>
                {acceptedNationalities.map((entry) => (
                  <Cell
                    key={entry.nationality}
                    fill={entry.nationality === "Emirati" ? CHART_GOLD : CHART_BLUE}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Accepted Students by Track */}
        <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
            Accepted Students by Track
          </p>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart
              data={acceptedByTrack}
              layout="vertical"
              margin={{ top: 0, right: 30, bottom: 0, left: 0 }}
            >
              <CartesianGrid stroke={GRID_COLOR} horizontal={false} strokeDasharray="3 3" />
              <XAxis
                type="number"
                tick={{ fill: TICK_COLOR, fontSize: 11, fontFamily: "monospace" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="track"
                tick={{ fill: LABEL_COLOR, fontSize: 11, fontFamily: "monospace" }}
                width={100}
                axisLine={false}
                tickLine={false}
              />
              <Bar dataKey="count" fill={CHART_BLUE} radius={[0, 2, 2, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Diversity Targets — 3 vertical mini-charts */}
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
          Diversity Targets vs. Actual
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {diversityTargets.map((dt) => {
            const isOnTrack = dt.status === "on-track";
            const barColor = isOnTrack ? CHART_GREEN : CHART_RED;
            const chartData = [
              { label: "Target", value: dt.target },
              { label: "Actual", value: dt.actual },
            ];
            return (
              <div
                key={dt.dimension}
                className="bg-bg-tertiary rounded-sm border border-border-primary p-4 flex flex-col items-center"
              >
                <p className="font-mono text-[14px] text-text-secondary font-medium mb-1">
                  {dt.dimension}
                </p>
                <span
                  className="font-mono text-[12px] px-2 py-0.5 rounded-full mb-3"
                  style={{
                    color: isOnTrack ? CHART_GREEN : CHART_RED,
                    backgroundColor: isOnTrack ? `${CHART_GREEN}15` : `${CHART_RED}15`,
                  }}
                >
                  {isOnTrack ? "On track" : "Off track"}
                </span>
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 5, left: 10 }}>
                    <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, Math.max(dt.target, dt.actual) + 10]}
                      tick={{ fill: TICK_COLOR, fontSize: 10, fontFamily: "monospace" }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: number) => `${v}%`}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={32}>
                      <Cell fill={`${CHART_BLUE}30`} stroke={CHART_BLUE} strokeDasharray="4 4" strokeWidth={1} />
                      <Cell fill={barColor} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="flex items-center gap-4 mt-1">
                  <span className="font-mono text-[13px] text-text-muted">
                    Target: <span className="text-text-secondary">{dt.target}%</span>
                  </span>
                  <span className="font-mono text-[13px] text-text-muted">
                    Actual: <span className="text-text-secondary font-medium">{dt.actual}%</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Key Awards & Achievements */}
      <div>
        <SectionHeader title="Key Awards & Achievements" />
        <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
          <ul className="space-y-2">
            {keyAwards.map((award) => (
              <li key={award} className="flex items-start gap-2">
                <svg
                  className="w-4 h-4 mt-0.5 shrink-0"
                  style={{ color: CHART_GREEN }}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <span className="font-mono text-[14px] text-text-secondary">{award}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Competing Offers Summary */}
      <div>
        <SectionHeader title="Competing Offers" />
        <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
          <div className="space-y-2">
            {competingOffersSummary.map((entry) => {
              const isWon = entry.outcome.startsWith("Won");
              return (
                <div
                  key={entry.institution}
                  className="flex items-center justify-between py-1.5 border-b border-border-primary last:border-b-0"
                >
                  <span className="font-mono text-[14px] text-text-secondary font-medium">
                    {entry.institution}
                  </span>
                  <span
                    className="font-mono text-[13px]"
                    style={{ color: isWon ? CHART_GREEN : CHART_RED }}
                  >
                    {entry.outcome}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Notable Applicants */}
      <div>
        <SectionHeader title="Notable Applicants" />
        <StarStudentCards students={starStudents} />
      </div>
    </div>
  );
}
