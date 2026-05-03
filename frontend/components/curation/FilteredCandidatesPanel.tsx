"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * FilteredCandidatesPanel
 *
 * Phase 1 drop-visibility surface for the curation workspace.
 *
 * Shows every candidate item the pipeline dropped for the current brief_date,
 * grouped by `dropped_at_stage`. Previously, triage / previous-brief overlap /
 * post-Gatekeeper overlap / Gatekeeper implicit drops were silently lost with
 * no curator visibility — that is the bug this component closes.
 *
 * View-only for v1. Each row links through to the admin Drops page for raw
 * context. Rescue (moving a dropped item back into the pending pool) is a
 * follow-up once Phase 2 (Synthesis) is validated in production.
 */

interface FilteredItem {
  id: string;
  run_date: string;
  headline: string;
  source_name: string | null;
  source_url: string | null;
  dropped_at_stage: string;
  drop_reason: string | null;
  composite_score: number | null;
  created_at: string;
}

interface FilteredResponse {
  date: string;
  total: number;
  byStage: Record<string, FilteredItem[]>;
  items: FilteredItem[];
}

const STAGE_LABELS: Record<string, string> = {
  triage: "Triage",
  date_filter: "Date Filter",
  content_filter: "Content Filter",
  previous_brief_overlap: "Previous-Brief Overlap",
  gatekeeper: "Gatekeeper",
  gatekeeper_implicit: "Gatekeeper (Implicit)",
  post_gatekeeper_overlap: "Post-Gatekeeper Overlap",
};

// Stages that indicate a genuinely lost candidate the curator might want to
// rescue (as opposed to routine relevance filtering). Rendered first.
const PRIORITY_STAGES = [
  "gatekeeper_implicit",
  "post_gatekeeper_overlap",
  "previous_brief_overlap",
  "gatekeeper",
];

function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage;
}

function sortStages(stages: string[]): string[] {
  const priority = new Set(PRIORITY_STAGES);
  const prioritised = PRIORITY_STAGES.filter((s) => stages.includes(s));
  const rest = stages.filter((s) => !priority.has(s)).sort();
  return [...prioritised, ...rest];
}

export function FilteredCandidatesPanel({ briefDate }: { briefDate: string }) {
  const [data, setData] = useState<FilteredResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [openStages, setOpenStages] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!expanded || data) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/admin/curation/filtered?date=${encodeURIComponent(briefDate)}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: FilteredResponse = await res.json();
        if (!cancelled) setData(json);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Load failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [expanded, data, briefDate]);

  const total = data?.total ?? 0;
  const stages = data ? sortStages(Object.keys(data.byStage)) : [];

  return (
    <div className="mt-8 mb-6 rounded-lg border border-border-secondary bg-surface-secondary">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-surface-tertiary transition-colors"
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-text-muted" />
          ) : (
            <ChevronDown className="h-4 w-4 text-text-muted" />
          )}
          <span className="text-sm font-medium text-text-primary">
            Filtered candidates
          </span>
          {data && (
            <span className="text-xs text-text-muted tabular-nums">
              ({total})
            </span>
          )}
        </div>
        <span className="text-xs text-text-muted">
          Items the pipeline dropped — review for missed stories
        </span>
      </button>

      {expanded && (
        <div className="border-t border-border-secondary px-4 pb-4">
          {loading && (
            <p className="py-4 text-xs text-text-muted font-mono">
              Loading filtered candidates…
            </p>
          )}
          {error && (
            <p className="py-4 text-xs text-accent-danger font-mono">
              Error: {error}
            </p>
          )}
          {!loading && !error && data && total === 0 && (
            <p className="py-4 text-xs text-text-muted font-mono">
              No filtered candidates on record for this brief date.
            </p>
          )}
          {!loading && !error && data && total > 0 && (
            <div className="mt-3 space-y-3">
              {stages.map((stage) => {
                const rows = data.byStage[stage] ?? [];
                const isOpen = openStages[stage] ?? PRIORITY_STAGES.includes(stage);
                return (
                  <div
                    key={stage}
                    className="rounded-md border border-border-primary bg-bg-secondary"
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setOpenStages((prev) => ({
                          ...prev,
                          [stage]: !isOpen,
                        }))
                      }
                      className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-bg-tertiary transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        {isOpen ? (
                          <ChevronUp className="h-3 w-3 text-text-muted" />
                        ) : (
                          <ChevronDown className="h-3 w-3 text-text-muted" />
                        )}
                        <span className="text-xs font-medium text-text-primary">
                          {stageLabel(stage)}
                        </span>
                        <span className="text-[11px] text-text-muted tabular-nums">
                          ({rows.length})
                        </span>
                      </div>
                    </button>
                    {isOpen && (
                      <ul className="divide-y divide-border-primary">
                        {rows.map((row) => (
                          <li
                            key={row.id}
                            className="px-3 py-2 text-xs"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <p className="text-text-primary leading-snug">
                                  {row.headline}
                                </p>
                                <p className="mt-0.5 text-[11px] text-text-muted font-mono uppercase">
                                  {row.source_name ?? "—"}
                                  {row.composite_score !== null && (
                                    <span className="ml-2">
                                      score {row.composite_score.toFixed(2)}
                                    </span>
                                  )}
                                </p>
                                {row.drop_reason && (
                                  <p className="mt-1 text-[11px] text-text-secondary">
                                    {row.drop_reason}
                                  </p>
                                )}
                              </div>
                              <Link
                                href={`/admin/drops?date=${encodeURIComponent(briefDate)}&stage=${encodeURIComponent(stage)}&search=${encodeURIComponent(row.headline.slice(0, 40))}`}
                                className={cn(
                                  "shrink-0 text-[11px] font-mono text-text-muted hover:text-text-primary",
                                )}
                              >
                                View →
                              </Link>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
