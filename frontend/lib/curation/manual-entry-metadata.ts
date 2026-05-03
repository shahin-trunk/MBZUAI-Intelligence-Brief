import type { ExhibitData } from "@/lib/types/brief";

const MANUAL_ENTRY_META_PREFIX = "__manual_entry_meta__:";
const LEGACY_EXHIBIT_IMAGE_RE = /\[exhibit_image:\s*(https?:\/\/[^\]]+)\]/i;

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function sanitizeExhibit(value: unknown): ExhibitData | null {
  if (!isRecord(value)) return null;

  const type = asString(value.type);
  const data = isRecord(value.data) ? value.data : null;
  const sourceImageUrl = asString(value.source_image_url);

  if (
    !type ||
    !data ||
    ![
      "benchmark_table",
      "comparison_table",
      "metric_highlight",
      "timeline",
      "raw_image",
    ].includes(type)
  ) {
    return null;
  }

  return {
    type: type as ExhibitData["type"],
    data,
    ...(sourceImageUrl ? { source_image_url: sourceImageUrl } : {}),
  };
}

function buildRawImageExhibit(imageUrl: string): ExhibitData {
  return {
    type: "raw_image",
    data: {
      image_url: imageUrl,
      caption: "",
    },
    source_image_url: imageUrl,
  };
}

export function buildManualEntryNotes({
  exhibit,
  imageUrl,
}: {
  exhibit?: ExhibitData | null;
  imageUrl?: string | null;
}): string | null {
  const safeExhibit = sanitizeExhibit(exhibit);
  const safeImageUrl = asString(imageUrl) ?? safeExhibit?.source_image_url ?? null;

  if (!safeExhibit && !safeImageUrl) return null;

  return `${MANUAL_ENTRY_META_PREFIX}${JSON.stringify({
    exhibit: safeExhibit,
    exhibit_image_url: safeImageUrl,
  })}`;
}

export function extractExhibitsFromManualEntryNotes(
  notes: string | null | undefined
): ExhibitData[] | null {
  const text = asString(notes);
  if (!text) return null;

  if (text.startsWith(MANUAL_ENTRY_META_PREFIX)) {
    const payload = text.slice(MANUAL_ENTRY_META_PREFIX.length);
    try {
      const parsed = JSON.parse(payload) as Record<string, unknown>;
      const exhibit = sanitizeExhibit(parsed.exhibit);
      if (exhibit) return [exhibit];

      const imageUrl = asString(parsed.exhibit_image_url);
      if (imageUrl) return [buildRawImageExhibit(imageUrl)];
    } catch {
      // Fall through to legacy parsing below.
    }
  }

  const legacyMatch = text.match(LEGACY_EXHIBIT_IMAGE_RE);
  const legacyImageUrl = asString(legacyMatch?.[1]);
  return legacyImageUrl ? [buildRawImageExhibit(legacyImageUrl)] : null;
}
