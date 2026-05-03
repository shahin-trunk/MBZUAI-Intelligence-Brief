import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import {
  getEngagementMaterialStoragePath,
  resolveEngagementMaterials,
} from "@/lib/server/engagement-materials";

/**
 * POST /api/internal/engagements/[id]/materials
 *
 * Admin-only. Upload a file to the engagement-materials storage bucket
 * and append its metadata to the engagement's materials JSONB column.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await params;

    const formData = await request.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return jsonError("file is required", 400);
    }

    if (file.size > 10 * 1024 * 1024) {
      return jsonError("File must be under 10MB", 400);
    }

    // Fetch current engagement
    const { data: eng, error: fetchErr } = await supabase
      .from("engagements")
      .select("materials")
      .eq("id", id)
      .maybeSingle();

    if (fetchErr || !eng) {
      return jsonError("Engagement not found", 404);
    }

    // Upload to storage
    const timestamp = Date.now();
    const storagePath = `${id}/${timestamp}-${file.name}`;
    const fileBuffer = Buffer.from(await file.arrayBuffer());

    const { error: uploadErr } = await supabase.storage
      .from("engagement-materials")
      .upload(storagePath, fileBuffer, {
        contentType: file.type || "application/octet-stream",
      });

    if (uploadErr) {
      console.error("[materials POST] upload failed:", uploadErr);
      return jsonError(`Upload failed: ${uploadErr.message}`, 500);
    }

    // Append to materials array
    const materials = Array.isArray(eng.materials) ? eng.materials : [];
    const newMaterial = {
      id: `mat-${timestamp}`,
      name: file.name,
      url: null,
      storage_path: storagePath,
      uploadedAt: new Date().toISOString(),
    };

    const { data, error: updateErr } = await supabase
      .from("engagements")
      .update({ materials: [...materials, newMaterial] })
      .eq("id", id)
      .select()
      .maybeSingle();

    if (updateErr) {
      console.error("[materials POST] DB update failed:", updateErr);
      return jsonError("Failed to update materials list", 500);
    }
    if (!data) {
      return jsonError("Engagement not found", 404);
    }

    const [resolvedMaterial] = await resolveEngagementMaterials(supabase, [
      newMaterial,
    ]);

    return jsonOk(
      {
        engagement: {
          ...data,
          materials: await resolveEngagementMaterials(supabase, data.materials),
        },
        material: resolvedMaterial ?? newMaterial,
      },
      201
    );
  } catch (err) {
    return handleRouteError(err, "engagements/[id]/materials POST");
  }
}

/**
 * DELETE /api/internal/engagements/[id]/materials
 *
 * Admin-only. Remove a material from the engagement.
 * Body: { materialId: string }
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await params;

    const body = await request.json();
    const { materialId } = body;

    if (!materialId) {
      return jsonError("materialId is required", 400);
    }

    // Fetch current engagement
    const { data: eng, error: fetchErr } = await supabase
      .from("engagements")
      .select("materials")
      .eq("id", id)
      .maybeSingle();

    if (fetchErr || !eng) {
      return jsonError("Engagement not found", 404);
    }

    const materials = Array.isArray(eng.materials) ? eng.materials : [];
    interface MaterialEntry {
      id: string;
      name: string;
      url: string | null;
      storage_path?: string | null;
      uploadedAt: string;
    }
    const toRemove = materials.find(
      (m: MaterialEntry) => m.id === materialId
    ) as MaterialEntry | undefined;

    if (!toRemove) {
      return jsonError("Material not found", 404);
    }

    const storagePath = getEngagementMaterialStoragePath(toRemove);
    if (storagePath) {
      try {
        await supabase.storage
          .from("engagement-materials")
          .remove([storagePath]);
      } catch {
        // Non-fatal — file may already be removed
      }
    }

    // Update materials array
    const updated = materials.filter(
      (m: MaterialEntry) => m.id !== materialId
    );
    const { data, error: updateErr } = await supabase
      .from("engagements")
      .update({ materials: updated })
      .eq("id", id)
      .select()
      .maybeSingle();

    if (updateErr) {
      console.error("[materials DELETE] DB update failed:", updateErr);
      return jsonError("Failed to update materials list", 500);
    }
    if (!data) {
      return jsonError("Engagement not found", 404);
    }

    return jsonOk({
      engagement: {
        ...data,
        materials: await resolveEngagementMaterials(supabase, data.materials),
      },
    });
  } catch (err) {
    return handleRouteError(err, "engagements/[id]/materials DELETE");
  }
}
