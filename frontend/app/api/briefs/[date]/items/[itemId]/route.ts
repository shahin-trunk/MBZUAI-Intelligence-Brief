import { NextRequest, NextResponse } from "next/server";
import { revalidatePath } from "next/cache";
import { getCurationClient } from "@/lib/api/curation-helpers";
import { handleRouteError } from "@/lib/api/helpers";
import type { RawPipelineBrief, RawPipelineItem } from "@/lib/types/brief";

type Params = { params: Promise<{ date: string; itemId: string }> };

function serializeDiffValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

// v2-only editable surface. Legacy v1 fields (main_bullet, context,
// implication) are server-derived from v2 — never accepted from the
// request body. Keeps the drawer reader (which reads analysis) in sync
// with what analysts edit.
const EDITABLE_FIELDS = [
  "headline",
  "key_bullets",
  "analysis",
  "primary_entity",
  "primary_entity_category",
  "section",
  "exhibits",
  "significance_level",
] as const;

function revalidateBrief(briefDate: string) {
  revalidatePath("/brief/today");
  revalidatePath(`/brief/${briefDate}`);
  revalidatePath("/brief/[date]");
}

async function loadBriefRawJson(
  supabase: Awaited<ReturnType<typeof getCurationClient>>["supabase"],
  briefDate: string
) {
  const { data, error } = await supabase
    .from("briefs")
    .select("raw_json")
    .eq("brief_date", briefDate)
    .maybeSingle();

  if (error) throw NextResponse.json({ error: error.message }, { status: 500 });
  if (!data) throw NextResponse.json({ error: "Brief not found" }, { status: 404 });

  return data.raw_json as RawPipelineBrief;
}

function rebuildMetadata(rawBrief: RawPipelineBrief) {
  const items = rawBrief.items.filter(
    (i) => !i.is_placeholder && i.depth !== "placeholder"
  );
  const sectionCounts: Record<string, number> = {};
  for (const item of items) {
    sectionCounts[item.section] = (sectionCounts[item.section] ?? 0) + 1;
  }
  rawBrief.brief_metadata.total_items = items.length;
  rawBrief.brief_metadata.section_counts = sectionCounts;
  if (items.length > 0) {
    rawBrief.brief_metadata.lead_story_id = items[0].id;
  }
}

// ─── PUT: Edit a published brief item ────────────────────────────────────────

export async function PUT(request: NextRequest, { params }: Params) {
  try {
    const { supabase, user } = await getCurationClient();
    const { date: briefDate, itemId } = await params;
    const body = await request.json();

    const rawBrief = await loadBriefRawJson(supabase, briefDate);
    const itemIndex = rawBrief.items.findIndex((i) => i.id === itemId);
    if (itemIndex === -1) {
      return NextResponse.json({ error: "Item not found in brief" }, { status: 404 });
    }

    const currentItem = rawBrief.items[itemIndex];
    const snapshot = { ...currentItem };

    // Build update + diff
    const editFields: Record<string, { before: string; after: string }> = {};
    let changed = false;

    for (const field of EDITABLE_FIELDS) {
      if (body[field] !== undefined) {
        const current = currentItem[field as keyof RawPipelineItem];
        if (JSON.stringify(body[field]) !== JSON.stringify(current)) {
          editFields[field] = {
            before: serializeDiffValue(current),
            after: serializeDiffValue(body[field]),
          };
          (currentItem as unknown as Record<string, unknown>)[field] = body[field];
          changed = true;
        }
      }
    }

    if (!changed) {
      return NextResponse.json({ ok: true, changed: false });
    }

    // Re-derive legacy v1 fields from v2 — unconditional overwrite so the
    // drawer reader (consumes analysis) stays in sync with cross-date
    // queries that still read main_bullet/context from brief_items.
    if (editFields.key_bullets || editFields.analysis) {
      const bullets = Array.isArray(currentItem.key_bullets)
        ? currentItem.key_bullets
        : [];
      const analysis =
        typeof currentItem.analysis === "string"
          ? currentItem.analysis.trim()
          : "";
      currentItem.main_bullet = bullets.length ? bullets.join(" ") : "";
      currentItem.context = analysis;
      currentItem.implication = "";
    }

    // If section changed, recalculate metadata
    if (editFields.section) {
      rebuildMetadata(rawBrief);
    }

    // Write updated raw_json back to briefs
    const { error: briefErr } = await supabase
      .from("briefs")
      .update({ raw_json: rawBrief })
      .eq("brief_date", briefDate);

    if (briefErr) {
      return NextResponse.json(
        { error: `Failed to update brief: ${briefErr.message}` },
        { status: 500 }
      );
    }

    // Update the brief_items row. Only columns still present on the
    // narrowed table (see migration 018) — v2 content columns live in
    // briefs.raw_json only.
    const itemUpdate: Record<string, unknown> = {};
    const columnMap: Record<string, string> = {
      headline: "headline",
      section: "section",
      significance_level: "significance",
    };

    for (const field of Object.keys(editFields)) {
      const col = columnMap[field];
      if (col) {
        itemUpdate[col] = (currentItem as unknown as Record<string, unknown>)[field];
      }
    }
    // Mirror derived legacy text fields so cross-date queries stay current.
    if (editFields.key_bullets || editFields.analysis) {
      itemUpdate.main_bullet = currentItem.main_bullet;
      itemUpdate.context = currentItem.context;
      itemUpdate.implication = currentItem.implication;
    }

    // Skip the brief_items UPDATE when no mirrored columns changed — edits
    // limited to v2-only fields (e.g. primary_entity, exhibits) that no
    // longer exist on brief_items would issue an empty UPDATE.
    if (Object.keys(itemUpdate).length > 0) {
      const { error: itemErr } = await supabase
        .from("brief_items")
        .update(itemUpdate)
        .eq("brief_date", briefDate)
        .eq("item_id", itemId);

      if (itemErr) {
        console.error("[briefs/edit] brief_items update failed:", itemErr.message);
      }
    }

    // Audit log
    await supabase.from("brief_edit_log").insert({
      brief_date: briefDate,
      item_id: itemId,
      action: "edit",
      previous_item: snapshot,
      updated_fields: editFields,
      analyst_id: user.id,
    });

    revalidateBrief(briefDate);

    return NextResponse.json({ ok: true, changed: true, item: currentItem });
  } catch (err) {
    return handleRouteError(err, "briefs/[date]/items/[itemId] PUT");
  }
}

// ─── DELETE: Remove a published brief item ───────────────────────────────────

export async function DELETE(_request: NextRequest, { params }: Params) {
  try {
    const { supabase, user } = await getCurationClient();
    const { date: briefDate, itemId } = await params;

    const rawBrief = await loadBriefRawJson(supabase, briefDate);
    const itemIndex = rawBrief.items.findIndex((i) => i.id === itemId);
    if (itemIndex === -1) {
      return NextResponse.json({ error: "Item not found in brief" }, { status: 404 });
    }

    const snapshot = { ...rawBrief.items[itemIndex] };

    // Remove item and re-rank
    rawBrief.items.splice(itemIndex, 1);
    rawBrief.items.forEach((item, idx) => {
      item.rank = idx + 1;
    });

    rebuildMetadata(rawBrief);

    // Write updated raw_json + item_count
    const { error: briefErr } = await supabase
      .from("briefs")
      .update({
        raw_json: rawBrief,
        item_count: rawBrief.brief_metadata.total_items,
      })
      .eq("brief_date", briefDate);

    if (briefErr) {
      return NextResponse.json(
        { error: `Failed to update brief: ${briefErr.message}` },
        { status: 500 }
      );
    }

    // Delete the brief_items row
    const { error: itemErr } = await supabase
      .from("brief_items")
      .delete()
      .eq("brief_date", briefDate)
      .eq("item_id", itemId);

    if (itemErr) {
      console.error("[briefs/delete] brief_items delete failed:", itemErr.message);
    }

    // Audit log
    await supabase.from("brief_edit_log").insert({
      brief_date: briefDate,
      item_id: itemId,
      action: "delete",
      previous_item: snapshot,
      updated_fields: null,
      analyst_id: user.id,
    });

    revalidateBrief(briefDate);

    return NextResponse.json({
      ok: true,
      remaining_items: rawBrief.brief_metadata.total_items,
    });
  } catch (err) {
    return handleRouteError(err, "briefs/[date]/items/[itemId] DELETE");
  }
}
