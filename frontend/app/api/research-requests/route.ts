import { type NextRequest } from "next/server";
import {
  getAuthenticatedClient,
  handleRouteError,
  jsonOk,
  jsonError,
} from "@/lib/api/helpers";
import { sendResearchRequestEmail } from "@/lib/email/research-request";

/**
 * GET /api/research-requests?brief_date=YYYY-MM-DD
 * Returns all research requests for the given brief date (RLS scoped).
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const briefDate = request.nextUrl.searchParams.get("brief_date");

    if (!briefDate) {
      return jsonError("brief_date query parameter is required");
    }

    const { data, error } = await supabase
      .from("research_requests")
      .select("*")
      .eq("user_id", user.id)
      .eq("brief_date", briefDate)
      .order("created_at", { ascending: false });

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ requests: data ?? [] });
  } catch (err) {
    return handleRouteError(err, "research-requests GET");
  }
}

/**
 * POST /api/research-requests
 * Creates a new research request. Prevents duplicates for same user+item+date
 * with pending/in_progress status.
 * Body: { item_id, brief_date, request_note? }
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const body = await request.json();
    const { item_id, brief_date, request_note } = body;

    if (!item_id || !brief_date) {
      return jsonError("item_id and brief_date are required");
    }

    // Check for existing active request
    const { data: existing } = await supabase
      .from("research_requests")
      .select("id, status")
      .eq("user_id", user.id)
      .eq("item_id", item_id)
      .eq("brief_date", brief_date)
      .in("status", ["pending", "in_progress"])
      .maybeSingle();

    if (existing) {
      return jsonError(
        "A research request already exists for this item",
        409
      );
    }

    const { data, error } = await supabase
      .from("research_requests")
      .insert({
        user_id: user.id,
        item_id,
        brief_date,
        request_note: request_note?.trim() || null,
        status: "pending",
      })
      .select()
      .single();

    if (error) {
      return jsonError(error.message, 500);
    }

    try {
      await sendResearchRequestEmail(supabase, {
        itemId: item_id,
        briefDate: brief_date,
        requestNote: request_note?.trim() || null,
        userId: user.id,
      });
    } catch (err) {
      console.error("[research-requests] Email notification failed:", err);
    }

    return jsonOk({ request: data }, 201);
  } catch (err) {
    return handleRouteError(err, "research-requests POST");
  }
}
