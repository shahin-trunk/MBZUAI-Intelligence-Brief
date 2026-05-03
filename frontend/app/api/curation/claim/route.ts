import { NextRequest, NextResponse } from "next/server";
import { getCurationClient } from "@/lib/api/curation-helpers";

export async function POST(request: NextRequest) {
  const { supabase, user } = await getCurationClient();
  const { pending_brief_id } = await request.json();

  if (!pending_brief_id) {
    return NextResponse.json({ error: "Missing pending_brief_id" }, { status: 400 });
  }

  const now = new Date().toISOString();

  // Try to claim atomically while the brief is still pending.
  const { data: claimedBrief, error: claimError } = await supabase
    .from("pending_briefs")
    .update({
      status: "in_review",
      claimed_by: user.id,
      claimed_at: now,
      updated_at: now,
    })
    .eq("id", pending_brief_id)
    .eq("status", "pending")
    .select("id")
    .maybeSingle();

  if (claimError) {
    return NextResponse.json({ error: claimError.message }, { status: 500 });
  }

  if (claimedBrief) {
    return NextResponse.json({ ok: true });
  }

  // No pending row matched, so inspect the current state.
  const { data: brief, error: briefError } = await supabase
    .from("pending_briefs")
    .select("status, claimed_by")
    .eq("id", pending_brief_id)
    .maybeSingle();

  if (briefError) {
    return NextResponse.json({ error: briefError.message }, { status: 500 });
  }
  if (!brief) {
    return NextResponse.json({ error: "Brief not found" }, { status: 404 });
  }

  if (brief.status === "in_review" && brief.claimed_by !== user.id) {
    return NextResponse.json(
      { error: "Brief already claimed by another analyst" },
      { status: 409 },
    );
  }
  if (brief.status === "in_review" && brief.claimed_by === user.id) {
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ error: "Brief cannot be claimed in its current state" }, { status: 409 });
}
