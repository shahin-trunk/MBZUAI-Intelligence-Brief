import { NextResponse } from "next/server";
import {
  getCurationClient,
  getLatestAccessiblePendingBrief,
  loadCurationItems,
} from "@/lib/api/curation-helpers";

export async function GET() {
  const { supabase, user } = await getCurationClient();

  // Mirror the server page guard (app/(portal)/curation/page.tsx): if today's
  // brief is already published, never fall back to an older pending brief —
  // otherwise a window-focus refresh can flip the workspace off the
  // published-editing view and onto a stale prior-day candidate list.
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Dubai" });
  const { data: publishedToday } = await supabase
    .from("pending_briefs")
    .select("id")
    .eq("status", "published")
    .eq("brief_date", today)
    .limit(1)
    .maybeSingle();

  if (publishedToday) {
    return NextResponse.json({ brief: null, items: [] });
  }

  const brief = await getLatestAccessiblePendingBrief(supabase, user.id);
  if (!brief) {
    return NextResponse.json({ brief: null, items: [] });
  }

  const items = await loadCurationItems(supabase, brief.id);
  return NextResponse.json({
    brief,
    items,
  });
}
