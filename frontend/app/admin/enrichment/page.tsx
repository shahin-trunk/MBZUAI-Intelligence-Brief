"use client";

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import type {
  EnrichmentItem,
  EnrichmentSummary,
  EnrichmentResponse,
  EnrichmentHistoryResponse,
} from "@/lib/types/enrichment";

/* ─── Dynamic chart import (SSR disabled) ─────────────────────────── */

const EnrichmentCharts = dynamic(
  () => import("@/components/admin/EnrichmentCharts"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] animate-pulse rounded-sm bg-bg-tertiary" />
    ),
  }
);

/* ─── Badge config ──────────────────────────────────────────────────── */

const SOURCE_STEP_CONFIG: Record<string, { label: string; classes: string }> = {
  url_fetch: {
    label: "URL Fetch",
    classes:
      "bg-accent-warning/10 text-accent-warning border-accent-warning/20",
  },
  web_search: {
    label: "Web Search",
    classes:
      "bg-accent-primary/10 text-accent-primary border-accent-primary/20",
  },
  research_agent: {
    label: "Research Agent",
    classes: "bg-sig-high/10 text-sig-high border-sig-high/20",
  },
  none: {
    label: "None",
    classes: "bg-text-muted/10 text-text-muted border-text-muted/20",
  },
};

const STEP_LABEL: Record<string, string> = {
  url_fetch: "URL Fetch",
  judge_1: "Judge 1",
  web_search: "Web Search",
  judge_2: "Judge 2",
  research_agent: "Research Agent",
};

const STAGE_PRIORITY: Record<string, number> = {
  url_fetch: 1,
  web_search: 2,
  research_agent: 3,
};

/** Return the highest enrichment stage present in steps_taken (ignoring judge steps). */
function getHighestStage(stepsTaken: string[]): string {
  let highest = "none";
  let highestPriority = 0;
  for (const step of stepsTaken) {
    const p = STAGE_PRIORITY[step] ?? 0;
    if (p > highestPriority) {
      highestPriority = p;
      highest = step;
    }
  }
  return highest;
}

/* ─── Formatting helpers ────────────────────────────────────────────── */

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function formatPercent(n: number, total: number): string {
  if (total === 0) return "0%";
  return `${Math.round((n / total) * 100)}%`;
}

/* ─── Main Component ────────────────────────────────────────────────── */

export default function EnrichmentPage() {
  const [items, setItems] = useState<EnrichmentItem[]>([]);
  const [summary, setSummary] = useState<EnrichmentSummary | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [history, setHistory] = useState<
    Array<{ date: string; summary: EnrichmentSummary }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [date, setDate] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [search, setSearch] = useState("");

  /* ── Fetch single-date data ──────────────────────────────────────── */
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (date) params.set("date", date);
      params.set("mode", "single");

      const res = await fetch(`/api/admin/enrichment?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: EnrichmentResponse = await res.json();

      setSummary(json.summary ?? null);
      setItems(json.items ?? []);
      setDates(json.dates ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [date]);

  /* ── Fetch history (once) ────────────────────────────────────────── */
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/admin/enrichment?mode=history");
        if (!res.ok) return;
        const json: EnrichmentHistoryResponse = await res.json();
        setHistory(json.history ?? []);
      } catch {
        // non-critical — charts just won't render
      }
    })();
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  /* ── Client-side filtering ───────────────────────────────────────── */
  const filtered = items.filter((item) => {
    if (sourceFilter === "reached_research_agent") {
      if (!item.steps_taken.includes("research_agent")) return false;
    } else if (sourceFilter !== "all" && item.final_source !== sourceFilter) {
      return false;
    }
    if (
      search &&
      !item.headline.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-[28px] text-text-bright">Enrichment</h1>

      {/* ── Date Selector ─────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3">
        <select
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-1.5 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
        >
          <option value="">Latest</option>
          {dates.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-1.5 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
        >
          <option value="all">All Sources</option>
          <option value="url_fetch">URL Fetch</option>
          <option value="web_search">Web Search</option>
          <option value="research_agent">Research Agent</option>
          <option value="reached_research_agent">Reached Research Agent</option>
          <option value="none">None</option>
        </select>

        <input
          type="text"
          placeholder="Search headlines..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-1.5 font-mono text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary flex-1 min-w-[160px]"
        />
      </div>

      {/* ── Loading / Error ───────────────────────────────────────── */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-text-muted">Loading...</p>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-accent-danger">
            Error: {error}
          </p>
        </div>
      )}

      {/* ── Content (only when loaded) ────────────────────────────── */}
      {!loading && !error && (
        <>
          {summary ? (
            <>
              {/* ── Summary Metrics ────────────────────────────────── */}
              <SummaryMetrics summary={summary} />

              {/* ── Chain Flow ─────────────────────────────────────── */}
              <ChainFlow summary={summary} />

              {/* ── Results count ──────────────────────────────────── */}
              <p className="font-mono text-[13px] text-text-muted">
                {filtered.length} item{filtered.length !== 1 ? "s" : ""}{" "}
                {sourceFilter !== "all" || search ? "(filtered)" : ""}
              </p>

              {/* ── Item Cards ─────────────────────────────────────── */}
              <div className="space-y-2">
                {filtered.map((item, i) => (
                  <EnrichmentItemCard key={`${item.headline}-${i}`} item={item} />
                ))}
                {filtered.length === 0 && (
                  <p className="text-center font-mono text-sm text-text-muted py-8">
                    No items match the current filters.
                  </p>
                )}
              </div>
            </>
          ) : (
            <p className="text-center font-mono text-sm text-text-muted py-8">
              No enrichment data available for this date.
            </p>
          )}

          {/* ── Historical Charts ──────────────────────────────────── */}
          {history.length > 1 && (
            <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
              <h3 className="mb-4 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                Historical Trends
              </h3>
              <EnrichmentCharts history={history} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ─── Summary Metrics Grid ──────────────────────────────────────────── */

function MetricTile({
  label,
  value,
  subtext,
  highlight,
}: {
  label: string;
  value: string | number;
  subtext?: string;
  highlight?: "success" | "warning" | "danger" | "gold";
}) {
  const valueColor =
    highlight === "success"
      ? "text-accent-success"
      : highlight === "warning"
        ? "text-accent-warning"
        : highlight === "danger"
          ? "text-accent-danger"
          : highlight === "gold"
            ? "text-sig-high"
            : "text-text-bright";

  return (
    <div className="rounded-sm border border-border-primary bg-bg-tertiary px-3 py-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
        {label}
      </p>
      <p className={cn("mt-1 font-mono text-sm font-bold", valueColor)}>
        {value}
      </p>
      {subtext && (
        <p className="mt-0.5 font-mono text-[12px] text-text-muted">
          {subtext}
        </p>
      )}
    </div>
  );
}

function SummaryMetrics({ summary }: { summary: EnrichmentSummary }) {
  const totalTokens = summary.total_tokens_input + summary.total_tokens_output;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <MetricTile label="Total Items" value={summary.total_items} />
      <MetricTile
        label="Thin Items"
        value={summary.thin_items}
        subtext={formatPercent(summary.thin_items, summary.total_items) + " of total"}
      />
      <MetricTile
        label="Enriched OK"
        value={summary.enriched_successfully}
        highlight="success"
        subtext={formatPercent(summary.enriched_successfully, summary.thin_items) + " success rate"}
      />
      <MetricTile
        label="Tokens"
        value={formatTokens(totalTokens)}
        subtext={`${formatTokens(summary.total_tokens_input)} in / ${formatTokens(summary.total_tokens_output)} out`}
      />
      <MetricTile
        label="Time"
        value={formatDuration(summary.total_elapsed_seconds)}
      />
      <MetricTile
        label="Research Agent"
        value={summary.stage_entered.research_agent ?? 0}
        highlight={(summary.stage_entered.research_agent ?? 0) > 0 ? "gold" : undefined}
        subtext={
          (summary.stage_entered.research_agent ?? 0) > 0
            ? `${summary.research_agent_count} resolved`
            : "no escalations"
        }
      />
    </div>
  );
}

/* ─── Chain Flow Visualization ──────────────────────────────────────── */

function ChainFlow({ summary }: { summary: EnrichmentSummary }) {
  const stages = [
    { key: "url_fetch", label: "URL Fetch", judge: "Judge 1" },
    { key: "web_search", label: "Web Search", judge: "Judge 2" },
    { key: "research_agent", label: "Research Agent", judge: null },
  ];

  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
      <h3 className="mb-4 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
        Enrichment Chain Flow
      </h3>
      <div className="flex items-stretch gap-0 overflow-x-auto">
        {stages.map((stage, idx) => {
          const entered = summary.stage_entered[stage.key] ?? 0;
          const resolved = summary.stage_resolved[stage.key] ?? 0;
          const passedThrough = entered - resolved;

          return (
            <div key={stage.key} className="contents">
              {/* Arrow between stages */}
              {idx > 0 && (
                <div className="flex items-center px-2 text-text-muted shrink-0">
                  <span className="font-mono text-[12px]">▶</span>
                </div>
              )}

              {/* Stage block */}
              <div className="flex-1 min-w-[140px] rounded-sm border border-border-primary bg-bg-tertiary p-3">
                <p className="font-mono text-[12px] font-bold uppercase tracking-[0.1em] text-text-primary">
                  {stage.label}
                </p>
                <div className="mt-2 space-y-1">
                  <p className="font-mono text-[12px] text-text-secondary">
                    <span className="text-text-muted">Entered:</span>{" "}
                    <span className="text-text-bright font-bold">{entered}</span>
                  </p>
                  <p className="font-mono text-[12px] text-text-secondary">
                    <span className="text-text-muted">Resolved:</span>{" "}
                    <span className="text-accent-success font-bold">{resolved}</span>
                  </p>
                  {passedThrough > 0 && (
                    <p className="font-mono text-[12px] text-text-secondary">
                      <span className="text-text-muted">Passed through:</span>{" "}
                      <span className="text-text-muted">{passedThrough}</span>
                    </p>
                  )}
                </div>
                {stage.judge && (
                  <p className="mt-2 font-mono text-[11px] text-text-muted">
                    {stage.judge}: {resolved}/{entered} sufficient
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Enrichment Item Card ──────────────────────────────────────────── */

function EnrichmentItemCard({ item }: { item: EnrichmentItem }) {
  const [expanded, setExpanded] = useState(false);

  const highestStage = getHighestStage(item.steps_taken);
  const sourceConf = SOURCE_STEP_CONFIG[highestStage] ??
    SOURCE_STEP_CONFIG.none;
  const stageDidNotResolve =
    highestStage !== item.final_source && highestStage !== "none";

  const growthPct =
    item.enriched_word_count > 0 && item.original_word_count > 0
      ? Math.round(
          ((item.enriched_word_count - item.original_word_count) /
            item.original_word_count) *
            100
        )
      : 0;

  const barWidth = Math.min(
    100,
    item.enriched_word_count > 0
      ? Math.round((item.enriched_word_count / 1500) * 100)
      : 0
  );

  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
      {/* ── Collapsed header ──────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h4 className="font-serif text-sm text-text-primary leading-snug">
            {item.headline}
          </h4>
          <p className="mt-1 font-mono text-[13px] text-text-muted uppercase">
            {item.source}
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-sm border px-2 py-0.5 font-mono text-[12px]",
            sourceConf.classes
          )}
        >
          {sourceConf.label}
          {stageDidNotResolve && " ✗"}
        </span>
      </div>

      {/* ── Metrics row ───────────────────────────────────────────── */}
      <div className="mt-2 flex flex-wrap items-center gap-3">
        {/* Word growth */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-[12px] text-text-muted">
            {item.original_word_count} → {item.enriched_word_count} words
          </span>
          {growthPct > 0 && (
            <span className="font-mono text-[12px] text-accent-success">
              +{growthPct}%
            </span>
          )}
        </div>

        {/* Inline bar */}
        <div className="flex-1 min-w-[80px] max-w-[200px] h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
          <div
            className="h-full rounded-full bg-accent-primary/60"
            style={{ width: `${barWidth}%` }}
          />
        </div>

        {/* Time badge */}
        <span className="font-mono text-[12px] text-text-muted">
          {item.elapsed_seconds.toFixed(1)}s
        </span>

        {/* Tokens */}
        <span className="font-mono text-[12px] text-text-muted">
          {formatTokens(item.tokens.input + item.tokens.output)} tokens
        </span>
      </div>

      {/* ── Expand toggle ─────────────────────────────────────────── */}
      <div className="mt-2">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 font-mono text-[12px] text-text-muted hover:text-text-primary transition-colors"
        >
          {expanded ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
          {expanded ? "Hide" : "Show"} enrichment details
        </button>
      </div>

      {/* ── Expanded details ──────────────────────────────────────── */}
      {expanded && (
        <div className="mt-3 space-y-4">
          {/* Steps chain */}
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted mb-2">
              Steps Taken
            </p>
            <div className="flex flex-wrap items-center gap-1">
              {item.steps_taken.map((step, i) => (
                <div key={i} className="flex items-center gap-1">
                  {i > 0 && (
                    <span className="text-text-muted font-mono text-[12px]">
                      →
                    </span>
                  )}
                  <span
                    className={cn(
                      "rounded-sm border px-1.5 py-0.5 font-mono text-[11px]",
                      SOURCE_STEP_CONFIG[step]?.classes ??
                        "bg-bg-tertiary text-text-secondary border-border-primary"
                    )}
                  >
                    {STEP_LABEL[step] ?? step}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Judge 1 */}
          <JudgeResultSection label="Judge 1" result={item.judge_1_result} />

          {/* Judge 2 */}
          {item.judge_2_result.confidence > 0 && (
            <JudgeResultSection label="Judge 2" result={item.judge_2_result} />
          )}

          {/* Enriched Sources */}
          {item.enriched_sources.length > 0 && (
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted mb-2">
                Enriched Sources ({item.enriched_sources.length})
              </p>
              <div className="space-y-2">
                {item.enriched_sources.map((src, i) => (
                  <SourceCard key={i} source={src} />
                ))}
              </div>
            </div>
          )}

          {/* Enriched Facts (research agent) */}
          {item.enriched_facts && (
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted mb-2">
                Research Agent Findings
              </p>
              <div className="rounded-sm bg-bg-tertiary p-3 space-y-2">
                <p className="text-[13px] text-text-secondary leading-relaxed">
                  {item.enriched_facts.summary}
                </p>
                {item.enriched_facts.key_facts.length > 0 && (
                  <div>
                    <p className="font-mono text-[11px] text-text-muted uppercase mb-1">
                      Key Facts
                    </p>
                    <ul className="space-y-1">
                      {item.enriched_facts.key_facts.map((kf, i) => (
                        <li
                          key={i}
                          className="font-mono text-[12px] text-text-secondary"
                        >
                          • {kf.fact}
                          {kf.source && (
                            <a
                              href={kf.source}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="ml-1 text-accent-primary hover:underline"
                            >
                              [src]
                            </a>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {item.enriched_facts.open_questions.length > 0 && (
                  <div>
                    <p className="font-mono text-[11px] text-text-muted uppercase mb-1">
                      Open Questions
                    </p>
                    <ul className="space-y-0.5">
                      {item.enriched_facts.open_questions.map((q, i) => (
                        <li
                          key={i}
                          className="font-mono text-[12px] text-text-muted"
                        >
                          ? {q}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Token breakdown */}
          <div className="flex gap-4">
            <p className="font-mono text-[12px] text-text-muted">
              Tokens: {item.tokens.input.toLocaleString()} in /{" "}
              {item.tokens.output.toLocaleString()} out
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Judge Result Section ──────────────────────────────────────────── */

function JudgeResultSection({
  label,
  result,
}: {
  label: string;
  result: EnrichmentItem["judge_1_result"];
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
          {label}
        </p>
        <span
          className={cn(
            "rounded-sm border px-1.5 py-0.5 font-mono text-[11px]",
            result.decision === "SUFFICIENT"
              ? "bg-accent-success/10 text-accent-success border-accent-success/20"
              : "bg-accent-danger/10 text-accent-danger border-accent-danger/20"
          )}
        >
          {result.decision}
        </span>
        <span className="font-mono text-[12px] text-text-muted">
          {(result.confidence * 100).toFixed(0)}% confidence
        </span>
      </div>
      <div className="rounded-sm bg-bg-tertiary p-3 space-y-2">
        {result.reasoning && (
          <p className="text-[13px] text-text-secondary leading-relaxed">
            {result.reasoning}
          </p>
        )}
        {result.missing_elements.length > 0 && (
          <div>
            <p className="font-mono text-[11px] text-text-muted uppercase mb-1">
              Missing Elements
            </p>
            <ul className="space-y-0.5">
              {result.missing_elements.map((el, i) => (
                <li
                  key={i}
                  className="font-mono text-[12px] text-text-secondary"
                >
                  • {el}
                </li>
              ))}
            </ul>
          </div>
        )}
        {result.recommended_query_terms.length > 0 && (
          <div>
            <p className="font-mono text-[11px] text-text-muted uppercase mb-1">
              Recommended Queries
            </p>
            <div className="flex flex-wrap gap-1">
              {result.recommended_query_terms.map((term, i) => (
                <span
                  key={i}
                  className="rounded-sm bg-bg-secondary border border-border-primary px-1.5 py-0.5 font-mono text-[11px] text-text-secondary"
                >
                  {term}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Source Card ────────────────────────────────────────────────────── */

function SourceCard({ source }: { source: EnrichmentItem["enriched_sources"][0] }) {
  const [showFull, setShowFull] = useState(false);
  const stepConf = SOURCE_STEP_CONFIG[source.source_step] ?? SOURCE_STEP_CONFIG.none;

  const truncated =
    source.extract.length > 200
      ? source.extract.slice(0, 200) + "..."
      : source.extract;

  return (
    <div className="rounded-sm bg-bg-tertiary p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[13px] text-text-primary font-medium truncate">
            {source.title || "(untitled)"}
          </p>
          {source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-0.5 flex items-center gap-1 font-mono text-[12px] text-accent-primary hover:underline truncate"
            >
              <ExternalLink className="h-2.5 w-2.5 shrink-0" />
              {source.url}
            </a>
          )}
        </div>
        <span
          className={cn(
            "shrink-0 rounded-sm border px-1.5 py-0.5 font-mono text-[11px]",
            stepConf.classes
          )}
        >
          {stepConf.label}
        </span>
      </div>
      {source.extract && (
        <div className="mt-2">
          <p className="font-mono text-[12px] text-text-secondary whitespace-pre-wrap leading-relaxed">
            {showFull ? source.extract : truncated}
          </p>
          {source.extract.length > 200 && (
            <button
              type="button"
              onClick={() => setShowFull(!showFull)}
              className="mt-1 font-mono text-[11px] text-accent-primary hover:underline"
            >
              {showFull ? "Show less" : "Show full extract"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
