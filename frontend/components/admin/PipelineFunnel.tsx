"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import type { AdminPipelineRun } from "@/lib/types/admin";

/* ─── Types ──────────────────────────────────────────────────────────── */

interface FunnelStage {
  key: string;
  label: string;
  count: number;
}

interface PipelineFunnelProps {
  run: Pick<
    AdminPipelineRun,
    | "items_collected"
    | "items_after_triage"
    | "items_after_date_filter"
    | "items_after_dedup"
    | "items_after_content_filter"
    | "items_after_gatekeeper"
    | "items_in_final_brief"
  >;
  className?: string;
}

/* ─── Stage colors: gradient from muted (early) to accent-primary (final) ─ */

const STAGE_COLORS: Record<string, string> = {
  collected: "bg-text-muted",
  triaged: "bg-text-muted",
  date_filter: "bg-sig-low",
  dedup: "bg-sig-low",
  content_filter: "bg-sig-medium",
  gatekeeper: "bg-sig-high",
  final_brief: "bg-accent-primary",
};

const STAGE_TEXT_COLORS: Record<string, string> = {
  collected: "text-text-muted",
  triaged: "text-text-muted",
  date_filter: "text-sig-low",
  dedup: "text-sig-low",
  content_filter: "text-sig-medium",
  gatekeeper: "text-sig-high",
  final_brief: "text-accent-primary",
};

/* ─── Component ──────────────────────────────────────────────────────── */

export function PipelineFunnel({ run, className }: PipelineFunnelProps) {
  const hasExpansion =
    (run.items_after_triage ?? run.items_after_dedup ?? 0) >
    (run.items_collected ?? 0);

  // Build stages array, skipping null values
  const allStages: FunnelStage[] = [
    {
      key: "collected",
      label: "Collected Articles",
      count: run.items_collected ?? -1,
    },
    {
      key: "triaged",
      label: "Triaged",
      count: run.items_after_triage ?? -1,
    },
    {
      key: "date_filter",
      label: "Date Filter",
      count: run.items_after_date_filter ?? -1,
    },
    {
      key: "dedup",
      label: "Candidate Pool",
      count: run.items_after_dedup ?? -1,
    },
    {
      key: "content_filter",
      label: "Content Filter",
      count: run.items_after_content_filter ?? -1,
    },
    {
      key: "gatekeeper",
      label: "Gatekeeper",
      count: run.items_after_gatekeeper ?? -1,
    },
    {
      key: "final_brief",
      label: "Final Brief",
      count: run.items_in_final_brief ?? -1,
    },
  ];

  const stages = allStages.filter((s) => s.count >= 0);

  if (stages.length === 0) {
    return (
      <p className="font-mono text-xs text-text-muted">
        No funnel data available.
      </p>
    );
  }

  const maxCount = Math.max(...stages.map((s) => s.count), 1);

  return (
    <div className={cn("space-y-2", className)}>
      <h3 className="font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
        Pipeline Funnel
      </h3>
      {hasExpansion && (
        <p className="font-mono text-[12px] text-text-muted">
          Candidate stages can exceed collected articles because newsletter and
          feed items split into multiple story candidates.
        </p>
      )}

      <div className="space-y-1.5">
        {stages.map((stage, idx) => {
          const widthPct = Math.max((stage.count / maxCount) * 100, 4);
          const drop =
            idx > 0 ? stages[idx - 1].count - stage.count : null;

          return (
            <div key={stage.key}>
              {/* Drop indicator between bars */}
              {drop !== null && drop !== 0 && (
                <div className="flex items-center gap-1.5 pl-[92px] py-0.5">
                  <div className="h-px flex-1 max-w-16 bg-border-primary" />
                  <span
                    className={cn(
                      "font-mono text-[12px]",
                      drop > 0 ? "text-accent-danger" : "text-accent-primary"
                    )}
                  >
                    {drop > 0 ? `-${drop}` : `+${Math.abs(drop)}`}
                  </span>
                </div>
              )}

              <div className="flex items-center gap-3">
                {/* Stage label — links to drop log filtered by stage */}
                <Link
                  href={`/admin/drops?stage=${stage.key}`}
                  className={cn(
                    "w-[88px] shrink-0 text-right font-mono text-[12px] hover:underline",
                    STAGE_TEXT_COLORS[stage.key] ?? "text-text-muted"
                  )}
                >
                  {stage.label}
                </Link>

                {/* Bar */}
                <div className="flex-1 flex items-center gap-2">
                  <div
                    className={cn(
                      "h-5 rounded-sm transition-all duration-300",
                      STAGE_COLORS[stage.key] ?? "bg-text-muted"
                    )}
                    style={{ width: `${widthPct}%` }}
                  />
                  <span className="font-mono text-xs text-text-secondary">
                    {stage.count}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
