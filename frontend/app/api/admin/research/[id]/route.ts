import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * PATCH /api/admin/research/[id]
 * Updates a research request's status, assigned_to, or response.
 * Body: { status?, assigned_to?, response? }
 */
export async function PATCH(request: NextRequest, context: RouteContext) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await context.params;
    const body = await request.json();
    const { status, assigned_to, response } = body;

    // Build update payload
    const updateData: Record<string, unknown> = {};

    if (status !== undefined) {
      updateData.status = status;
    }
    if (assigned_to !== undefined) {
      updateData.assigned_to = assigned_to;
    }
    if (response !== undefined) {
      updateData.response = response;
    }

    // Keep completed_at in sync with the effective status.
    if (status === "completed") {
      updateData.completed_at = new Date().toISOString();
    } else if (status === "pending") {
      updateData.completed_at = null;
      updateData.response = null;
    } else if (status !== undefined) {
      updateData.completed_at = null;
    }

    if (Object.keys(updateData).length === 0) {
      return jsonError("No update fields provided");
    }

    const { data, error } = await supabase
      .from("research_requests")
      .update(updateData)
      .eq("id", id)
      .select()
      .maybeSingle();

    if (error) {
      return jsonError(error.message, 500);
    }

    if (!data) {
      return jsonError("Research request not found", 404);
    }

    return jsonOk({ request: data });
  } catch (err) {
    return handleRouteError(err, "admin/research/[id] PATCH");
  }
}

/**
 * DELETE /api/admin/research/[id]
 * Permanently deletes a research request.
 */
export async function DELETE(
  _request: NextRequest,
  context: RouteContext
) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await context.params;

    const { error } = await supabase
      .from("research_requests")
      .delete()
      .eq("id", id);

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ deleted: true });
  } catch (err) {
    return handleRouteError(err, "admin/research/[id] DELETE");
  }
}
