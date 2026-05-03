import { type NextRequest } from "next/server";
import {
  getAuthenticatedClient,
  handleRouteError,
  jsonOk,
  jsonError,
} from "@/lib/api/helpers";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * PATCH /api/annotations/[id]
 * Updates an annotation's note_text.
 * Body: { note_text }
 */
export async function PATCH(request: NextRequest, context: RouteContext) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const { id } = await context.params;
    const body = await request.json();
    const { note_text } = body;

    if (!note_text?.trim()) {
      return jsonError("note_text is required");
    }

    const { data, error } = await supabase
      .from("annotations")
      .update({
        note_text: note_text.trim(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", id)
      .eq("user_id", user.id)
      .select()
      .maybeSingle();

    if (error) {
      return jsonError(error.message, 500);
    }

    if (!data) {
      return jsonError("Annotation not found", 404);
    }

    return jsonOk({ annotation: data });
  } catch (err) {
    return handleRouteError(err, "annotations/[id] PATCH");
  }
}

/**
 * DELETE /api/annotations/[id]
 * Deletes an annotation (RLS enforces ownership).
 */
export async function DELETE(_request: NextRequest, context: RouteContext) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const { id } = await context.params;

    const { error } = await supabase
      .from("annotations")
      .delete()
      .eq("id", id)
      .eq("user_id", user.id);

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ success: true });
  } catch (err) {
    return handleRouteError(err, "annotations/[id] DELETE");
  }
}
