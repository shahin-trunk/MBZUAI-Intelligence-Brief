import { getAuthenticatedClient, handleRouteError, jsonError, jsonOk } from "@/lib/api/helpers";
import { createServiceClient } from "@/lib/supabase/server";
import { type NextRequest } from "next/server";

/**
 * GET /api/audio-status?date=YYYY-MM-DD
 *
 * Lightweight polling endpoint for audio generation progress + the
 * playable assets. The web portal renders brief audio via a server
 * component that reads the `briefs` row directly; non-Next consumers
 * (mobile clients through `intelligence-brief-backend`) rely on this
 * route as the single source of truth for every audio-adjacent field.
 *
 * `audio_segments` is the per-item time map (`{item_id, start, end}[]`),
 * required for card-scroll → audio-seek on mobile.
 */
export async function GET(request: NextRequest) {
  try {
    await getAuthenticatedClient();

    const date = request.nextUrl.searchParams.get("date");
    if (!date) return jsonError("date query parameter is required", 400);

    const supabase = createServiceClient();

    const { data, error } = await supabase
      .from("briefs")
      .select(
        "audio_status, audio_url",
      )
      .eq("brief_date", date)
      .maybeSingle();

    if (error) return jsonError(error.message, 500);
    if (!data) return jsonError("Brief not found", 404);

    return jsonOk({
      audio_status: data.audio_status ?? null,
      audio_url: data.audio_url ?? null,
    });
  } catch (err) {
    return handleRouteError(err, "audio-status GET");
  }
}
