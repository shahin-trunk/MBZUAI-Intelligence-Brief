import { NextResponse } from "next/server";
import { getAuthenticatedClient } from "@/lib/api/helpers";

/**
 * Authenticate the request and verify the user has admin role.
 * Returns a service-role Supabase client + user info.
 * Throws 403 if the user is not an admin.
 *
 * Reuse pattern from getAuthenticatedClient() — same cookie-based
 * auth bypass, but adds a role check against user_profiles.
 */
export async function getAdminClient() {
  const { supabase, user } = await getAuthenticatedClient();

  // Fetch role from user_profiles
  const { data: profile, error } = await supabase
    .from("user_profiles")
    .select("role")
    .eq("id", user.id)
    .single();

  if (error || profile?.role !== "admin") {
    throw NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  return { supabase, user };
}
