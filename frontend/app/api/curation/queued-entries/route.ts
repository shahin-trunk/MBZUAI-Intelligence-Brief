import { NextRequest } from "next/server";
import { getCurationClient } from "@/lib/api/curation-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

/**
 * GET /api/curation/queued-entries?brief_date=YYYY-MM-DD
 *
 * Returns all manual_entries with the given target_date and status=pending.
 * Used by the curation workspace to surface admin-queued items for import.
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase } = await getCurationClient();

    const briefDate = request.nextUrl.searchParams.get("brief_date");
    if (!briefDate) {
      return jsonError("brief_date query parameter is required", 400);
    }

    const { data, error } = await supabase
      .from("manual_entries")
      .select("*")
      .eq("target_date", briefDate)
      .eq("status", "pending")
      .order("created_at", { ascending: true });

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ entries: data ?? [] });
  } catch (err) {
    return handleRouteError(err, "curation/queued-entries GET");
  }
}
