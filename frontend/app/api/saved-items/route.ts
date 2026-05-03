import { NextRequest, NextResponse } from "next/server";
import { getAuthenticatedClient } from "@/lib/api/helpers";

export async function GET(request: NextRequest) {
  const { supabase, user } = await getAuthenticatedClient();
  const briefDate = request.nextUrl.searchParams.get("brief_date");

  if (!briefDate) {
    return NextResponse.json({ error: "Missing brief_date" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("saved_items")
    .select("item_id, saved_at")
    .eq("user_id", user.id)
    .eq("brief_date", briefDate);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ items: data ?? [] });
}

export async function POST(request: NextRequest) {
  const { supabase, user } = await getAuthenticatedClient();
  const { brief_date, item_id } = await request.json();

  if (!brief_date || !item_id) {
    return NextResponse.json({ error: "Missing brief_date or item_id" }, { status: 400 });
  }

  // Toggle: check if exists, delete if so, insert if not
  const { data: existing, error: existingError } = await supabase
    .from("saved_items")
    .select("id")
    .eq("user_id", user.id)
    .eq("brief_date", brief_date)
    .eq("item_id", item_id)
    .maybeSingle();

  if (existingError) {
    return NextResponse.json({ error: existingError.message }, { status: 500 });
  }

  if (existing) {
    const { error } = await supabase.from("saved_items").delete().eq("id", existing.id);
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({ saved: false });
  }

  const { error } = await supabase.from("saved_items").insert({
    user_id: user.id,
    brief_date,
    item_id,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ saved: true });
}
