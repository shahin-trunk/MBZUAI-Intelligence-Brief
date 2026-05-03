// Shared helpers for the admin logos routes (POST on this folder, PATCH +
// DELETE on [entityName]). Handles file validation, entity-name slugging,
// aliases parsing, and a guarded upload-to-bucket wrapper so both endpoints
// apply the same rules.

import type { SupabaseClient } from "@supabase/supabase-js";

export const ENTITY_LOGOS_BUCKET = "entity-logos";

export const ALLOWED_LOGO_MIME = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/svg+xml",
  "image/gif",
]);

export const MAX_LOGO_BYTES = 2 * 1024 * 1024; // 2 MB

/**
 * Convert an entity name into a safe, lowercase, ascii slug suitable for
 * storage filenames. Matches the existing convention: "Apple" -> "apple",
 * "South Korea" -> "south-korea". Strips leading/trailing dashes so we
 * never produce "-apple-.png".
 */
export function slugifyEntityName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Map an image mime type to the file extension we want stored. */
export function extForMime(mime: string): string {
  switch (mime) {
    case "image/svg+xml":
      return "svg";
    case "image/jpeg":
      return "jpg";
    case "image/png":
      return "png";
    case "image/webp":
      return "webp";
    case "image/gif":
      return "gif";
    default:
      return "bin";
  }
}

/**
 * Parse a comma-separated aliases string into a trimmed, deduped array.
 * Empty/whitespace-only entries are dropped. Ordering of first occurrence
 * is preserved.
 */
export function parseAliasesField(raw: string | null | undefined): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(",")) {
    const trimmed = part.trim();
    if (trimmed && !seen.has(trimmed)) {
      seen.add(trimmed);
      out.push(trimmed);
    }
  }
  return out;
}

export interface FileValidationError {
  status: number;
  message: string;
}

/**
 * Validate an uploaded logo file. Returns null on success or a
 * { status, message } error object on failure, which the caller should
 * pass straight into jsonError().
 */
export function validateLogoFile(file: File): FileValidationError | null {
  if (file.size === 0) {
    return { status: 400, message: "Uploaded file is empty" };
  }
  if (file.size > MAX_LOGO_BYTES) {
    return {
      status: 413,
      message: `File exceeds ${MAX_LOGO_BYTES / (1024 * 1024)}MB limit`,
    };
  }
  const mime = (file.type || "").toLowerCase();
  if (!ALLOWED_LOGO_MIME.has(mime)) {
    return {
      status: 415,
      message: `Unsupported file type: ${mime || "unknown"}. Allowed: png, jpeg, webp, svg, gif`,
    };
  }
  return null;
}

export interface UploadLogoResult {
  ok: true;
  filename: string;
}

export interface UploadLogoFailure {
  ok: false;
  status: number;
  message: string;
}

/**
 * Upload a validated logo file to the entity-logos bucket under
 * `{slug}.{ext}` with upsert=true, so repeated writes replace the file
 * rather than erroring. Returns the stored filename on success.
 */
export async function uploadLogoToBucket(
  supabase: SupabaseClient,
  entityName: string,
  file: File,
): Promise<UploadLogoResult | UploadLogoFailure> {
  const slug = slugifyEntityName(entityName);
  if (!slug) {
    return {
      ok: false,
      status: 400,
      message: "Entity name must contain at least one alphanumeric character",
    };
  }

  const ext = extForMime(file.type);
  const filename = `${slug}.${ext}`;
  const buffer = Buffer.from(await file.arrayBuffer());

  const { error: uploadErr } = await supabase.storage
    .from(ENTITY_LOGOS_BUCKET)
    .upload(filename, buffer, {
      contentType: file.type,
      upsert: true,
    });

  if (uploadErr) {
    console.error("[admin/logos] storage upload failed:", uploadErr);
    return {
      ok: false,
      status: 500,
      message: `Upload failed: ${uploadErr.message}`,
    };
  }

  return { ok: true, filename };
}
