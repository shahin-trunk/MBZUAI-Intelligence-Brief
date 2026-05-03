import { NextResponse } from "next/server";
import { createServiceClient } from "@/lib/supabase/server";

/**
 * Returns all entity logos. Cached aggressively — logos rarely change.
 * Client fetches once per brief load and caches in state.
 */
export async function GET() {
  const supabase = createServiceClient();

  const { data, error } = await supabase
    .from("entity_logos")
    .select("entity_name, logo_path, aliases, category");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // Build lookup: name → {logoUrl, category}, plus aliases.
  // Rows with a null/empty logo_path return { logoUrl: null } so the client
  // can skip straight to the category fallback without trying a bad URL.
  const logos: Record<string, { logoUrl: string | null; category: string }> = {};

  for (const row of data ?? []) {
    const path = typeof row.logo_path === "string" ? row.logo_path.trim() : "";
    const logoUrl = !path
      ? null
      : path.startsWith("http")
        ? path
        : `${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/entity-logos/${path}`;

    const entry = { logoUrl, category: row.category };

    logos[row.entity_name.toLowerCase()] = entry;

    for (const alias of row.aliases ?? []) {
      logos[alias.toLowerCase()] = entry;
    }
  }

  return NextResponse.json(
    { logos },
    { headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" } },
  );
}
