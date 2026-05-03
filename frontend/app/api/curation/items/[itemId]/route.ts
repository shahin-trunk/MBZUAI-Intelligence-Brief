import { NextRequest, NextResponse } from "next/server";
import {
  getCurationClient,
  requireClaimedBriefAccess,
} from "@/lib/api/curation-helpers";
import {
  buildLegacyTextFields,
  mapManualItem,
  mapPendingItem,
  mergeRawItem,
} from "@/lib/curation/items";

function serializeDiffValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

async function getNextCurationOrder(
  supabase: Awaited<ReturnType<typeof getCurationClient>>["supabase"],
  pendingBriefId: string
) {
  const [{ data: pendingRows }, { data: manualRows }] = await Promise.all([
    supabase
      .from("pending_items")
      .select("curation_order")
      .eq("pending_brief_id", pendingBriefId)
      .eq("selected", true),
    supabase
      .from("manual_items")
      .select("curation_order")
      .eq("pending_brief_id", pendingBriefId)
      .eq("selected", true),
  ]);

  const orders = [...(pendingRows ?? []), ...(manualRows ?? [])]
    .map((row) => Number(row.curation_order ?? 0))
    .filter((value) => Number.isFinite(value) && value > 0);
  return (orders.length > 0 ? Math.max(...orders) : 0) + 1;
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ itemId: string }> },
) {
  const { supabase, user } = await getCurationClient();
  const { itemId } = await params;
  const body = await request.json();
  const kind = body.kind === "manual" ? "manual" : "pending";

  const table = kind === "manual" ? "manual_items" : "pending_items";
  const { data: current, error: currentError } = await supabase
    .from(table)
    .select("*")
    .eq("id", itemId)
    .maybeSingle();

  if (currentError) {
    return NextResponse.json({ error: currentError.message }, { status: 500 });
  }
  if (!current) {
    return NextResponse.json({ error: "Item not found" }, { status: 404 });
  }

  await requireClaimedBriefAccess(supabase, user.id, current.pending_brief_id);

  // Build update object from allowed fields
  const updateFields: Record<string, unknown> = {};
  const editFields: Record<string, { before: string; after: string }> = {};
  const editable = [
    "headline",
    "main_bullet",
    "context",
    "implication",
    "key_bullets",
    "analysis",
    "primary_entity",
    "exhibits",
    "section",
    "selected",
    "curation_order",
  ] as const;

  for (const field of editable) {
    if (body[field] !== undefined && body[field] !== current[field]) {
      updateFields[field] = body[field];
      editFields[field] = {
        before: serializeDiffValue(current[field]),
        after: serializeDiffValue(body[field]),
      };
    }
  }

  if (Object.keys(updateFields).length === 0) {
    return NextResponse.json({ ok: true, changed: false });
  }

  const legacy = buildLegacyTextFields({
    key_bullets: updateFields.key_bullets ?? current.key_bullets,
    analysis: updateFields.analysis ?? current.analysis,
    main_bullet: updateFields.main_bullet ?? current.main_bullet,
    context: updateFields.context ?? current.context,
    implication: updateFields.implication ?? current.implication,
  });

  if (updateFields.key_bullets !== undefined || updateFields.analysis !== undefined) {
    updateFields.main_bullet = legacy.main_bullet;
    updateFields.context = legacy.context;
    updateFields.implication = legacy.implication;
  }

  // Case A: deselect — clear the order locally, single UPDATE handles it.
  if (updateFields.selected === false) {
    updateFields.curation_order = null;
  }

  // Case B: selection transition false → true without an explicit order.
  // Use the atomic Postgres function to avoid a race when multiple selects
  // happen in quick succession (each client-side click fires an independent
  // PUT; concurrent reads of max(curation_order) otherwise collide).
  const needsAtomicAssign =
    updateFields.selected === true &&
    current.selected !== true &&
    updateFields.curation_order === undefined;

  let assignedOrder: number | null = null;
  if (needsAtomicAssign) {
    const { data: rpcOrder, error: rpcError } = await supabase.rpc(
      "assign_curation_order",
      {
        p_table: table,
        p_item_id: itemId,
        p_brief_id: current.pending_brief_id,
      }
    );
    if (rpcError) {
      return NextResponse.json({ error: rpcError.message }, { status: 500 });
    }
    assignedOrder = rpcOrder as number;
    // The RPC already set selected=true and curation_order; don't re-apply.
    delete updateFields.selected;
    delete updateFields.curation_order;
  }

  if (kind === "pending" || kind === "manual") {
    updateFields.raw_item = mergeRawItem(current, {
      ...current,
      ...updateFields,
      ...(assignedOrder != null
        ? { selected: true, curation_order: assignedOrder }
        : {}),
    });
    updateFields.primary_entity_category =
      ((updateFields.raw_item as Record<string, unknown>).primary_entity_category as string | null | undefined)
      ?? null;
  }
  updateFields.updated_at = new Date().toISOString();

  // Only run the regular UPDATE if there are still fields to write (there
  // always will be at least updated_at, but raw_item may be the only change).
  const { error } = await supabase
    .from(table)
    .update(updateFields)
    .eq("id", itemId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const { data: updated, error: updatedError } = await supabase
    .from(table)
    .select("*")
    .eq("id", itemId)
    .single();

  if (updatedError || !updated) {
    return NextResponse.json(
      { error: updatedError?.message ?? "Updated item could not be loaded" },
      { status: 500 }
    );
  }

  // Record curation decision
  const changedKeys = Object.keys(updateFields).filter(
    (key) => key !== "updated_at" && key !== "raw_item"
  );
  const decision =
    changedKeys.length === 1 && changedKeys[0] === "selected"
      ? updateFields.selected
        ? "keep"
        : "remove"
      : changedKeys.every((key) => key === "curation_order" || key === "selected")
        ? "reorder"
        : "edit";

  await supabase.from("curation_decisions").insert({
    pending_brief_id: current.pending_brief_id,
    item_id: current.item_id,
    decision,
    original_tier: current.tier ?? null,
    original_section: current.section,
    original_rank: current.rank,
    final_section: updateFields.section ?? current.section,
    final_rank: updateFields.curation_order ?? current.rank ?? current.curation_order ?? null,
    edit_fields: decision === "edit" ? editFields : null,
    analyst_id: user.id,
  });

  return NextResponse.json({
    ok: true,
    changed: true,
    item: kind === "manual" ? mapManualItem(updated) : mapPendingItem(updated),
  });
}
