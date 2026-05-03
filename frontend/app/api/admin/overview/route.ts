import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { getDubaiDateString } from "@/lib/dubai-time";
import { hydratePipelineRun } from "@/lib/server/pipeline-runs";

/**
 * GET /api/admin/overview
 * Returns dashboard overview: latest pipeline run, pending research count,
 * and today's flag count.
 */
export async function GET() {
  try {
    const { supabase } = await getAdminClient();

    // Latest pipeline run
    const { data: run, error: runErr } = await supabase
      .from("pipeline_runs")
      .select("*")
      .order("run_date", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (runErr) {
      return jsonError(runErr.message, 500);
    }

    // Pending research requests (all users)
    const { count: pendingResearch, error: resErr } = await supabase
      .from("research_requests")
      .select("id", { count: "exact", head: true })
      .eq("status", "pending");

    if (resErr) {
      return jsonError(resErr.message, 500);
    }

    // Flags for today
    const todayStr = getDubaiDateString();
    const { count: todayFlags, error: flagErr } = await supabase
      .from("flags")
      .select("id", { count: "exact", head: true })
      .eq("brief_date", todayStr);

    if (flagErr) {
      return jsonError(flagErr.message, 500);
    }

    return jsonOk({
      run: run ? await hydratePipelineRun(run) : null,
      pendingResearch: pendingResearch ?? 0,
      todayFlags: todayFlags ?? 0,
    });
  } catch (err) {
    return handleRouteError(err, "admin/overview GET");
  }
}
