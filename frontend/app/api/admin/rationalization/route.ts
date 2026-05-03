import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { readRationalizationData } from "@/lib/server/pipeline-runs";

/**
 * GET /api/admin/rationalization?date=YYYY-MM-DD
 *
 * Returns brief rationalization data for a single run date.
 *
 * Data sources (tried in order):
 * 1. Local JSON artifact (dev / self-hosted with ENABLE_LOCAL_PIPELINE_HYDRATION)
 * 2. Supabase cost_breakdown.rationalization in pipeline_runs (production fallback)
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();

    const dateParam = request.nextUrl.searchParams.get("date");

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

    const selectedDate = dateParam || dates[0] || "";

    if (!selectedDate) {
      return jsonOk({ data: null, dates });
    }

    // Try local file first
    let data = await readRationalizationData(selectedDate);

    // Supabase fallback: read from cost_breakdown.rationalization
    if (!data) {
      const { data: row } = await supabase
        .from("pipeline_runs")
        .select("cost_breakdown")
        .eq("run_date", selectedDate)
        .single();

      if (row?.cost_breakdown && typeof row.cost_breakdown === "object") {
        const cb = row.cost_breakdown as Record<string, unknown>;
        if (cb.rationalization && typeof cb.rationalization === "object") {
          data = cb.rationalization as Record<string, unknown>;
        }
      }
    }

    return jsonOk({ data: data ?? null, dates });
  } catch (err) {
    return handleRouteError(err, "admin/rationalization GET");
  }
}
