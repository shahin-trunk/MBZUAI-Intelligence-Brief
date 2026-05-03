"use client";

interface PipelineMetric {
  metric: string;
  currentFacultyValue: number;
  pipelineCandidateValue: number;
  currentFacultyMedian?: number;
  pipelineCandidateMedian?: number;
  format?: "number" | "percentage";
}

interface FacultyChartsProps {
  pipelineQualityComparison: {
    label: string;
    metrics: PipelineMetric[];
  };
  growthByDivision: { division: string; arrivals: number; departures: number; totalFaculty: number }[];
}

const COLOR_GREEN = "#22C55E";
const COLOR_RED = "#EF4444";

export function FacultyCharts({
  pipelineQualityComparison,
  growthByDivision,
}: FacultyChartsProps) {
  const growthData = [...growthByDivision].sort((a, b) => {
    // Pin Undergraduate Division last
    if (a.division === "Undergraduate Division") return 1;
    if (b.division === "Undergraduate Division") return -1;
    return (b.arrivals - b.departures) - (a.arrivals - a.departures);
  });
  const maxBar = Math.max(...growthData.map((e) => Math.max(e.arrivals, e.departures)), 1);

  return (
    <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-stretch">
      {/* Pipeline quality comparison */}
      <div className="flex h-full flex-col rounded-sm border border-border-primary bg-bg-tertiary p-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
          {pipelineQualityComparison.label}
        </p>
        <div className="flex flex-1 flex-col justify-evenly gap-3">
          {pipelineQualityComparison.metrics.map((entry) => {
            const delta = entry.pipelineCandidateValue - entry.currentFacultyValue;
            const formattedDelta =
              entry.format === "percentage"
                ? `+${delta} pts`
                : `+${delta.toLocaleString()}`;
            const hasMedian =
              entry.currentFacultyMedian != null && entry.pipelineCandidateMedian != null;

            return (
              <div
                key={entry.metric}
                className="rounded-sm border border-border-primary bg-bg-secondary px-4 py-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
                    {entry.metric}
                  </p>
                  <span className="font-mono text-[12px] text-sig-high">
                    Pipeline {formattedDelta}
                  </span>
                </div>
                {/* Average row */}
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-sm border border-border-primary bg-bg-tertiary px-3 py-3">
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Current Faculty Avg
                    </p>
                    <p className="mt-1 font-mono text-xl font-bold text-[#93C5FD]">
                      {formatMetricValue(entry.currentFacultyValue, entry.format)}
                    </p>
                  </div>
                  <div className="rounded-sm border border-border-primary bg-bg-tertiary px-3 py-3">
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Pipeline Candidates Avg
                    </p>
                    <p className="mt-1 font-mono text-xl font-bold text-[#FCD34D]">
                      {formatMetricValue(entry.pipelineCandidateValue, entry.format)}
                    </p>
                  </div>
                </div>
                {/* Median row (if present) */}
                {hasMedian && (
                  <div className="mt-2 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-sm border border-border-primary bg-bg-tertiary px-3 py-2">
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                        Current Faculty Median
                      </p>
                      <p className="mt-1 font-mono text-lg font-semibold text-[#93C5FD]">
                        {formatMetricValue(entry.currentFacultyMedian!, entry.format)}
                      </p>
                    </div>
                    <div className="rounded-sm border border-border-primary bg-bg-tertiary px-3 py-2">
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                        Pipeline Candidates Median
                      </p>
                      <p className="mt-1 font-mono text-lg font-semibold text-[#FCD34D]">
                        {formatMetricValue(entry.pipelineCandidateMedian!, entry.format)}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Faculty change by division — arrivals & departures */}
      <div className="flex h-full flex-col rounded-sm border border-border-primary bg-bg-tertiary p-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
          Faculty Change by Division — Trailing 6 Months
        </p>

        {/* Legend */}
        <div className="mb-3 flex items-center gap-4">
          <span className="flex items-center gap-1.5 font-mono text-[12px] text-text-muted">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: COLOR_GREEN }} />
            Arrivals
          </span>
          <span className="flex items-center gap-1.5 font-mono text-[12px] text-text-muted">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: COLOR_RED }} />
            Departures
          </span>
        </div>

        <div className="flex flex-1 flex-col justify-evenly gap-4">
          {growthData.map((entry) => {
            const net = entry.arrivals - entry.departures;
            const label = formatDivisionTick(entry.division);
            const arrPct = (entry.arrivals / maxBar) * 100;
            const depPct = (entry.departures / maxBar) * 100;

            return (
              <div key={entry.division}>
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <span className="font-mono text-[13px] text-text-secondary">
                    {label}
                    <span className="ml-1.5 text-[12px] text-text-muted">
                      ({entry.totalFaculty} faculty)
                    </span>
                  </span>
                  <span className={`font-mono text-[14px] font-semibold tabular-nums shrink-0 ${net >= 0 ? "text-accent-success" : "text-accent-danger"}`}>
                    Net {net >= 0 ? "+" : ""}{net}
                  </span>
                </div>
                {/* Arrivals bar */}
                <div className="relative h-1.5 w-full rounded-full bg-bg-secondary">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{ width: `${Math.max(arrPct, 4)}%`, backgroundColor: COLOR_GREEN }}
                  />
                </div>
                <div className="flex items-center justify-between mt-0.5">
                  <span className="font-mono text-[12px] text-text-muted">+{entry.arrivals} joined</span>
                </div>
                {/* Departures bar */}
                <div className="relative mt-1 h-1.5 w-full rounded-full bg-bg-secondary">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{ width: `${entry.departures > 0 ? Math.max(depPct, 4) : 0}%`, backgroundColor: COLOR_RED }}
                  />
                </div>
                <div className="flex items-center justify-between mt-0.5">
                  <span className="font-mono text-[12px] text-text-muted">{entry.departures > 0 ? `−${entry.departures} left` : "No departures"}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function formatMetricValue(
  value: number,
  format: "number" | "percentage" | undefined
) {
  if (format === "percentage") {
    return `${value}%`;
  }
  return value.toLocaleString();
}

function formatDivisionTick(value: string) {
  return value
    .replace(" and ", " & ")
    .replace(", Social and ", ", Social & ");
}
