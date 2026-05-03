import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { isEntityLogoCategory } from "@/lib/constants/entity-logo-categories";
import {
  ENTITY_LOGOS_BUCKET,
  parseAliasesField,
  uploadLogoToBucket,
  validateLogoFile,
} from "../shared";

/**
 * PATCH /api/admin/logos/[entityName]
 * Admin-only. Updates an existing entity_logos row. Accepts multipart/form-data:
 *   - category (optional, one of ENTITY_LOGO_CATEGORIES)
 *   - aliases (optional, comma-separated — pass empty string to clear)
 *   - file (optional, image file <= 2MB — replaces the current logo)
 *
 * Entity name is immutable through this endpoint — renames happen via
 * delete + re-create. If no fields are provided, returns 400.
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ entityName: string }> },
) {
  try {
    const { supabase } = await getAdminClient();
    const { entityName: encoded } = await params;
    const entityName = decodeURIComponent(encoded);

    // Confirm the row exists — we want 404 rather than a silent no-op update.
    const { data: existing, error: existingErr } = await supabase
      .from("entity_logos")
      .select("entity_name")
      .eq("entity_name", entityName)
      .maybeSingle();
    if (existingErr) return jsonError(existingErr.message, 500);
    if (!existing) return jsonError(`Entity "${entityName}" not found`, 404);

    const form = await request.formData();
    const categoryRaw = form.get("category");
    const aliasesRaw = form.get("aliases");
    const file = form.get("file");

    const updatePayload: Record<string, unknown> = {};

    if (typeof categoryRaw === "string") {
      if (!isEntityLogoCategory(categoryRaw)) {
        return jsonError(`Invalid category: ${categoryRaw}`, 400);
      }
      updatePayload.category = categoryRaw;
    }

    if (typeof aliasesRaw === "string") {
      // Present-but-empty means "clear the aliases".
      updatePayload.aliases = parseAliasesField(aliasesRaw);
    }

    if (file instanceof File && file.size > 0) {
      const fileError = validateLogoFile(file);
      if (fileError) {
        return jsonError(fileError.message, fileError.status);
      }
      const uploadResult = await uploadLogoToBucket(supabase, entityName, file);
      if (!uploadResult.ok) {
        return jsonError(uploadResult.message, uploadResult.status);
      }
      updatePayload.logo_path = uploadResult.filename;
    }

    if (Object.keys(updatePayload).length === 0) {
      return jsonError("No fields to update", 400);
    }

    // Bump updated_at explicitly so the admin grid can show fresh mtimes.
    updatePayload.updated_at = new Date().toISOString();

    const { data: updated, error: updateErr } = await supabase
      .from("entity_logos")
      .update(updatePayload)
      .eq("entity_name", entityName)
      .select("*")
      .single();

    if (updateErr) {
      console.error("[admin/logos PATCH] update failed:", updateErr);
      return jsonError(updateErr.message, 500);
    }

    return jsonOk({ entity: updated });
  } catch (err) {
    return handleRouteError(err, "admin/logos PATCH");
  }
}

/**
 * DELETE /api/admin/logos/[entityName]
 * Admin-only. Removes the entity_logos row and its storage file.
 */
export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ entityName: string }> },
) {
  try {
    const { supabase } = await getAdminClient();
    const { entityName: encoded } = await params;
    const entityName = decodeURIComponent(encoded);

    // Fetch the row first so we know which storage file to clean up.
    const { data: deleted, error: deleteErr } = await supabase
      .from("entity_logos")
      .delete()
      .eq("entity_name", entityName)
      .select("entity_name, logo_path")
      .maybeSingle();

    if (deleteErr) {
      console.error("[admin/logos DELETE] delete failed:", deleteErr);
      return jsonError(deleteErr.message, 500);
    }
    if (!deleted) {
      return jsonError(`Entity "${entityName}" not found`, 404);
    }

    // Remove the storage file if one exists. Non-fatal — the row is
    // already gone, so a storage failure just leaves an orphan.
    const logoPath = deleted.logo_path;
    if (logoPath && !logoPath.startsWith("http") && !logoPath.startsWith("fallback")) {
      try {
        await supabase.storage.from(ENTITY_LOGOS_BUCKET).remove([logoPath]);
      } catch {
        // Non-fatal — file may already be removed or path was invalid.
      }
    }

    return jsonOk({ ok: true, deleted: deleted.entity_name });
  } catch (err) {
    return handleRouteError(err, "admin/logos DELETE");
  }
}
