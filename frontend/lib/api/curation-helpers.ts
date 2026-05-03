import { NextResponse } from "next/server";
import { getAuthenticatedClient } from "@/lib/api/helpers";
import { normalizeCurationItems } from "@/lib/curation/items";
import type { CurationItem, PendingBrief } from "@/lib/types/curation";

type CurationRole = "admin" | "analyst";
type AuthenticatedClient = Awaited<ReturnType<typeof getAuthenticatedClient>>;

function pickLatestBrief(
  first: PendingBrief | null,
  second: PendingBrief | null
): PendingBrief | null {
  if (!first) return second;
  if (!second) return first;
  return first.created_at >= second.created_at ? first : second;
}

/**
 * Authenticate the request and verify the user has analyst or admin role.
 * Returns a service-role Supabase client + user info + role.
 * Throws 403 if the user is not an analyst or admin.
 */
export async function getCurationClient() {
  const { supabase, user } = await getAuthenticatedClient();

  const { data: profile, error } = await supabase
    .from("user_profiles")
    .select("role")
    .eq("id", user.id)
    .single();

  if (error || !["admin", "analyst"].includes(profile?.role)) {
    throw NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  return { supabase, user, role: profile.role as CurationRole };
}

export async function getLatestAccessiblePendingBrief(
  supabase: AuthenticatedClient["supabase"],
  userId: string
): Promise<PendingBrief | null> {
  // Show the most recent pending or claimed-by-me brief, regardless of
  // date. This allows admins to work on briefs from prior days (e.g.
  // re-running curation for a past date or testing the flow).
  const [{ data: latestPending, error: pendingError }, { data: latestClaimed, error: claimedError }] =
    await Promise.all([
      supabase
        .from("pending_briefs")
        .select("*")
        .eq("status", "pending")
        .order("brief_date", { ascending: false })
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
      supabase
        .from("pending_briefs")
        .select("*")
        .eq("status", "in_review")
        .eq("claimed_by", userId)
        .order("brief_date", { ascending: false })
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
    ]);

  if (pendingError) {
    throw NextResponse.json({ error: pendingError.message }, { status: 500 });
  }
  if (claimedError) {
    throw NextResponse.json({ error: claimedError.message }, { status: 500 });
  }

  return pickLatestBrief(
    (latestPending as PendingBrief | null) ?? null,
    (latestClaimed as PendingBrief | null) ?? null
  );
}

export async function requireClaimedBriefAccess(
  supabase: AuthenticatedClient["supabase"],
  userId: string,
  pendingBriefId: string
): Promise<PendingBrief> {
  const { data: brief, error } = await supabase
    .from("pending_briefs")
    .select("*")
    .eq("id", pendingBriefId)
    .maybeSingle();

  if (error) {
    throw NextResponse.json({ error: error.message }, { status: 500 });
  }
  if (!brief) {
    throw NextResponse.json({ error: "Brief not found" }, { status: 404 });
  }
  if (brief.status !== "in_review") {
    throw NextResponse.json(
      { error: "Brief must be claimed before editing" },
      { status: 409 }
    );
  }
  if (brief.claimed_by !== userId) {
    throw NextResponse.json(
      { error: "Brief is claimed by another analyst" },
      { status: 409 }
    );
  }

  return brief as PendingBrief;
}

export async function loadCurationItems(
  supabase: AuthenticatedClient["supabase"],
  pendingBriefId: string
): Promise<CurationItem[]> {
  const [{ data: pendingRows, error: pendingError }, { data: manualRows, error: manualError }] =
    await Promise.all([
      supabase
        .from("pending_items")
        .select("*")
        .eq("pending_brief_id", pendingBriefId),
      supabase
        .from("manual_items")
        .select("*")
        .eq("pending_brief_id", pendingBriefId),
    ]);

  if (pendingError) {
    throw NextResponse.json({ error: pendingError.message }, { status: 500 });
  }
  if (manualError) {
    throw NextResponse.json({ error: manualError.message }, { status: 500 });
  }

  return normalizeCurationItems(
    (pendingRows ?? []) as Array<Record<string, unknown>>,
    (manualRows ?? []) as Array<Record<string, unknown>>
  );
}
