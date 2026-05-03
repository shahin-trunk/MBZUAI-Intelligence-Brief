import "server-only";

import { createServiceClient } from "@/lib/supabase/server";
import type { EngagementMaterial } from "@/lib/types/executive-engagement";

const ENGAGEMENT_MATERIALS_BUCKET = "engagement-materials";
const DEFAULT_SIGNED_URL_TTL_SECONDS = 60 * 60;

type SupabaseServiceClient = ReturnType<typeof createServiceClient>;
type MaterialLike = Partial<EngagementMaterial> & {
  storage_path?: string | null;
};

function decodeStoragePath(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function getEngagementMaterialStoragePath(
  material: MaterialLike | null | undefined
): string | null {
  const directPath = material?.storage_path?.trim();
  if (directPath) {
    return directPath;
  }

  const rawUrl = material?.url?.trim();
  if (!rawUrl) {
    return null;
  }

  try {
    const url = new URL(rawUrl);
    const match = url.pathname.match(
      /\/storage\/v1\/object\/(?:public|sign)\/engagement-materials\/(.+)/
    );
    return match ? decodeStoragePath(match[1]) : null;
  } catch {
    return null;
  }
}

async function createSignedMaterialUrl(
  supabase: SupabaseServiceClient,
  storagePath: string
): Promise<string | null> {
  const { data, error } = await supabase.storage
    .from(ENGAGEMENT_MATERIALS_BUCKET)
    .createSignedUrl(storagePath, DEFAULT_SIGNED_URL_TTL_SECONDS);

  if (error) {
    console.warn(
      `[engagement-materials] Failed to sign ${storagePath}:`,
      error.message
    );
    return null;
  }

  return data.signedUrl;
}

export async function resolveEngagementMaterials(
  supabase: SupabaseServiceClient,
  materials: unknown
): Promise<EngagementMaterial[]> {
  const entries = Array.isArray(materials) ? materials : [];

  return Promise.all(
    entries.map(async (entry, index) => {
      const material =
        entry && typeof entry === "object" && !Array.isArray(entry)
          ? (entry as MaterialLike)
          : {};
      const storagePath = getEngagementMaterialStoragePath(material);
      const signedUrl = storagePath
        ? await createSignedMaterialUrl(supabase, storagePath)
        : null;

      return {
        id:
          typeof material.id === "string" && material.id.trim()
            ? material.id
            : `material-${index + 1}`,
        name:
          typeof material.name === "string" && material.name.trim()
            ? material.name
            : "Material",
        url:
          signedUrl ??
          (typeof material.url === "string" && material.url.trim()
            ? material.url
            : null),
        storage_path: storagePath,
        uploadedAt:
          typeof material.uploadedAt === "string" ? material.uploadedAt : "",
      };
    })
  );
}
