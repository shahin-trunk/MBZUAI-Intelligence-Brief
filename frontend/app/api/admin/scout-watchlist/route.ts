import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

/**
 * GET /api/admin/scout-watchlist
 * Returns all entities from the scout_entity_watchlist table.
 */
export async function GET() {
  try {
    const { supabase } = await getAdminClient();

    const { data, error } = await supabase
      .from("scout_entity_watchlist")
      .select("*")
      .order("priority", { ascending: true })
      .order("entity_name");

    if (error) return jsonError(error.message, 500);

    return jsonOk({ entities: data ?? [] });
  } catch (err) {
    return handleRouteError(err, "admin/scout-watchlist GET");
  }
}

/**
 * POST /api/admin/scout-watchlist
 * Insert a new entity into the watchlist.
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();
    const body = await request.json();

    if (!body.entity_name?.trim()) {
      return jsonError("entity_name is required", 400);
    }

    const row = {
      entity_name: body.entity_name.trim(),
      aliases: body.aliases ?? [],
      priority: body.priority === "high" ? "high" : "standard",
      notes: body.notes?.trim() || null,
      enabled: body.enabled !== false,
    };

    const { data, error } = await supabase
      .from("scout_entity_watchlist")
      .insert(row)
      .select()
      .single();

    if (error) return jsonError(error.message, 500);

    return jsonOk({ entity: data }, 201);
  } catch (err) {
    return handleRouteError(err, "admin/scout-watchlist POST");
  }
}

/**
 * PUT /api/admin/scout-watchlist?id=<uuid>
 * Update an existing entity (partial update).
 */
export async function PUT(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();
    const id = request.nextUrl.searchParams.get("id");

    if (!id) return jsonError("id query param required", 400);

    const body = await request.json();
    const updates: Record<string, unknown> = {};

    if (body.entity_name !== undefined) updates.entity_name = body.entity_name.trim();
    if (body.aliases !== undefined) updates.aliases = body.aliases;
    if (body.priority !== undefined) updates.priority = body.priority === "high" ? "high" : "standard";
    if (body.notes !== undefined) updates.notes = body.notes?.trim() || null;
    if (body.enabled !== undefined) updates.enabled = body.enabled;

    if (Object.keys(updates).length === 0) {
      return jsonError("No fields to update", 400);
    }

    const { data, error } = await supabase
      .from("scout_entity_watchlist")
      .update(updates)
      .eq("id", id)
      .select()
      .single();

    if (error) return jsonError(error.message, 500);

    return jsonOk({ entity: data });
  } catch (err) {
    return handleRouteError(err, "admin/scout-watchlist PUT");
  }
}

/**
 * DELETE /api/admin/scout-watchlist?id=<uuid>
 * Delete an entity from the watchlist.
 */
export async function DELETE(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();
    const id = request.nextUrl.searchParams.get("id");

    if (!id) return jsonError("id query param required", 400);

    const { error } = await supabase
      .from("scout_entity_watchlist")
      .delete()
      .eq("id", id);

    if (error) return jsonError(error.message, 500);

    return jsonOk({ deleted: true });
  } catch (err) {
    return handleRouteError(err, "admin/scout-watchlist DELETE");
  }
}
