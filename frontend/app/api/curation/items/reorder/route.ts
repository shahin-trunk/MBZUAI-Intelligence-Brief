import { NextRequest, NextResponse } from "next/server";
import {
  getCurationClient,
  requireClaimedBriefAccess,
} from "@/lib/api/curation-helpers";
import type { CurationItemRef } from "@/lib/types/curation";

export async function POST(request: NextRequest) {
  const { supabase, user } = await getCurationClient();
  const { pending_brief_id, ordered_items } = await request.json();

  if (!pending_brief_id || !Array.isArray(ordered_items)) {
    return NextResponse.json(
      { error: "Missing pending_brief_id or ordered_items" },
      { status: 400 }
    );
  }

  if (ordered_items.length === 0) {
    return NextResponse.json({ ok: true });
  }

  await requireClaimedBriefAccess(supabase, user.id, pending_brief_id);

  const pendingIds = ordered_items
    .filter((item: CurationItemRef) => item.kind === "pending")
    .map((item: CurationItemRef) => item.id);
  const manualIds = ordered_items
    .filter((item: CurationItemRef) => item.kind === "manual")
    .map((item: CurationItemRef) => item.id);

  const [{ data: pendingRows, error: pendingError }, { data: manualRows, error: manualError }] =
    await Promise.all([
      pendingIds.length > 0
        ? supabase
            .from("pending_items")
            .select("id, item_id, pending_brief_id")
            .in("id", pendingIds)
        : Promise.resolve({ data: [], error: null }),
      manualIds.length > 0
        ? supabase
            .from("manual_items")
            .select("id, item_id, pending_brief_id")
            .in("id", manualIds)
        : Promise.resolve({ data: [], error: null }),
    ]);

  if (pendingError || manualError) {
    return NextResponse.json(
      { error: pendingError?.message ?? manualError?.message ?? "Failed to load ordered items" },
      { status: 500 }
    );
  }

  const allRows = [...(pendingRows ?? []), ...(manualRows ?? [])];
  if (allRows.length !== ordered_items.length) {
    return NextResponse.json({ error: "One or more ordered items were not found" }, { status: 404 });
  }
  if (allRows.some((row) => row.pending_brief_id !== pending_brief_id)) {
    return NextResponse.json(
      { error: "All ordered items must belong to the same brief" },
      { status: 400 }
    );
  }

  const updates = ordered_items.map((item: CurationItemRef, index: number) => {
    const table = item.kind === "manual" ? "manual_items" : "pending_items";
    return supabase
      .from(table)
      .update({
        selected: true,
        curation_order: index + 1,
        updated_at: new Date().toISOString(),
      })
      .eq("id", item.id);
  });

  const results = await Promise.all(updates);
  const failedUpdate = results.find((result) => result.error);
  if (failedUpdate?.error) {
    return NextResponse.json({ error: failedUpdate.error.message }, { status: 500 });
  }

  await supabase.from("curation_decisions").insert({
    pending_brief_id,
    item_id: allRows[0].item_id,
    decision: "reorder",
    final_rank: 1,
    analyst_id: user.id,
  });

  return NextResponse.json({ ok: true });
}
