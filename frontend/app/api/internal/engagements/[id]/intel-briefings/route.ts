import { type NextRequest } from "next/server";
import { getAuthenticatedClient } from "@/lib/api/helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

/**
 * GET /api/internal/engagements/[id]/intel-briefings
 *
 * Lightweight polling endpoint — returns just the intel_briefings column.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { supabase } = await getAuthenticatedClient();
    const { id } = await params;

    const { data, error } = await supabase
      .from("engagements")
      .select("intel_briefings")
      .eq("id", id)
      .single();

    if (error || !data) {
      return jsonError("Engagement not found", 404);
    }

    return jsonOk({ briefings: data.intel_briefings || [] });
  } catch (err) {
    return handleRouteError(err, "intel-briefings GET");
  }
}
