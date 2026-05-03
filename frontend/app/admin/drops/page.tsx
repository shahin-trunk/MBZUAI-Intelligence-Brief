"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";

/* ─── Types ──────────────────────────────────────────────────────────── */

interface DroppedItem {
  id: string;
  run_date: string;
  headline: string;
  source_name: string;
  dropped_at_stage: string;
  drop_reason: string | null;
  composite_score: number | null;
  raw_content: string | null;
  created_at: string;
}

interface DropsResponse {
  items: DroppedItem[];
  dates: Array<{ run_date: string }>;
}

/* ─── Stage display config ───────────────────────────────────────────── */

const STAGE_CONFIG: Record<string, { label: string; classes: string }> = {
  triage: {
    label: "Triage",
    classes: "bg-text-muted/10 text-text-muted border-text-muted/20",
  },
  date_filter: {
    label: "Date Filter",
    classes: "bg-accent-warning/10 text-accent-warning border-accent-warning/20",
  },
  content_filter: {
    label: "Content Filter",
    classes: "bg-accent-primary/10 text-accent-primary border-accent-primary/20",
  },
  previous_brief_overlap: {
    label: "Previous-Brief Overlap",
    classes: "bg-sig-medium/10 text-sig-medium border-sig-medium/20",
  },
  gatekeeper: {
    label: "Gatekeeper",
    classes: "bg-sig-high/10 text-sig-high border-sig-high/20",
  },
  gatekeeper_implicit: {
    label: "Gatekeeper (Implicit)",
    classes: "bg-accent-danger/10 text-accent-danger border-accent-danger/20",
  },
  post_gatekeeper_overlap: {
    label: "Post-Gatekeeper Overlap",
    classes: "bg-sig-medium/10 text-sig-medium border-sig-medium/20",
  },
};

const STAGE_OPTIONS = [
  { label: "All Stages", value: "all" },
  { label: "Triage", value: "triage" },
  { label: "Date Filter", value: "date_filter" },
  { label: "Content Filter", value: "content_filter" },
  { label: "Previous-Brief Overlap", value: "previous_brief_overlap" },
  { label: "Gatekeeper", value: "gatekeeper" },
  { label: "Gatekeeper (Implicit)", value: "gatekeeper_implicit" },
  { label: "Post-Gatekeeper Overlap", value: "post_gatekeeper_overlap" },
];

/* ─── Component ──────────────────────────────────────────────────────── */

export default function DropsPage() {
  const searchParams = useSearchParams();

  const [items, setItems] = useState<DroppedItem[]>([]);
  const [dates, setDates] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters — initialize from URL params
  const [date, setDate] = useState(searchParams.get("date") ?? "");
  const [stage, setStage] = useState(searchParams.get("stage") ?? "all");
  const [source, setSource] = useState(searchParams.get("source") ?? "");
  const [search, setSearch] = useState(searchParams.get("search") ?? "");

  const fetchDrops = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (date) params.set("date", date);
      if (stage && stage !== "all") params.set("stage", stage);
      if (source) params.set("source", source);
      if (search) params.set("search", search);

      const res = await fetch(`/api/admin/drops?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: DropsResponse = await res.json();
      setItems(json.items ?? []);
      setDates((json.dates ?? []).map((d) => d.run_date));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [date, stage, source, search]);

  useEffect(() => {
    fetchDrops();
  }, [fetchDrops]);

  return (
    <div className="space-y-6">
      {/* Page title */}
      <h1 className="font-serif text-[28px] text-text-bright">Drop Log</h1>

      {/* ── Filter Bar ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3">
        {/* Date select */}
        <select
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-1.5 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
        >
          <option value="">All Dates</option>
          {dates.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>

        {/* Stage select */}
        <select
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-1.5 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
        >
          {STAGE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Source input */}
        <input
          type="text"
          placeholder="Source..."
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-1.5 font-mono text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary w-32"
        />

        {/* Search input */}
        <input
          type="text"
          placeholder="Search headlines..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-sm border border-border-primary bg-bg-secondary px-3 py-1.5 font-mono text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary flex-1 min-w-[160px]"
        />
      </div>

      {/* ── Results count ──────────────────────────────────────────── */}
      {!loading && !error && (
        <p className="font-mono text-[13px] text-text-muted">
          {items.length} item{items.length !== 1 ? "s" : ""} dropped
        </p>
      )}

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

      {/* ── Drop Item Cards ────────────────────────────────────────── */}
      {!loading && !error && (
        <div className="space-y-2">
          {items.map((item) => (
            <DropItemCard key={item.id} item={item} />
          ))}
          {items.length === 0 && (
            <p className="text-center font-mono text-sm text-text-muted py-8">
              No dropped items match the current filters.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Drop Item Card ─────────────────────────────────────────────────── */

function DropItemCard({ item }: { item: DroppedItem }) {
  const [expanded, setExpanded] = useState(false);

  const stageConf = STAGE_CONFIG[item.dropped_at_stage] ?? {
    label: item.dropped_at_stage,
    classes: "bg-bg-tertiary text-text-muted border-border-primary",
  };

  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
      {/* Header row: headline + stage badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h4 className="font-serif text-sm text-text-primary leading-snug">
            {item.headline}
          </h4>
          <p className="mt-1 font-mono text-[13px] text-text-muted uppercase">
            {item.source_name}
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-sm border px-2 py-0.5 font-mono text-[12px]",
            stageConf.classes
          )}
        >
          {stageConf.label}
        </span>
      </div>

      {/* Drop reason */}
      {item.drop_reason && (
        <p className="mt-2 text-sm text-text-secondary">
          {item.drop_reason}
        </p>
      )}

      {/* Composite score */}
      {item.composite_score !== null && (
        <p className="mt-1 font-mono text-[13px] text-text-muted">
          Score: {item.composite_score.toFixed(2)}
        </p>
      )}

      {/* Expandable raw content */}
      {item.raw_content && (
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
            {expanded ? "Hide" : "Show"} raw content
          </button>
          {expanded && (
            <pre className="mt-2 max-h-48 overflow-auto rounded-sm bg-bg-tertiary p-3 font-mono text-[12px] text-text-secondary whitespace-pre-wrap">
              {item.raw_content}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
