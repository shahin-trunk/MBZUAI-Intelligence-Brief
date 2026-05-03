import { type NextRequest } from "next/server";
import {
  getAuthenticatedClient,
  handleRouteError,
  jsonOk,
  jsonError,
} from "@/lib/api/helpers";

/**
 * GET /api/flags?brief_date=YYYY-MM-DD
 * Returns all flags for the given brief date (RLS scopes by user).
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const briefDate = request.nextUrl.searchParams.get("brief_date");

    if (!briefDate) {
      return jsonError("brief_date query parameter is required");
    }

    const { data, error } = await supabase
      .from("flags")
      .select("*")
      .eq("user_id", user.id)
      .eq("brief_date", briefDate);

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ flags: data ?? [] });
  } catch (err) {
    return handleRouteError(err, "flags GET");
  }
}

/**
 * POST /api/flags
 * Toggle behavior: if flag exists (same user, item, date, type), delete it.
 * If not, create it.
 * Body: { item_id, brief_date, flag_type }
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const body = await request.json();
    const { item_id, brief_date, flag_type } = body;

    if (!item_id || !brief_date || !flag_type) {
      return jsonError("item_id, brief_date, and flag_type are required");
    }

    // Check if flag already exists
    const { data: existing } = await supabase
      .from("flags")
      .select("id")
      .eq("user_id", user.id)
      .eq("item_id", item_id)
      .eq("brief_date", brief_date)
      .eq("flag_type", flag_type)
      .maybeSingle();

    if (existing) {
      // Remove the flag
      const { error } = await supabase.from("flags").delete().eq("id", existing.id);
      if (error) {
        return jsonError(error.message, 500);
      }
      return jsonOk({ flag: null, action: "removed" });
    }

    // Create the flag
    const { data, error } = await supabase
      .from("flags")
      .insert({
        user_id: user.id,
        item_id,
        brief_date,
        flag_type,
      })
      .select()
      .single();

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ flag: data, action: "created" }, 201);
  } catch (err) {
    return handleRouteError(err, "flags POST");
  }
}
