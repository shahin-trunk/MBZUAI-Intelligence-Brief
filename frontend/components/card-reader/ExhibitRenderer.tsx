"use client";

import type { ExhibitData } from "@/lib/types/brief";

interface ExhibitRendererProps {
  exhibit: ExhibitData;
}

/* ── Helpers ─────────────────────────────────────────────── */

/** Return the column index with the highest numeric score, or -1. */
function findBestScoreIndex(
  scores: Record<string, string> | undefined,
  columns: string[],
): number {
  if (!scores || columns.length < 2) return -1;
  let bestIdx = -1;
  let bestVal = -Infinity;
  columns.forEach((col, idx) => {
    const raw = scores[col]?.replace(/[^0-9.]/g, "");
    const num = raw ? parseFloat(raw) : NaN;
    if (!isNaN(num) && num > bestVal) {
      bestVal = num;
      bestIdx = idx;
    }
  });
  return bestIdx;
}

/* ── Benchmark Table ─────────────────────────────────────── */

function BenchmarkTable({ data }: { data: Record<string, unknown> }) {
  const title = data.title as string | undefined;
  const columns = (data.columns ?? data.models ?? []) as string[];
  const rows = (data.rows ?? []) as {
    benchmark?: string;
    model?: string;
    scores?: Record<string, string>;
  }[];

  if (!rows.length) return null;

  return (
    <div className="overflow-x-auto">
      {title && (
        <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-text-muted mb-2.5 pb-1.5 border-b border-border-primary/40">
          {title}
        </p>
      )}
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border-primary">
            <th className="text-left py-2 pr-3 font-mono text-[11px] uppercase tracking-[0.06em] text-text-muted font-medium min-w-[100px]">
              Benchmark
            </th>
            {columns.map((col) => (
              <th
                key={col}
                className="text-right py-2 px-2.5 font-mono text-[11px] uppercase tracking-[0.06em] text-text-muted font-medium whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            // Backend may emit scores as a positional array (["85%", "—"])
            // or as an object keyed by column name ({"Model A": "85%"}).
            // Normalize to object so the column lookup works either way.
            const scoreMap: Record<string, string> = Array.isArray(row.scores)
              ? Object.fromEntries(
                  columns.map((col, idx) => [col, (row.scores as unknown as string[])[idx] ?? "\u2014"])
                )
              : (row.scores ?? {});
            const bestIdx = findBestScoreIndex(scoreMap, columns);
            return (
              <tr
                key={i}
                className={`border-b border-border-primary/30 last:border-0 ${i % 2 === 1 ? "bg-bg-tertiary/30" : ""}`}
              >
                <td className="py-2 pr-3 text-text-primary font-sans">
                  {row.benchmark ?? row.model}
                </td>
                {columns.map((col, colIdx) => {
                  const isBest = colIdx === bestIdx;
                  return (
                    <td
                      key={col}
                      className={`text-right py-2 px-2.5 tabular-nums font-mono ${
                        isBest
                          ? "text-text-bright font-medium"
                          : "text-text-muted"
                      }`}
                    >
                      {scoreMap[col] ?? "\u2014"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── Metric Highlight ────────────────────────────────────── */

function MetricHighlight({ data }: { data: Record<string, unknown> }) {
  const metrics = (data.metrics ?? []) as {
    label: string;
    value: string;
    change?: string;
  }[];
  if (!metrics.length) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
      {metrics.map((m, i) => (
        <div
          key={i}
          className="rounded-sm bg-bg-tertiary/50 px-3 py-3 text-center"
        >
          <p className="text-xl font-semibold tabular-nums text-text-bright">
            {m.value}
          </p>
          {m.change && (
            <p className="text-xs font-mono text-accent-primary mt-0.5">
              {m.change}
            </p>
          )}
          <p className="text-[10px] uppercase tracking-widest text-text-muted mt-1">
            {m.label}
          </p>
        </div>
      ))}
    </div>
  );
}

/* ── Timeline ────────────────────────────────────────────── */

function Timeline({ data }: { data: Record<string, unknown> }) {
  const events = (data.events ?? []) as {
    date: string;
    description: string;
  }[];
  if (!events.length) return null;

  return (
    <div className="space-y-3 pl-5 relative">
      {/* Accent line */}
      <div className="absolute left-[7px] top-1 bottom-1 w-0.5 bg-accent-primary/30 rounded-full" />

      {events.map((ev, i) => (
        <div key={i} className="relative">
          {/* Dot on the line */}
          <div className="absolute -left-5 top-[5px] w-2 h-2 rounded-full bg-accent-primary ring-2 ring-surface-primary" />
          <p className="font-mono text-[11px] text-accent-primary leading-none">
            {ev.date}
          </p>
          <p className="text-sm text-text-primary leading-relaxed mt-0.5">
            {ev.description}
          </p>
        </div>
      ))}
    </div>
  );
}

/* ── Comparison Table ────────────────────────────────────── */

function ComparisonTable({ data }: { data: Record<string, unknown> }) {
  const title = data.title as string | undefined;
  const columns = (data.columns ?? []) as string[];
  const rows = (data.rows ?? []) as Record<string, string>[];

  if (!rows.length) return null;

  return (
    <div className="overflow-x-auto">
      {title && (
        <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-text-muted mb-2.5 pb-1.5 border-b border-border-primary/40">
          {title}
        </p>
      )}
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border-primary">
            {columns.map((col, idx) => (
              <th
                key={col}
                className={`py-2 px-2.5 font-mono text-[11px] uppercase tracking-[0.06em] text-text-muted font-medium whitespace-nowrap ${
                  idx === 0 ? "text-left" : "text-left"
                }`}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={`border-b border-border-primary/30 last:border-0 ${i % 2 === 1 ? "bg-bg-tertiary/30" : ""}`}
            >
              {columns.map((col, colIdx) => (
                <td
                  key={col}
                  className={`py-2 px-2.5 ${
                    colIdx === 0
                      ? "font-medium text-text-primary"
                      : "text-text-secondary"
                  }`}
                >
                  {row[col] ?? "\u2014"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Raw Image ───────────────────────────────────────────── */

function RawImage({
  data,
  sourceImageUrl,
}: {
  data: Record<string, unknown>;
  sourceImageUrl?: string;
}) {
  const url =
    (data.image_url as string) || (data.url as string) || sourceImageUrl;
  const caption = data.caption as string | undefined;

  if (!url) return null;

  return (
    <div>
      <img
        src={url}
        alt={caption ?? "Exhibit image"}
        className="w-full rounded-sm border border-border-secondary"
        loading="lazy"
      />
      {caption && (
        <p className="text-xs text-text-muted italic text-center mt-2">
          {caption}
        </p>
      )}
    </div>
  );
}

/* ── Main Renderer ───────────────────────────────────────── */

export function ExhibitRenderer({ exhibit }: ExhibitRendererProps) {
  return (
    <div className="rounded-sm border border-border-primary/60 bg-surface-primary/80 p-4 mt-5">
      {exhibit.type === "benchmark_table" && (
        <BenchmarkTable data={exhibit.data} />
      )}
      {exhibit.type === "comparison_table" && (
        <ComparisonTable data={exhibit.data} />
      )}
      {exhibit.type === "metric_highlight" && (
        <MetricHighlight data={exhibit.data} />
      )}
      {exhibit.type === "timeline" && <Timeline data={exhibit.data} />}
      {exhibit.type === "raw_image" && (
        <RawImage data={exhibit.data} sourceImageUrl={exhibit.source_image_url} />
      )}
      {exhibit.source_image_url && exhibit.type !== "raw_image" && (
        <a
          href={exhibit.source_image_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] text-text-muted hover:text-accent-primary mt-2 inline-block"
        >
          View original image
        </a>
      )}
    </div>
  );
}
