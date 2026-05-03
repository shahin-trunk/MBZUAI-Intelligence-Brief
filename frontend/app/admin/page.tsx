"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { PipelineFunnel } from "@/components/admin/PipelineFunnel";
import type { AdminPipelineRun } from "@/lib/types/admin";
import {
  ExternalLink,
  Search,
  Flag,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from "lucide-react";

interface OverviewData {
  run: AdminPipelineRun | null;
  pendingResearch: number;
  todayFlags: number;
}

/* ─── Helpers ────────────────────────────────────────────────────────── */

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatTime(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Dubai",
    }) + " GST";
  } catch {
    return "";
  }
}

function formatCost(cost: number | null): string {
  return typeof cost === "number" ? `$${cost.toFixed(2)}` : "Unavailable";
}

function formatDuration(duration: number | null): string {
  if (typeof duration !== "number") {
    return "Unavailable";
  }
  if (duration < 60) {
    return `${duration}s`;
  }

  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;
  return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
}

/* ─── Component ──────────────────────────────────────────────────────── */

export default function AdminOverview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/admin/overview");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

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

  const run = data?.run ?? null;

  return (
    <div className="space-y-6">
      {/* Page title */}
      <h1 className="font-serif text-[28px] text-text-bright">Overview</h1>

      {/* ── Run Status Banner ──────────────────────────────────────── */}
      {run ? (
        <RunStatusBanner run={run} />
      ) : (
        <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
          <p className="font-mono text-sm text-text-muted">
            No pipeline runs found.
          </p>
        </div>
      )}

      {/* ── Pipeline Funnel ────────────────────────────────────────── */}
      {run && (
        <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
          <PipelineFunnel run={run} />
        </div>
      )}

      {/* ── Source Breakdown ───────────────────────────────────────── */}
      {run && run.items_per_source && (
        <SourceBreakdown
          itemsPerSource={run.items_per_source}
          sourceErrors={run.source_errors}
        />
      )}

      {/* ── Quick Action Cards ─────────────────────────────────────── */}
      <QuickActions
        pendingResearch={data?.pendingResearch ?? 0}
        todayFlags={data?.todayFlags ?? 0}
      />
    </div>
  );
}

/* ─── Run Status Banner ──────────────────────────────────────────────── */

function RunStatusBanner({ run }: { run: AdminPipelineRun }) {
  const status = run.status ?? "success";
  const borderColor =
    status === "success"
      ? "border-l-accent-success"
      : status === "partial"
        ? "border-l-accent-warning"
        : "border-l-accent-danger";

  const dotColor =
    status === "success"
      ? "bg-accent-success"
      : status === "partial"
        ? "bg-accent-warning"
        : "bg-accent-danger";

  const statusLabel =
    status === "success"
      ? "BRIEF DELIVERED"
      : status === "partial"
        ? "PARTIAL DELIVERY"
        : "PIPELINE FAILED";

  const itemCount = run.items_in_final_brief ?? 0;
  const sourceCount = run.sources_count ?? 0;
  const generatedAt = run.completed_at ? formatTime(run.completed_at) : "";
  const duration = formatDuration(run.duration_seconds);
  const cost = formatCost(run.total_cost_usd);

  return (
    <div
      className={cn(
        "rounded-sm border border-border-primary border-l-4 bg-bg-secondary p-4",
        borderColor
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn("mt-1 h-2.5 w-2.5 rounded-full shrink-0", dotColor)} />
        <div className="min-w-0 flex-1">
          <p className="font-mono text-xs font-bold text-text-bright uppercase tracking-wide">
            {statusLabel} — {formatDate(run.run_date)}
          </p>
          <p className="mt-1 font-mono text-[13px] text-text-secondary">
            {itemCount} items · {sourceCount} sources
            {generatedAt ? ` · Generated ${generatedAt}` : ""}
          </p>
          <p className="mt-0.5 font-mono text-[13px] text-text-muted">
            Pipeline duration: {duration} · Cost: {cost}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ─── Source Breakdown Table ──────────────────────────────────────────── */

function SourceBreakdown({
  itemsPerSource,
  sourceErrors,
}: {
  itemsPerSource: Record<string, number>;
  sourceErrors: Record<string, string> | null;
}) {
  const errors = new Set(Object.keys(sourceErrors ?? {}));
  const sources = Object.entries(itemsPerSource).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary">
      <div className="border-b border-border-primary px-4 py-2.5">
        <h3 className="font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
          Source Breakdown
        </h3>
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b border-border-primary text-left">
            <th className="px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
              Source
            </th>
            <th className="px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted text-right">
              Items
            </th>
            <th className="px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted text-center">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {sources.map(([source, count]) => {
            const hasError = errors.has(source);
            return (
              <tr
                key={source}
                className="border-b border-border-primary/50 last:border-0"
              >
                <td className="px-4 py-2 font-mono text-[13px] text-text-primary uppercase">
                  {source}
                </td>
                <td className="px-4 py-2 font-mono text-[13px] text-text-secondary text-right">
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
  );
}

/* ─── Quick Action Cards ─────────────────────────────────────────────── */

function QuickActions({
  pendingResearch,
  todayFlags,
}: {
  pendingResearch: number;
  todayFlags: number;
}) {
  const cards = [
    {
      label: "View Today's Brief",
      href: "/",
      icon: ExternalLink,
      value: null,
    },
    {
      label: "Pending Research",
      href: "/admin/research",
      icon: Search,
      value: pendingResearch,
    },
    {
      label: "Items Flagged",
      href: "/flagged",
      icon: Flag,
      value: todayFlags,
    },
    {
      label: "View Drop Log",
      href: "/admin/drops",
      icon: Trash2,
      value: null,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <Link
            key={card.href}
            href={card.href}
            className="group rounded-sm border border-border-primary bg-bg-secondary p-4 hover:border-border-accent hover:bg-bg-tertiary transition-colors"
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon className="h-3.5 w-3.5 text-text-muted group-hover:text-accent-primary transition-colors" />
              <span className="font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                {card.label}
              </span>
            </div>
            {card.value !== null && (
              <p className="font-mono text-lg text-text-bright">{card.value}</p>
            )}
          </Link>
        );
      })}
    </div>
  );
}
