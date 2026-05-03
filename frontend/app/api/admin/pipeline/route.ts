import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { hydratePipelineRuns } from "@/lib/server/pipeline-runs";

/**
 * GET /api/admin/pipeline?range=7|14|30|all
 * Returns pipeline runs ordered by run_date DESC.
 * If range is a number, limits to that many rows. If "all", no limit.
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();

    const range = request.nextUrl.searchParams.get("range") ?? "7";

    let query = supabase
      .from("pipeline_runs")
      .select("*")
      .order("run_date", { ascending: false });

    if (range !== "all") {
      const limit = parseInt(range, 10);
      if (!isNaN(limit) && limit > 0) {
        query = query.limit(limit);
      }
    }

    const { data, error } = await query;

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ runs: await hydratePipelineRuns((data ?? []) as Record<string, unknown>[]) });
  } catch (err) {
    return handleRouteError(err, "admin/pipeline GET");
  }
}
