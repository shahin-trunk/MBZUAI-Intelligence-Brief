import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { hydratePipelineRun } from "@/lib/server/pipeline-runs";

interface RouteContext {
  params: Promise<{ date: string }>;
}

/**
 * GET /api/admin/pipeline/[date]
 * Returns the pipeline_runs row for the given date.
 */
export async function GET(_request: NextRequest, context: RouteContext) {
  try {
    const { supabase } = await getAdminClient();
    const { date } = await context.params;

    const { data, error } = await supabase
      .from("pipeline_runs")
      .select("*")
      .eq("run_date", date)
      .maybeSingle();

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ run: data ? await hydratePipelineRun(data) : null });
  } catch (err) {
    return handleRouteError(err, "admin/pipeline/[date] GET");
  }
}
