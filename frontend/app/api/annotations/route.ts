import { type NextRequest } from "next/server";
import {
  getAuthenticatedClient,
  handleRouteError,
  jsonOk,
  jsonError,
} from "@/lib/api/helpers";

/**
 * GET /api/annotations?brief_date=YYYY-MM-DD
 * Returns all annotations for the given brief date (RLS scopes by user).
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const briefDate = request.nextUrl.searchParams.get("brief_date");

    if (!briefDate) {
      return jsonError("brief_date query parameter is required");
    }

    const { data, error } = await supabase
      .from("annotations")
      .select("*")
      .eq("user_id", user.id)
      .eq("brief_date", briefDate)
      .order("created_at", { ascending: false });

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ annotations: data ?? [] });
  } catch (err) {
    return handleRouteError(err, "annotations GET");
  }
}

/**
 * POST /api/annotations
 * Creates a new annotation.
 * Body: { item_id, brief_date, note_text }
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const body = await request.json();
    const { item_id, brief_date, note_text } = body;

    if (!item_id || !brief_date || !note_text?.trim()) {
      return jsonError("item_id, brief_date, and note_text are required");
    }

    const { data, error } = await supabase
      .from("annotations")
      .insert({
        user_id: user.id,
        item_id,
        brief_date,
        note_text: note_text.trim(),
      })
      .select()
      .single();

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ annotation: data }, 201);
  } catch (err) {
    return handleRouteError(err, "annotations POST");
  }
}
