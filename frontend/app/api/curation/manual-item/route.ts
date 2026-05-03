import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";
import {
  getCurationClient,
  requireClaimedBriefAccess,
} from "@/lib/api/curation-helpers";
import {
  buildLegacyTextFields,
  mapManualItem,
  mergeRawItem,
  normalizeExhibits,
  normalizeKeyBullets,
} from "@/lib/curation/items";

export async function POST(request: NextRequest) {
  const { supabase, user } = await getCurationClient();
  const body = await request.json();

  const {
    pending_brief_id,
    section,
    headline,
    source_name,
    source_url,
    key_bullets,
    analysis,
    primary_entity,
    exhibits,
  } = body;

  if (!pending_brief_id || !section || !headline || !Array.isArray(key_bullets) || key_bullets.length === 0) {
    return NextResponse.json(
      { error: "Missing required fields: pending_brief_id, section, headline, key_bullets" },
      { status: 400 },
    );
  }

  await requireClaimedBriefAccess(supabase, user.id, pending_brief_id);

  const manualRowId = randomUUID();
  const itemId = `manual-${randomUUID().slice(0, 8)}`;
  const legacy = buildLegacyTextFields({ key_bullets, analysis });
  const insertedAt = new Date().toISOString();
  const row = {
    id: manualRowId,
    pending_brief_id,
    item_id: itemId,
    section,
    headline,
    main_bullet: legacy.main_bullet,
    context: legacy.context,
    implication: legacy.implication,
    source_name: source_name || null,
    source_url: source_url || null,
    composite_score: 8,
    significance_level: "medium",
    key_bullets: normalizeKeyBullets(key_bullets),
    analysis: typeof analysis === "string" ? analysis : null,
    primary_entity:
      typeof primary_entity === "string" && primary_entity.trim().length > 0
        ? primary_entity.trim()
        : null,
    exhibits: normalizeExhibits(exhibits),
    depth: "standard",
    is_model_release: false,
    model_release_data: null,
    // Insert unselected; assign_curation_order below atomically flips
    // selected=true and sets the next curation_order under an advisory lock.
    selected: false,
    curation_order: null,
    added_by: user.id,
    created_at: insertedAt,
    updated_at: insertedAt,
  };
  const rawItem = mergeRawItem(row, row);

  const { error: insertError } = await supabase
    .from("manual_items")
    .insert({
      ...row,
      primary_entity_category:
        (rawItem.primary_entity_category as string | null | undefined) ?? null,
      raw_item: rawItem,
    });

  if (insertError) {
    return NextResponse.json({ error: insertError.message }, { status: 500 });
  }

  const { data: assignedOrder, error: rpcError } = await supabase.rpc(
    "assign_curation_order",
    {
      p_table: "manual_items",
      p_item_id: manualRowId,
      p_brief_id: pending_brief_id,
    }
  );

  if (rpcError) {
    return NextResponse.json({ error: rpcError.message }, { status: 500 });
  }

  const { data: inserted, error: reloadError } = await supabase
    .from("manual_items")
    .select("*")
    .eq("id", manualRowId)
    .single();

  if (reloadError || !inserted) {
    return NextResponse.json(
      { error: reloadError?.message ?? "Manual item could not be loaded" },
      { status: 500 }
    );
  }

  // Record curation decision
  await supabase.from("curation_decisions").insert({
    pending_brief_id,
    item_id: inserted.item_id,
    decision: "add",
    final_section: section,
    final_rank: assignedOrder as number,
    analyst_id: user.id,
  });

  return NextResponse.json({ ok: true, item: mapManualItem(inserted) });
}
