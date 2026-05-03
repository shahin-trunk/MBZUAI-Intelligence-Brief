"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import type { AdminPipelineRun } from "@/lib/types/admin";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

/* ─── Dynamic import for Recharts (SSR disabled) ─────────────────────── */

const PipelineCharts = dynamic(
  () => import("@/components/admin/PipelineCharts"),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

function ChartSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-[220px] skeleton-pulse rounded-sm" />
      <div className="h-[160px] skeleton-pulse rounded-sm" />
      <div className="h-[180px] skeleton-pulse rounded-sm" />
    </div>
  );
}

/* ─── Range options ──────────────────────────────────────────────────── */

const RANGE_OPTIONS = [
  { label: "7d", value: "7" },
  { label: "14d", value: "14" },
  { label: "30d", value: "30" },
  { label: "All", value: "all" },
];

/* ─── Helpers ────────────────────────────────────────────────────────── */

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/* ─── Component ──────────────────────────────────────────────────────── */

export default function PipelineHistoryPage() {
  const router = useRouter();
  const [range, setRange] = useState("30");
  const [runs, setRuns] = useState<AdminPipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = useCallback(async (rangeVal: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/pipeline?range=${rangeVal}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setRuns(json.runs ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns(range);
  }, [range, fetchRuns]);

  return (
    <div className="space-y-6">
      {/* Page title */}
      <h1 className="font-serif text-[28px] text-text-bright">Pipeline History</h1>

      {/* ── Date Range Selector ────────────────────────────────────── */}
      <div className="flex items-center gap-1">
        {RANGE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setRange(opt.value)}
            className={cn(
              "px-3 py-1.5 rounded-sm font-mono text-[13px] transition-colors",
              range === opt.value
                ? "bg-accent-primary text-white"
                : "bg-bg-secondary text-text-muted hover:text-text-primary hover:bg-bg-tertiary border border-border-primary"
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* ── Loading / Error ────────────────────────────────────────── */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-text-muted">Loading...</p>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-accent-danger">Error: {error}</p>
        </div>
      )}

      {/* ── Charts ─────────────────────────────────────────────────── */}
      {!loading && !error && (
        <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
          <PipelineCharts runs={runs} />
        </div>
      )}

      {/* ── Run Table ──────────────────────────────────────────────── */}
      {!loading && !error && runs.length > 0 && (
        <div className="rounded-sm border border-border-primary bg-bg-secondary">
          <div className="border-b border-border-primary px-4 py-2.5">
            <h3 className="font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
              Run History
            </h3>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-primary text-left">
                <th className="px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Date
                </th>
                <th className="px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted text-right">
                  Items
                </th>
                <th className="px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted text-right">
                  Duration
                </th>
                <th className="px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted text-center">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  onClick={() =>
                    router.push(`/admin/pipeline/${run.run_date}`)
                  }
                  className="border-b border-border-primary/50 last:border-0 cursor-pointer hover:bg-bg-tertiary/50 transition-colors"
                >
                  <td className="px-4 py-2.5 font-mono text-[13px] text-text-primary">
                    {formatDate(run.run_date)}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[13px] text-text-secondary text-right">
                    {run.items_in_final_brief ?? 0} / {run.items_collected ?? 0}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[13px] text-text-secondary text-right">
                    {typeof run.duration_seconds === "number"
                      ? `${run.duration_seconds}s`
                      : "Unavailable"}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <StatusIcon status={run.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && runs.length === 0 && (
        <p className="text-center font-mono text-sm text-text-muted py-8">
          No pipeline runs found for the selected range.
        </p>
      )}
    </div>
  );
}

/* ─── Status Icon ────────────────────────────────────────────────────── */

function StatusIcon({ status }: { status: string }) {
  if (status === "success") {
    return <CheckCircle2 className="inline h-3.5 w-3.5 text-accent-success" />;
  }
  if (status === "partial") {
    return <AlertTriangle className="inline h-3.5 w-3.5 text-accent-warning" />;
  }
  return <XCircle className="inline h-3.5 w-3.5 text-accent-danger" />;
}
