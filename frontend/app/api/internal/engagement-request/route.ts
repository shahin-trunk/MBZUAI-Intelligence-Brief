import { type NextRequest } from "next/server";
import { getAuthenticatedClient } from "@/lib/api/helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

/**
 * POST /api/internal/engagement-request
 *
 * Any authenticated user. Sends a request to the strategy team
 * associated with an engagement.
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();

    const body = await request.json();
    const { engagementId, message } = body;

    if (!engagementId || !message?.trim()) {
      return jsonError("engagementId and message are required", 400);
    }

    // Verify engagement exists
    const { data: engagement, error: fetchErr } = await supabase
      .from("engagements")
      .select("id")
      .eq("id", engagementId)
      .single();

    if (fetchErr || !engagement) {
      return jsonError("Engagement not found", 404);
    }

    const { data, error } = await supabase
      .from("engagement_requests")
      .insert({
        engagement_id: engagementId,
        message: message.trim(),
        requested_by: user.id,
        status: "open",
      })
      .select()
      .single();

    if (error) {
      console.error("[engagement-request] DB insert failed:", error);
      return jsonError("Failed to save request", 500);
    }

    return jsonOk({ request: data }, 201);
  } catch (err) {
    return handleRouteError(err, "engagement-request POST");
  }
}
