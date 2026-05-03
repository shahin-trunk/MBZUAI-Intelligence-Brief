import { NextResponse } from "next/server";
import { getCurationClient } from "@/lib/api/curation-helpers";

export async function GET() {
  const { supabase } = await getCurationClient();

  const { data, error } = await supabase
    .from("pending_briefs")
    .select("id, brief_date, status, claimed_by, claimed_at, approved_at, published_at, pipeline_stats, created_at")
    .in("status", ["approved", "published"])
    .order("brief_date", { ascending: false })
    .limit(30);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ briefs: data ?? [] });
}
