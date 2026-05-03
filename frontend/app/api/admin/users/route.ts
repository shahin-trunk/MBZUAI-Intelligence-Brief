import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

/**
 * GET /api/admin/users
 * Returns all user profiles ordered by creation date.
 */
export async function GET() {
  try {
    const { supabase } = await getAdminClient();

    const { data, error } = await supabase
      .from("user_profiles")
      .select("*")
      .order("created_at", { ascending: true });

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ users: data ?? [] });
  } catch (err) {
    return handleRouteError(err, "admin/users GET");
  }
}
