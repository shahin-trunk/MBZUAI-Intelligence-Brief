import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

/**
 * GET /api/admin/scout-analytics?days=30
 * Returns scout run log and entity hit summary.
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();
    const days = parseInt(request.nextUrl.searchParams.get("days") ?? "30", 10);
    const limit = Math.min(Math.max(days, 1), 365);

    // Calculate cutoff date
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - limit);
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    // Fetch run log
    const { data: runs, error: runsErr } = await supabase
      .from("scout_run_log")
      .select("*")
      .gte("run_date", cutoffStr)
      .order("run_date", { ascending: false });

    if (runsErr) return jsonError(runsErr.message, 500);

    // Fetch entity hit summary (names + last hit dates)
    const { data: entities, error: entErr } = await supabase
      .from("scout_entity_watchlist")
      .select("entity_name, priority, enabled, last_hit_date")
      .order("last_hit_date", { ascending: false, nullsFirst: false });

    if (entErr) return jsonError(entErr.message, 500);

    // Compute summary stats
    const runList = runs ?? [];
    const totalRuns = runList.length;
    const totalCost = runList.reduce((s, r) => s + Number(r.cost_usd || 0), 0);
    const avgCandidates = totalRuns > 0
      ? runList.reduce((s, r) => s + (r.candidates_returned || 0), 0) / totalRuns
      : 0;
    const avgCost = totalRuns > 0 ? totalCost / totalRuns : 0;

    return jsonOk({
      runs: runList,
      entities: entities ?? [],
      summary: {
        total_runs: totalRuns,
        total_cost: Math.round(totalCost * 100) / 100,
        avg_candidates: Math.round(avgCandidates * 10) / 10,
        avg_cost: Math.round(avgCost * 100) / 100,
      },
    });
  } catch (err) {
    return handleRouteError(err, "admin/scout-analytics GET");
  }
}
