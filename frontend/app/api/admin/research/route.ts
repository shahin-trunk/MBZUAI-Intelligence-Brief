import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

const ALLOWED_STATUSES = new Set([
  "all",
  "pending",
  "in_progress",
  "completed",
  "dismissed",
]);

/**
 * GET /api/admin/research
 * Returns all research requests enriched with user display names
 * and brief item headlines.
 */
export async function GET() {
  try {
    const { supabase } = await getAdminClient();

    // Fetch all research requests
    const { data: requests, error: reqErr } = await supabase
      .from("research_requests")
      .select("*")
      .order("created_at", { ascending: false });

    if (reqErr) {
      return jsonError(reqErr.message, 500);
    }

    if (!requests || requests.length === 0) {
      return jsonOk({ requests: [] });
    }

    // Collect unique user_ids and item_ids for enrichment
    const userIds = [...new Set(requests.map((r) => r.user_id).filter(Boolean))];
    const itemIds = [...new Set(requests.map((r) => r.item_id).filter(Boolean))];

    // Fetch user display names
    let userMap: Record<string, string> = {};
    if (userIds.length > 0) {
      const { data: users } = await supabase
        .from("user_profiles")
        .select("id, display_name")
        .in("id", userIds);

      if (users) {
        userMap = Object.fromEntries(
          users.map((u) => [u.id, u.display_name])
        );
      }
    }

    // Fetch brief item headlines
    let itemMap: Record<string, string> = {};
    if (itemIds.length > 0) {
      const { data: items } = await supabase
        .from("brief_items")
        .select("item_id, headline")
        .in("item_id", itemIds);

      if (items) {
        itemMap = Object.fromEntries(
          items.map((i) => [i.item_id, i.headline])
        );
      }
    }

    // Enrich requests with display names and headlines
    const enrichedRequests = requests.map((r) => ({
      ...r,
      user_display_name: userMap[r.user_id] ?? null,
      item_headline: r.item_id ? (itemMap[r.item_id] ?? null) : null,
    }));

    return jsonOk({ requests: enrichedRequests });
  } catch (err) {
    return handleRouteError(err, "admin/research GET");
  }
}

/**
 * DELETE /api/admin/research?status=<status|all>
 * Permanently deletes research requests matching the current filter.
 */
export async function DELETE(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();
    const status = request.nextUrl.searchParams.get("status") ?? "all";

    if (!ALLOWED_STATUSES.has(status)) {
      return jsonError("Invalid status filter", 400);
    }

    let idQuery = supabase.from("research_requests").select("id");
    if (status !== "all") {
      idQuery = idQuery.eq("status", status);
    }

    const { data: rows, error: rowsError } = await idQuery;
    if (rowsError) {
      return jsonError(rowsError.message, 500);
    }

    const ids = (rows ?? []).map((row) => row.id);
    if (ids.length === 0) {
      return jsonOk({ deleted: true, deletedCount: 0 });
    }

    const { error } = await supabase
      .from("research_requests")
      .delete()
      .in("id", ids);

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ deleted: true, deletedCount: ids.length });
  } catch (err) {
    return handleRouteError(err, "admin/research DELETE");
  }
}
