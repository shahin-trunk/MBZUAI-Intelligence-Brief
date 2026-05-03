import { type NextRequest } from "next/server";
import {
  getAuthenticatedClient,
  handleRouteError,
  jsonOk,
  jsonError,
} from "@/lib/api/helpers";

function isMissingColumnError(error: { message?: string } | null, column: string): boolean {
  const message = error?.message ?? "";
  return (
    message.includes(`'${column}'`) ||
    message.includes(`"${column}"`) ||
    message.includes(`.${column} `) ||
    message.includes(` ${column} does not exist`) ||
    message.includes(`column ${column} does not exist`)
  );
}

/**
 * GET /api/read-status?brief_date=YYYY-MM-DD
 * Returns all item_ids the current user has read for the given brief date.
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const briefDate = request.nextUrl.searchParams.get("brief_date");

    if (!briefDate) {
      return jsonError("brief_date query parameter is required");
    }

    const { data, error } = await supabase
      .from("read_status")
      .select("item_id")
      .eq("user_id", user.id)
      .eq("brief_date", briefDate);

    if (error) {
      return jsonError(error.message, 500);
    }

    const readItems = (data ?? []).map((row) => row.item_id);
    return jsonOk({ readItems });
  } catch (err) {
    return handleRouteError(err, "read-status GET");
  }
}

/**
 * POST /api/read-status
 * Records that the user has expanded/read an item.
 * Upserts — if already exists, does nothing.
 * Body: { item_id, brief_date }
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const body = await request.json();
    const { item_id, brief_date } = body;

    if (!item_id || !brief_date) {
      return jsonError("item_id and brief_date are required");
    }

    const timestamp = new Date().toISOString();

    let { error } = await supabase.from("read_status").upsert(
      {
        user_id: user.id,
        item_id,
        brief_date,
        read_at: timestamp,
      },
      { onConflict: "user_id,item_id,brief_date", ignoreDuplicates: true }
    );

    if (error && isMissingColumnError(error, "read_at")) {
      ({ error } = await supabase.from("read_status").upsert(
        {
          user_id: user.id,
          item_id,
          brief_date,
          created_at: timestamp,
        },
        { onConflict: "user_id,item_id,brief_date", ignoreDuplicates: true }
      ));
    }

    if (error && isMissingColumnError(error, "created_at")) {
      ({ error } = await supabase.from("read_status").upsert(
        {
          user_id: user.id,
          item_id,
          brief_date,
        },
        { onConflict: "user_id,item_id,brief_date", ignoreDuplicates: true }
      ));
    }

    if (error) {
      console.error("read-status upsert error:", error.message);
      return jsonError(error.message, 500);
    }

    return jsonOk({ success: true });
  } catch (err) {
    return handleRouteError(err, "read-status POST");
  }
}
