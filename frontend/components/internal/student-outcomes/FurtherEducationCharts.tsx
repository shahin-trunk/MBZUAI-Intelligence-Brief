"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

interface ProgramCount {
  program: string;
  count: number;
}

interface DestinationCount {
  institution: string;
  count: number;
}

interface FurtherEducationChartsProps {
  byProgram: ProgramCount[];
  destinations: DestinationCount[];
}

const CHART_BLUE = "#3B82F6";
const GRID_COLOR = "var(--border-primary)";
const TICK_COLOR = "var(--text-muted)";
const LABEL_COLOR = "var(--text-secondary)";

export function FurtherEducationCharts({
  byProgram,
  destinations,
}: FurtherEducationChartsProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Further Education by Program Area */}
      <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
          Further Education by Program Area
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart
            data={byProgram}
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
              tick={{
                fill: TICK_COLOR,
                fontSize: 11,
                fontFamily: "monospace",
              }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="program"
              tick={{
                fill: LABEL_COLOR,
                fontSize: 11,
                fontFamily: "monospace",
              }}
              width={120}
              axisLine={false}
              tickLine={false}
            />
            <Bar
              dataKey="count"
              fill={CHART_BLUE}
              radius={[0, 2, 2, 0]}
              barSize={16}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Top Graduate Study Destinations */}
      <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
          Top Graduate Study Destinations
        </p>
        <ResponsiveContainer width="100%" height={340}>
          <BarChart
            data={destinations}
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
              tick={{
                fill: TICK_COLOR,
                fontSize: 11,
                fontFamily: "monospace",
              }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="institution"
              tick={{
                fill: LABEL_COLOR,
                fontSize: 11,
                fontFamily: "monospace",
              }}
              width={150}
              axisLine={false}
              tickLine={false}
            />
            <Bar
              dataKey="count"
              fill={CHART_BLUE}
              radius={[0, 2, 2, 0]}
              barSize={16}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
