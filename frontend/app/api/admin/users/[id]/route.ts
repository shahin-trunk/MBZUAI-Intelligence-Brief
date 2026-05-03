import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

interface RouteContext {
  params: Promise<{ id: string }>;
}

const ALLOWED_ROLES = ["reader", "editor", "analyst", "admin"] as const;

/**
 * PATCH /api/admin/users/[id]
 * Updates a user's role.
 * Body: { role: "reader" | "editor" | "analyst" | "admin" }
 */
export async function PATCH(request: NextRequest, context: RouteContext) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await context.params;
    const body = await request.json();
    const { role } = body;

    // Validate role
    if (!role || !ALLOWED_ROLES.includes(role)) {
      return jsonError(
        `Invalid role. Must be one of: ${ALLOWED_ROLES.join(", ")}`
      );
    }

    const { data, error } = await supabase
      .from("user_profiles")
      .update({ role })
      .eq("id", id)
      .select()
      .maybeSingle();

    if (error) {
      return jsonError(error.message, 500);
    }

    if (!data) {
      return jsonError("User not found", 404);
    }

    return jsonOk({ user: data });
  } catch (err) {
    return handleRouteError(err, "admin/users/[id] PATCH");
  }
}
