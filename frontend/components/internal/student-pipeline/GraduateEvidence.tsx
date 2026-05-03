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
  Tooltip,
} from "recharts";
import { cn } from "@/lib/utils";
import { MetricCard } from "@/components/internal/shared/MetricCard";
import { SectionHeader } from "@/components/internal/shared/SectionHeader";
import { StarStudentCards } from "./StarStudentCards";
import { GraduateHistoricalView } from "./GraduateHistoricalView";
import type {
  EvidenceMetric,
  ProgramDistribution,
  NationalityDistribution,
  FeederUniversity,
  HistoricalYearData,
  StarStudent,
} from "@/lib/types/internal-intelligence";

interface GraduateEvidenceProps {
  metrics: EvidenceMetric[];
  mscPrograms: ProgramDistribution[];
  phdPrograms: ProgramDistribution[];
  topNationalities: NationalityDistribution[];
  topFeederUniversities: FeederUniversity[];
  acceptedByProgram: ProgramDistribution[];
  acceptedByNationality: NationalityDistribution[];
  top100AcceptedByProgram: ProgramDistribution[];
  historicalComparison: HistoricalYearData[];
  starStudents: StarStudent[];
}

const CHART_BLUE = "#3B82F6";
const CHART_GOLD = "var(--sig-high)";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

type SubTab = "current" | "historical";
const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "current", label: "AY 2026-27" },
  { key: "historical", label: "Historical View" },
];

export function GraduateEvidence({
  metrics,
  mscPrograms,
  phdPrograms,
  topNationalities,
  topFeederUniversities,
  acceptedByProgram,
  acceptedByNationality,
  top100AcceptedByProgram,
  historicalComparison,
  starStudents,
}: GraduateEvidenceProps) {
  const [subTab, setSubTab] = useState<SubTab>("current");

  return (
    <div className="space-y-6">
      {/* Sub-tab toggle */}
      <div className="inline-flex bg-bg-tertiary border border-border-primary rounded-sm overflow-hidden">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setSubTab(tab.key)}
            className={cn(
              "px-4 py-2 font-mono text-[14px] transition-colors duration-150",
              subTab === tab.key
                ? "bg-accent-primary/15 text-accent-primary border-b-2 border-b-accent-primary"
                : "text-text-muted hover:text-text-secondary"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {subTab === "current" ? (
        <div className="space-y-6">
          {/* Metric cards — 7 items in 3-col grid, wraps to 3+3+1 */}
          <div className="grid grid-cols-3 gap-3">
            {metrics.map((metric) => (
              <MetricCard key={metric.id} metric={metric} />
            ))}
          </div>

          {/* Accepted by Program + Accepted by Nationality */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Accepted by Program — vertical bar */}
            <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
                Accepted Students by Program
              </p>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={acceptedByProgram}
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
                    dataKey="program"
                    tick={{ fill: LABEL_COLOR, fontSize: 10, fontFamily: "monospace" }}
                    width={220}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface-primary)",
                      border: "1px solid var(--border-primary)",
                      borderRadius: "4px",
                      color: "var(--text-primary)",
                      fontFamily: "monospace",
                      fontSize: "12px",
                    }}
                    labelStyle={{ color: "var(--text-secondary)" }}
                  />
                  <Bar dataKey="count" fill={CHART_BLUE} radius={[0, 2, 2, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Accepted by Nationality — horizontal bar, Emirati in gold */}
            <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
                Accepted Students by Nationality
              </p>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={acceptedByNationality}
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
                    width={100}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface-primary)",
                      border: "1px solid var(--border-primary)",
                      borderRadius: "4px",
                      color: "var(--text-primary)",
                      fontFamily: "monospace",
                      fontSize: "12px",
                    }}
                    labelStyle={{ color: "var(--text-secondary)" }}
                  />
                  <Bar dataKey="count" radius={[0, 2, 2, 0]} barSize={16}>
                    {acceptedByNationality.map((entry) => (
                      <Cell
                        key={entry.nationality}
                        fill={entry.nationality === "Emirati" ? CHART_GOLD : CHART_BLUE}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Application distribution — MSc + PhD */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* MSc Programs */}
            <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
                Applications by MSc Program
              </p>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={mscPrograms}
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
                    dataKey="program"
                    tick={{ fill: LABEL_COLOR, fontSize: 10, fontFamily: "monospace" }}
                    width={220}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Bar dataKey="count" fill={CHART_BLUE} radius={[0, 2, 2, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* PhD Programs */}
            <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
                Applications by PhD Program
              </p>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={phdPrograms}
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
                    dataKey="program"
                    tick={{ fill: LABEL_COLOR, fontSize: 10, fontFamily: "monospace" }}
                    width={220}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Bar dataKey="count" fill={CHART_BLUE} radius={[0, 2, 2, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Feeder universities + Applicant Nationalities */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Feeder universities */}
            <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
                Top Feeder Universities (Top 100 Institutions)
              </p>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={topFeederUniversities}
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
                    dataKey="university"
                    tick={{ fill: LABEL_COLOR, fontSize: 10, fontFamily: "monospace" }}
                    width={200}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Bar dataKey="count" fill={CHART_BLUE} radius={[0, 2, 2, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Applicant Nationalities (Top 100) */}
            <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
                Applicant Nationalities (Top 100 Institutions)
              </p>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={topNationalities}
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
                    {topNationalities.map((entry) => (
                      <Cell
                        key={entry.nationality}
                        fill={entry.nationality === "Emirati" ? CHART_GOLD : CHART_BLUE}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Top 100 Accepted by Program */}
          <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
              Top 100 Institution — Accepted by Program
            </p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={top100AcceptedByProgram}
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
                  dataKey="program"
                  tick={{ fill: LABEL_COLOR, fontSize: 10, fontFamily: "monospace" }}
                  width={220}
                  axisLine={false}
                  tickLine={false}
                />
                <Bar dataKey="count" fill={CHART_GOLD} radius={[0, 2, 2, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Notable Applicants */}
          <div>
            <SectionHeader title="Notable Applicants" />
            <StarStudentCards students={starStudents} />
          </div>
        </div>
      ) : (
        <GraduateHistoricalView data={historicalComparison} />
      )}
    </div>
  );
}
