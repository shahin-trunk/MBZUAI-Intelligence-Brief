import { type NextRequest } from "next/server";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";

const VALID_SECTIONS = [
  "UAE",
  "Regional Research & Academic Events",
  "International Politics & Policy",
  "International Business & Technology",
  "Model Releases & Technical Developments",
];

/**
 * GET /api/admin/manual-entries
 * Returns all manual entries, ordered by created_at desc.
 */
export async function GET() {
  try {
    const { supabase } = await getAdminClient();

    const { data, error } = await supabase
      .from("manual_entries")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ entries: data ?? [] });
  } catch (err) {
    return handleRouteError(err, "admin/manual-entries GET");
  }
}

/**
 * POST /api/admin/manual-entries
 * Insert a new manual entry.
 * Body: { source_url, summary?, headline?, brief_section?, notes?, target_date }
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await getAdminClient();
    const body = await request.json();

    const { headline, summary, source_url, brief_section, notes, target_date } =
      body;

    if (!source_url || typeof source_url !== "string" || !source_url.trim()) {
      return jsonError("Source URL is required", 400);
    }
    if (!target_date) {
      return jsonError("target_date is required", 400);
    }
    if (brief_section && !VALID_SECTIONS.includes(brief_section)) {
      return jsonError(
        `brief_section must be one of: ${VALID_SECTIONS.join(", ")}`,
        400
      );
    }

    const { data, error } = await supabase
      .from("manual_entries")
      .insert({
        headline: headline?.trim() || "",
        summary: summary?.trim() ?? "",
        source_url: source_url.trim(),
        brief_section: brief_section || "",
        notes: notes?.trim() || null,
        target_date,
        created_by: user.email,
      })
      .select()
      .single();

    if (error) {
      return jsonError(error.message, 500);
    }

    return jsonOk({ entry: data }, 201);
  } catch (err) {
    return handleRouteError(err, "admin/manual-entries POST");
  }
}
