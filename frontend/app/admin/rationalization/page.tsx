"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { ArrowRight, Minus, Plus, FileText } from "lucide-react";

/* ─── Types ───────────────────────────────────────────────────────── */

interface SwapItem {
  id?: string;
  headline: string;
  reason: string;
  composite_score?: number;
}

interface RationalizationData {
  swaps: number;
  demoted_count?: number;
  promoted_count?: number;
  demoted: SwapItem[];
  promoted: SwapItem[];
  editorial_note: string;
  selected_count_before?: number;
  selected_count_after?: number;
  promotion_pool_size?: number;
  input_tokens?: number;
  output_tokens?: number;
  error?: string;
}

interface ApiResponse {
  data: RationalizationData | null;
  dates: string[];
}

/* ─── Page ────────────────────────────────────────────────────────── */

export default function RationalizationPage() {
  const [data, setData] = useState<RationalizationData | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async (date?: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (date) params.set("date", date);
      const res = await fetch(`/api/admin/rationalization?${params}`);
      const json: ApiResponse = await res.json();
      setData(json.data);
      setDates(json.dates ?? []);
      if (!date && json.dates?.[0]) {
        setSelectedDate(json.dates[0]);
      }
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDateChange = (date: string) => {
    setSelectedDate(date);
    fetchData(date);
  };

  const hasSwaps = data && data.swaps > 0;
  const isNoOp = data && data.swaps === 0 && !data.error;
  const isError = data?.error;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">
            Brief Rationalization
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Portfolio-level review of the brief before writing
          </p>
        </div>
        {dates.length > 0 && (
          <select
            value={selectedDate}
            onChange={(e) => handleDateChange(e.target.value)}
            className="rounded-md border border-border-primary bg-bg-secondary px-3 py-1.5 text-sm text-text-primary"
          >
            {dates.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        )}
      </div>

      {loading && (
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-lg bg-bg-tertiary"
            />
          ))}
        </div>
      )}

      {!loading && !data && (
        <div className="rounded-lg border border-border-primary bg-bg-secondary p-8 text-center text-text-secondary">
          No rationalization data available for this date.
        </div>
      )}

      {!loading && data && (
        <>
          {/* Summary strip */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MetricTile
              label="Items before"
              value={data.selected_count_before ?? "—"}
            />
            <MetricTile
              label="Items after"
              value={data.selected_count_after ?? data.selected_count_before ?? "—"}
            />
            <MetricTile label="Swaps" value={data.swaps} highlight={data.swaps > 0} />
            <MetricTile
              label="Promotion pool"
              value={data.promotion_pool_size ?? "—"}
            />
          </div>

          {/* Token cost */}
          {(data.input_tokens || data.output_tokens) && (
            <p className="text-xs text-text-muted">
              Sonnet tokens: {(data.input_tokens ?? 0).toLocaleString()} in /{" "}
              {(data.output_tokens ?? 0).toLocaleString()} out
            </p>
          )}

          {/* Error state */}
          {isError && (
            <div className="rounded-lg border border-sig-high/30 bg-sig-high/5 p-4">
              <p className="text-sm font-medium text-sig-high">
                Rationalization failed (brief proceeded unchanged)
              </p>
              <p className="mt-1 text-xs text-text-secondary">{data.error}</p>
            </div>
          )}

          {/* No-op state */}
          {isNoOp && (
            <div className="rounded-lg border border-accent-primary/20 bg-accent-primary/5 p-4">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-accent-primary" />
                <p className="text-sm font-medium text-accent-primary">
                  No changes needed
                </p>
              </div>
              {data.editorial_note && (
                <p className="mt-2 text-sm text-text-secondary">
                  {data.editorial_note}
                </p>
              )}
            </div>
          )}

          {/* Swap cards */}
          {hasSwaps && (
            <div className="space-y-4">
              <h2 className="text-sm font-medium text-text-secondary uppercase tracking-wider">
                Swaps
              </h2>
              {data.demoted.map((demoted, i) => {
                const promoted = data.promoted[i];
                return (
                  <div
                    key={demoted.headline}
                    className="rounded-lg border border-border-primary bg-bg-secondary overflow-hidden"
                  >
                    <div className="grid grid-cols-1 divide-y divide-border-primary md:grid-cols-[1fr_auto_1fr] md:divide-x md:divide-y-0">
                      {/* Demoted */}
                      <div className="p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="inline-flex items-center gap-1 rounded-full bg-sig-high/10 px-2 py-0.5 text-xs font-medium text-sig-high">
                            <Minus className="h-3 w-3" />
                            Demoted
                          </span>
                          {demoted.composite_score != null && (
                            <span className="text-xs text-text-muted">
                              {demoted.composite_score}
                            </span>
                          )}
                        </div>
                        <p className="text-sm font-medium text-text-primary">
                          {demoted.headline}
                        </p>
                        <p className="mt-1 text-xs text-text-secondary">
                          {demoted.reason}
                        </p>
                      </div>

                      {/* Arrow */}
                      <div className="hidden md:flex items-center justify-center px-3">
                        <ArrowRight className="h-4 w-4 text-text-muted" />
                      </div>

                      {/* Promoted */}
                      {promoted ? (
                        <div className="p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="inline-flex items-center gap-1 rounded-full bg-accent-primary/10 px-2 py-0.5 text-xs font-medium text-accent-primary">
                              <Plus className="h-3 w-3" />
                              Promoted
                            </span>
                            {promoted.composite_score != null && (
                              <span className="text-xs text-text-muted">
                                {promoted.composite_score}
                              </span>
                            )}
                          </div>
                          <p className="text-sm font-medium text-text-primary">
                            {promoted.headline}
                          </p>
                          <p className="mt-1 text-xs text-text-secondary">
                            {promoted.reason}
                          </p>
                        </div>
                      ) : (
                        <div className="p-4 flex items-center text-sm text-text-muted">
                          No replacement (brief shrunk by 1)
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Editorial note */}
          {hasSwaps && data.editorial_note && (
            <div className="rounded-lg border border-border-primary bg-bg-secondary p-4">
              <h2 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-2">
                Editorial Note
              </h2>
              <p className="text-sm text-text-primary whitespace-pre-wrap">
                {data.editorial_note}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ─── Metric tile ─────────────────────────────────────────────────── */

function MetricTile({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border-primary bg-bg-secondary p-4">
      <p className="text-xs text-text-secondary">{label}</p>
      <p
        className={cn(
          "mt-1 text-2xl font-semibold",
          highlight ? "text-accent-primary" : "text-text-primary"
        )}
      >
        {value}
      </p>
    </div>
  );
}
