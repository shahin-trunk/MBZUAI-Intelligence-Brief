import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * PATCH /api/admin/manual-entries/[id]
 * Update status to 'cancelled'.
 */
export async function PATCH(request: NextRequest, context: RouteContext) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await context.params;
    const body = await request.json();
    const { status } = body;

    if (status !== "cancelled") {
      return jsonError("Only status='cancelled' is allowed", 400);
    }

    const { data, error } = await supabase
      .from("manual_entries")
      .update({ status: "cancelled" })
      .eq("id", id)
      .select()
      .maybeSingle();

    if (error) {
      return jsonError(error.message, 500);
    }
    if (!data) {
      return jsonError("Entry not found", 404);
    }

    return jsonOk({ entry: data });
  } catch (err) {
    return handleRouteError(err, "admin/manual-entries/[id] PATCH");
  }
}

/**
 * DELETE /api/admin/manual-entries/[id]
 * Hard delete a manual entry.
 */
export async function DELETE(
  _request: NextRequest,
  context: RouteContext
) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await context.params;

    const { error } = await supabase
      .from("manual_entries")
      .delete()
      .eq("id", id);

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ deleted: true });
  } catch (err) {
    return handleRouteError(err, "admin/manual-entries/[id] DELETE");
  }
}
