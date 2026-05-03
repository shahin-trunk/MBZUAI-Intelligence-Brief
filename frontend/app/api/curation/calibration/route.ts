import { NextResponse } from "next/server";
import { getCurationClient } from "@/lib/api/curation-helpers";

export async function GET() {
  const { supabase } = await getCurationClient();

  // Get all curation decisions grouped by brief
  const { data: decisions, error } = await supabase
    .from("curation_decisions")
    .select("pending_brief_id, decision, original_tier, edit_fields")
    .order("created_at", { ascending: false })
    .limit(500);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const allDecisions = decisions ?? [];

  // Compute calibration metrics
  const byBrief = new Map<string, typeof allDecisions>();
  for (const d of allDecisions) {
    const list = byBrief.get(d.pending_brief_id) ?? [];
    list.push(d);
    byBrief.set(d.pending_brief_id, list);
  }

  let totalKeep = 0;
  let totalRemove = 0;
  let totalPromote = 0;
  let totalEdit = 0;
  let totalAdd = 0;

  for (const d of allDecisions) {
    switch (d.decision) {
      case "keep":
        totalKeep++;
        break;
      case "remove":
      case "demote":
        totalRemove++;
        break;
      case "promote":
        totalPromote++;
        break;
      case "edit":
        totalEdit++;
        break;
      case "add":
        totalAdd++;
        break;
    }
  }

  const totalDecisions = totalKeep + totalRemove;
  const overlapRate = totalDecisions > 0 ? totalKeep / totalDecisions : 1;

  return NextResponse.json({
    total_sessions: byBrief.size,
    overlap_rate: Math.round(overlapRate * 100),
    total_keeps: totalKeep,
    total_removes: totalRemove,
    total_promotes: totalPromote,
    total_edits: totalEdit,
    total_manual_adds: totalAdd,
    promotion_rate:
      totalPromote + totalKeep > 0
        ? Math.round((totalPromote / (totalPromote + totalKeep)) * 100)
        : 0,
    edit_rate:
      totalKeep > 0 ? Math.round((totalEdit / totalKeep) * 100) : 0,
  });
}
