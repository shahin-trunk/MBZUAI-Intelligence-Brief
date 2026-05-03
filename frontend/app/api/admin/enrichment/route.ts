import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import {
  readEnrichmentData,
  readEnrichmentHistory,
} from "@/lib/server/pipeline-runs";
import type { EnrichmentSummary } from "@/lib/types/enrichment";

/**
 * GET /api/admin/enrichment?date=YYYY-MM-DD&mode=single|history
 *
 * mode=single (default): Returns enrichment data for a single run date.
 * mode=history:          Returns aggregated summaries for all available dates.
 *
 * Data sources (tried in order):
 * 1. Local JSON artifacts (dev / self-hosted with ENABLE_LOCAL_PIPELINE_HYDRATION)
 * 2. Supabase gatekeeper_log column in pipeline_runs (production fallback)
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();

    const dateParam = request.nextUrl.searchParams.get("date");
    const mode = request.nextUrl.searchParams.get("mode") ?? "single";

    // Fetch available dates from pipeline_runs
    const { data: availableDates, error: datesErr } = await supabase
      .from("pipeline_runs")
      .select("run_date")
      .order("run_date", { ascending: false });

    if (datesErr) {
      return jsonError(datesErr.message, 500);
    }

    const dates = (availableDates ?? []).map(
      (d: Record<string, unknown>) => d.run_date as string
    );

    /* ── History mode ──────────────────────────────────────────────── */
    if (mode === "history") {
      // Try local files first
      let history = await readEnrichmentHistory();

      // Supabase fallback: read enrichment summaries from cost_breakdown
      if (history.length === 0) {
        const { data: rows } = await supabase
          .from("pipeline_runs")
          .select("run_date, cost_breakdown")
          .order("run_date", { ascending: true });

        if (rows) {
          history = rows.flatMap((row: Record<string, unknown>) => {
            const cb =
              row.cost_breakdown &&
              typeof row.cost_breakdown === "object" &&
              !Array.isArray(row.cost_breakdown)
                ? (row.cost_breakdown as Record<string, unknown>)
                : null;
            const enrichment = cb?.enrichment;
            if (
              !enrichment ||
              typeof enrichment !== "object" ||
              Array.isArray(enrichment)
            )
              return [];
            const e = enrichment as Record<string, unknown>;
            const summary: EnrichmentSummary = {
              total_items: (e.total_items as number) ?? 0,
              thin_items: (e.thin_items as number) ?? 0,
              enriched_successfully: (e.enriched_successfully as number) ?? 0,
              total_tokens_input: (e.total_tokens_input as number) ?? 0,
              total_tokens_output: (e.total_tokens_output as number) ?? 0,
              total_elapsed_seconds: (e.total_elapsed_seconds as number) ?? 0,
              final_source_breakdown:
                (e.final_source_breakdown as Record<string, number>) ?? {},
              avg_original_word_count:
                (e.avg_original_word_count as number) ?? 0,
              avg_enriched_word_count:
                (e.avg_enriched_word_count as number) ?? 0,
              avg_confidence_judge_1: 0,
              avg_confidence_judge_2: 0,
              research_agent_count: (e.research_agent_count as number) ?? 0,
              stage_entered: (e.stage_entered as Record<string, number>) ?? {},
              stage_resolved:
                (e.stage_resolved as Record<string, number>) ?? {},
            };
            return [{ date: row.run_date as string, summary }];
          });
        }
      }

      return jsonOk({ history, dates });
    }

    /* ── Single date mode ──────────────────────────────────────────── */
    const selectedDate = dateParam || dates[0] || "";

    if (!selectedDate) {
      return jsonOk({ summary: null, items: [], dates });
    }

    // Try local files first
    let enrichmentData = await readEnrichmentData(selectedDate);

    // Supabase fallback: read gatekeeper_log (enriched version) from pipeline_runs
    if (!enrichmentData) {
      const { data: row } = await supabase
        .from("pipeline_runs")
        .select("gatekeeper_log")
        .eq("run_date", selectedDate)
        .single();

      if (
        row?.gatekeeper_log &&
        typeof row.gatekeeper_log === "object" &&
        !Array.isArray(row.gatekeeper_log)
      ) {
        enrichmentData = await readEnrichmentData(
          selectedDate,
          row.gatekeeper_log as Record<string, unknown>
        );
      }
    }

    return jsonOk({
      summary: enrichmentData?.summary ?? null,
      items: enrichmentData?.items ?? [],
      dates,
    });
  } catch (err) {
    return handleRouteError(err, "admin/enrichment GET");
  }
}
