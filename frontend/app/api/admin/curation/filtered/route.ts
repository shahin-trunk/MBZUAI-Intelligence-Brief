import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

/**
 * GET /api/admin/curation/filtered?date=YYYY-MM-DD
 *
 * Returns all `dropped_items` for a given brief date, grouped by stage.
 * Used by the Filtered Candidates panel on the curation workspace so curators
 * can see items that the pipeline dropped in any stage — including the
 * silent drops we surface as part of Phase 1 (triage, previous-brief
 * overlap, post-Gatekeeper overlap, Gatekeeper implicit).
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();

    const date = request.nextUrl.searchParams.get("date");
    if (!date) {
      return jsonError("date query parameter is required", 400);
    }

    const { data, error } = await supabase
      .from("dropped_items")
      .select(
        "id, run_date, headline, source_name, source_url, dropped_at_stage, drop_reason, composite_score, created_at",
      )
      .eq("run_date", date)
      .order("dropped_at_stage", { ascending: true })
      .order("composite_score", { ascending: false, nullsFirst: false })
      .order("created_at", { ascending: false });

    if (error) {
      return jsonError(error.message, 500);
    }

    // Group by stage for the panel UI.
    const byStage: Record<string, typeof data> = {};
    for (const row of data ?? []) {
      const stage = row.dropped_at_stage ?? "unknown";
      if (!byStage[stage]) byStage[stage] = [];
      byStage[stage].push(row);
    }

    return jsonOk({
      date,
      total: data?.length ?? 0,
      byStage,
      items: data ?? [],
    });
  } catch (err) {
    return handleRouteError(err, "admin/curation/filtered GET");
  }
}
