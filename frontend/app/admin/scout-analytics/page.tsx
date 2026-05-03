"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";

/* ─── Types ──────────────────────────────────────────────────────────── */

interface ScoutRun {
  id: string;
  run_date: string;
  model: string;
  search_count: number;
  candidates_returned: number;
  candidates_passed_triage: number;
  candidates_in_brief: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  duration_seconds: number;
  raw_output: unknown;
  created_at: string;
}

interface EntityHit {
  entity_name: string;
  priority: "high" | "standard";
  enabled: boolean;
  last_hit_date: string | null;
}

interface Summary {
  total_runs: number;
  total_cost: number;
  avg_candidates: number;
  avg_cost: number;
}

/* ─── Component ──────────────────────────────────────────────────────── */

export default function ScoutAnalyticsPage() {
  const [runs, setRuns] = useState<ScoutRun[]>([]);
  const [entities, setEntities] = useState<EntityHit[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/scout-analytics?days=${days}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setRuns(json.runs ?? []);
      setEntities(json.entities ?? []);
      setSummary(json.summary ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-[28px] text-text-bright">
          Scout Analytics
        </h1>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-1.5 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* ── Loading / Error ────────────────────────────────────────── */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-text-muted">Loading...</p>
        </div>
      )}

      {error && (
        <div className="rounded-sm border border-accent-danger/20 bg-accent-danger/5 p-3">
          <p className="font-mono text-sm text-accent-danger">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* ── Summary Stats ──────────────────────────────────────── */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard label="Total Runs" value={summary.total_runs} />
              <StatCard
                label="Avg Candidates"
                value={summary.avg_candidates}
              />
              <StatCard
                label="Avg Cost"
                value={`$${summary.avg_cost.toFixed(2)}`}
              />
              <StatCard
                label="Total Cost"
                value={`$${summary.total_cost.toFixed(2)}`}
              />
            </div>
          )}

          {/* ── Run Log Table ──────────────────────────────────────── */}
          <div>
            <h2 className="mb-3 font-mono text-[14px] font-bold uppercase tracking-[0.1em] text-text-muted">
              Run Log
            </h2>
            {runs.length === 0 ? (
              <p className="py-8 text-center font-mono text-sm text-text-muted">
                No scout runs recorded in this period.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-sm border border-border-primary">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border-primary bg-bg-secondary">
                      <th className="px-3 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                        Date
                      </th>
                      <th className="px-3 py-2.5 text-right font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                        Searches
                      </th>
                      <th className="px-3 py-2.5 text-right font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                        Found
                      </th>
                      <th className="px-3 py-2.5 text-right font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                        Triage
                      </th>
                      <th className="px-3 py-2.5 text-right font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                        Brief
                      </th>
                      <th className="px-3 py-2.5 text-right font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                        Tokens
                      </th>
                      <th className="px-3 py-2.5 text-right font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                        Cost
                      </th>
                      <th className="px-3 py-2.5 text-right font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                        Duration
                      </th>
                      <th className="px-3 py-2.5 w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <RunRow
                        key={run.id}
                        run={run}
                        expanded={expandedId === run.id}
                        onToggle={() =>
                          setExpandedId(
                            expandedId === run.id ? null : run.id
                          )
                        }
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Entity Hit Rates ────────────────────────────────────── */}
          <div>
            <h2 className="mb-3 font-mono text-[14px] font-bold uppercase tracking-[0.1em] text-text-muted">
              Entity Hit Rates
            </h2>
            <div className="overflow-x-auto rounded-sm border border-border-primary">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border-primary bg-bg-secondary">
                    <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                      Entity
                    </th>
                    <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                      Priority
                    </th>
                    <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                      Status
                    </th>
                    <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                      Last Hit
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {entities.map((ent) => (
                    <tr
                      key={ent.entity_name}
                      className="border-b border-border-primary last:border-0 hover:bg-bg-tertiary/30 transition-colors"
                    >
                      <td className="px-4 py-2 font-mono text-[13px] text-text-primary">
                        {ent.entity_name}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-sm border px-2 py-0.5 font-mono text-[11px]",
                            ent.priority === "high"
                              ? "bg-sig-high/10 text-sig-high border-sig-high/20"
                              : "bg-bg-tertiary text-text-muted border-border-primary"
                          )}
                        >
                          {ent.priority}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "font-mono text-[12px]",
                            ent.enabled
                              ? "text-accent-primary"
                              : "text-text-muted"
                          )}
                        >
                          {ent.enabled ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-[13px] text-text-muted">
                        {ent.last_hit_date ?? "Never"}
                      </td>
                    </tr>
                  ))}
                  {entities.length === 0 && (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-4 py-8 text-center font-mono text-sm text-text-muted"
                      >
                        No entities in watchlist.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ─── Stat Card ──────────────────────────────────────────────────────── */

function StatCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
        {label}
      </p>
      <p className="mt-1 font-mono text-[20px] text-text-bright">{value}</p>
    </div>
  );
}

/* ─── Run Row ────────────────────────────────────────────────────────── */

function RunRow({
  run,
  expanded,
  onToggle,
}: {
  run: ScoutRun;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className="border-b border-border-primary last:border-0 hover:bg-bg-tertiary/30 transition-colors">
        <td className="px-3 py-2 font-mono text-[13px] text-text-primary">
          {run.run_date}
        </td>
        <td className="px-3 py-2 text-right font-mono text-[13px] text-text-muted">
          {run.search_count}
        </td>
        <td className="px-3 py-2 text-right font-mono text-[13px] text-text-primary">
          {run.candidates_returned}
        </td>
        <td className="px-3 py-2 text-right font-mono text-[13px] text-text-muted">
          {run.candidates_passed_triage}
        </td>
        <td className="px-3 py-2 text-right font-mono text-[13px] text-text-muted">
          {run.candidates_in_brief}
        </td>
        <td className="px-3 py-2 text-right font-mono text-[13px] text-text-muted">
          {(run.input_tokens + run.output_tokens).toLocaleString()}
        </td>
        <td className="px-3 py-2 text-right font-mono text-[13px] text-text-muted">
          ${Number(run.cost_usd).toFixed(2)}
        </td>
        <td className="px-3 py-2 text-right font-mono text-[13px] text-text-muted">
          {Number(run.duration_seconds).toFixed(1)}s
        </td>
        <td className="px-3 py-2">
          <button
            type="button"
            onClick={onToggle}
            className="rounded-sm p-1 text-text-muted hover:text-text-primary transition-colors"
          >
            {expanded ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>
        </td>
      </tr>
      {expanded && run.raw_output && (
        <tr className="border-b border-border-primary">
          <td colSpan={9} className="px-3 py-3">
            <pre className="max-h-64 overflow-auto rounded-sm bg-bg-tertiary p-3 font-mono text-[12px] text-text-secondary whitespace-pre-wrap">
              {JSON.stringify(run.raw_output, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}
