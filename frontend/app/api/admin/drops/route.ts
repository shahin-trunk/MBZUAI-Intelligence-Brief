import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

/**
 * GET /api/admin/drops?date=YYYY-MM-DD&stage=<stage>&source=<source>&search=<text>
 * Returns dropped items with optional filters, plus available run dates.
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();

    const date = request.nextUrl.searchParams.get("date");
    const stage = request.nextUrl.searchParams.get("stage");
    const source = request.nextUrl.searchParams.get("source");
    const search = request.nextUrl.searchParams.get("search");

    // Build filtered query for dropped_items
    let query = supabase.from("dropped_items").select("*");

    if (date) {
      query = query.eq("run_date", date);
    }
    if (stage && stage !== "all") {
      query = query.eq("dropped_at_stage", stage);
    }
    if (source && source !== "all") {
      query = query.eq("source_name", source);
    }
    if (search) {
      query = query.ilike("headline", `%${search}%`);
    }

    query = query.order("created_at", { ascending: false }).limit(100);

    const { data, error } = await query;

    if (error) {
      return jsonError(error.message, 500);
    }

    // Fetch distinct run dates for the date picker
    const { data: availableDates, error: datesErr } = await supabase
      .from("pipeline_runs")
      .select("run_date")
      .order("run_date", { ascending: false });

    if (datesErr) {
      return jsonError(datesErr.message, 500);
    }

    return jsonOk({
      items: data ?? [],
      dates: availableDates ?? [],
    });
  } catch (err) {
    return handleRouteError(err, "admin/drops GET");
  }
}
