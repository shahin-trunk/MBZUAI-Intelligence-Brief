import { NextRequest, NextResponse } from "next/server";
import { getAuthenticatedClient } from "@/lib/api/helpers";

export async function POST(request: NextRequest) {
  const { supabase, user } = await getAuthenticatedClient();
  const { brief_date, item_id, action } = await request.json();

  if (!brief_date || !item_id || !action) {
    return NextResponse.json(
      { error: "Missing brief_date, item_id, or action" },
      { status: 400 },
    );
  }

  const validActions = ["dismissed", "saved", "expanded", "audio_played", "research_requested"];
  if (!validActions.includes(action)) {
    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  }

  // Fire-and-forget insert — don't fail the request on logging errors
  await supabase.from("reader_interactions").insert({
    user_id: user.id,
    brief_date,
    item_id,
    action,
  });

  return NextResponse.json({ ok: true });
}
