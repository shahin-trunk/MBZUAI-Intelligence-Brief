"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { PipelineFunnel } from "@/components/admin/PipelineFunnel";
import type { AdminPipelineRun } from "@/lib/types/admin";
import {
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from "lucide-react";

/* ─── Helpers ────────────────────────────────────────────────────────── */

function formatDisplayDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatDuration(duration: number | null): string {
  if (typeof duration !== "number") return "Unavailable";
  if (duration < 60) return `${duration}s`;
  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;
  return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
}

/* ─── Component ──────────────────────────────────────────────────────── */

export default function PipelineDetailPage() {
  const params = useParams<{ date: string }>();
  const date = params.date;

  const [run, setRun] = useState<AdminPipelineRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/admin/pipeline/${date}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setRun(json.run ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    }
    if (date) load();
  }, [date]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="font-mono text-sm text-text-muted">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="font-mono text-sm text-accent-danger">Error: {error}</p>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <p className="font-mono text-sm text-text-muted">
          No pipeline run found for {date}.
        </p>
        <Link
          href="/admin/pipeline"
          className="text-sm text-accent-primary hover:underline"
        >
          Back to Pipeline History
        </Link>
      </div>
    );
  }

  const sourceErrors = new Set(Object.keys(run.source_errors ?? {}));
  const sources = run.items_per_source
    ? Object.entries(run.items_per_source).sort(([a], [b]) =>
        a.localeCompare(b)
      )
    : [];

  return (
    <div className="space-y-6">
      {/* Page title */}
      <div>
        <Link
          href="/admin/pipeline"
          className="font-mono text-[11px] text-text-muted hover:text-text-primary transition-colors"
        >
          Pipeline History
        </Link>
        <h1 className="mt-1 font-serif text-2xl text-text-bright">
          Pipeline Run — {formatDisplayDate(date)}
        </h1>
      </div>

      {/* ── Status + metrics summary ──────────────────────────────── */}
      <div className="flex flex-wrap gap-4">
        <MetricChip label="Status" value={run.status} color={statusColor(run.status)} />
        <MetricChip
          label="Items"
          value={`${run.items_in_final_brief ?? 0} / ${run.items_collected ?? 0}`}
        />
        <MetricChip
          label="Duration"
          value={formatDuration(run.duration_seconds)}
        />
        <MetricChip
          label="Cost"
          value={
            typeof run.total_cost_usd === "number"
              ? `$${run.total_cost_usd.toFixed(2)}`
              : "Unavailable"
          }
        />
        <MetricChip
          label="Sources"
          value={String(run.sources_count ?? 0)}
        />
      </div>

      {/* ── Pipeline Funnel ────────────────────────────────────────── */}
      <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
        <PipelineFunnel run={run} />
      </div>

      {/* ── Source Breakdown Table ─────────────────────────────────── */}
      {sources.length > 0 && (
        <div className="rounded-sm border border-border-primary bg-bg-secondary">
          <div className="border-b border-border-primary px-4 py-2.5">
            <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">
              Source Breakdown
            </h3>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-primary text-left">
                <th className="px-4 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Source
                </th>
                <th className="px-4 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted text-right">
                  Items
                </th>
                <th className="px-4 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted text-center">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {sources.map(([source, count]) => {
                const hasError = sourceErrors.has(source);
                return (
                  <tr
                    key={source}
                    className="border-b border-border-primary/50 last:border-0"
                  >
                    <td className="px-4 py-2 font-mono text-[11px] text-text-primary uppercase">
                      {source}
                    </td>
                    <td className="px-4 py-2 font-mono text-[11px] text-text-secondary text-right">
                      {count}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {hasError ? (
                        <XCircle className="inline h-3.5 w-3.5 text-accent-danger" />
                      ) : count > 0 ? (
                        <CheckCircle2 className="inline h-3.5 w-3.5 text-accent-success" />
                      ) : (
                        <AlertTriangle className="inline h-3.5 w-3.5 text-accent-warning" />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Navigation Links ──────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3">
        <Link
          href={`/brief/${date}`}
          className="flex items-center gap-1.5 rounded-sm border border-border-primary bg-bg-secondary px-4 py-2 font-mono text-[11px] text-accent-primary hover:bg-bg-tertiary transition-colors"
        >
          View Brief <ArrowRight className="h-3 w-3" />
        </Link>
        <Link
          href={`/admin/drops?date=${date}`}
          className="flex items-center gap-1.5 rounded-sm border border-border-primary bg-bg-secondary px-4 py-2 font-mono text-[11px] text-accent-primary hover:bg-bg-tertiary transition-colors"
        >
          View Drops <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}

/* ─── Metric Chip ────────────────────────────────────────────────────── */

function MetricChip({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-2">
      <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-text-muted">
        {label}
      </p>
      <p
        className={cn(
          "font-mono text-sm font-bold",
          color ?? "text-text-bright"
        )}
      >
        {value}
      </p>
    </div>
  );
}

function statusColor(status: string): string {
  if (status === "success") return "text-accent-success";
  if (status === "partial") return "text-accent-warning";
  return "text-accent-danger";
}
