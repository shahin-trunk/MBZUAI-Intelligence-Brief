import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { isEntityLogoCategory } from "@/lib/constants/entity-logo-categories";
import {
  parseAliasesField,
  uploadLogoToBucket,
  validateLogoFile,
} from "./shared";

/**
 * GET /api/admin/logos
 * Returns all rows from entity_logos for the logo inventory page.
 */
export async function GET() {
  try {
    const { supabase } = await getAdminClient();

    const { data, error } = await supabase
      .from("entity_logos")
      .select("*")
      .order("category")
      .order("entity_name");

    if (error) return jsonError(error.message, 500);

    return jsonOk({ entities: data ?? [] });
  } catch (err) {
    return handleRouteError(err, "admin/logos GET");
  }
}

/**
 * POST /api/admin/logos
 * Admin-only. Creates a new entity_logos row. Accepts multipart/form-data:
 *   - entity_name (required, unique)
 *   - category (required, one of ENTITY_LOGO_CATEGORIES)
 *   - aliases (optional, comma-separated)
 *   - file (optional, image file <= 2MB)
 *
 * If `file` is present, it's uploaded to the entity-logos bucket first
 * (fail-fast before the DB insert) and the stored filename becomes the
 * new row's logo_path. If omitted, logo_path is left empty and the card
 * reader falls back to the category SVG.
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();

    const form = await request.formData();
    const entityNameRaw = form.get("entity_name");
    const categoryRaw = form.get("category");
    const aliasesRaw = form.get("aliases");
    const file = form.get("file");

    if (typeof entityNameRaw !== "string" || !entityNameRaw.trim()) {
      return jsonError("entity_name is required", 400);
    }
    if (typeof categoryRaw !== "string" || !isEntityLogoCategory(categoryRaw)) {
      return jsonError("category is required and must be a valid category", 400);
    }

    const entityName = entityNameRaw.trim();
    const category = categoryRaw;
    const aliases = parseAliasesField(
      typeof aliasesRaw === "string" ? aliasesRaw : null,
    );

    // Pre-flight uniqueness check so we can return a clean 409 instead of a
    // raw PG duplicate-key error message.
    const { data: existing, error: existingErr } = await supabase
      .from("entity_logos")
      .select("entity_name")
      .eq("entity_name", entityName)
      .maybeSingle();
    if (existingErr) {
      return jsonError(existingErr.message, 500);
    }
    if (existing) {
      return jsonError(`Entity "${entityName}" already exists`, 409);
    }

    let logoPath = "";
    if (file instanceof File && file.size > 0) {
      const fileError = validateLogoFile(file);
      if (fileError) {
        return jsonError(fileError.message, fileError.status);
      }
      const uploadResult = await uploadLogoToBucket(supabase, entityName, file);
      if (!uploadResult.ok) {
        return jsonError(uploadResult.message, uploadResult.status);
      }
      logoPath = uploadResult.filename;
    }

    const { data: inserted, error: insertErr } = await supabase
      .from("entity_logos")
      .insert({
        entity_name: entityName,
        logo_path: logoPath,
        category,
        aliases,
      })
      .select("*")
      .single();

    if (insertErr) {
      console.error("[admin/logos POST] insert failed:", insertErr);
      return jsonError(insertErr.message, 500);
    }

    return jsonOk({ entity: inserted }, 201);
  } catch (err) {
    return handleRouteError(err, "admin/logos POST");
  }
}
