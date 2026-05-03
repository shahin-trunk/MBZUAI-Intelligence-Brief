import {
  getAuthenticatedClient,
  handleRouteError,
  jsonOk,
} from "@/lib/api/helpers";

/**
 * GET /api/me
 * Returns the current user's profile (role, display_name).
 * Uses the service-role client to bypass RLS on user_profiles.
 */
export async function GET() {
  try {
    const { supabase, user } = await getAuthenticatedClient();

    const { data: profile, error } = await supabase
      .from("user_profiles")
      .select("role, display_name")
      .eq("id", user.id)
      .maybeSingle();

    if (error) {
      console.error("[/api/me] user_profiles query failed:", error.message);
    }

    return jsonOk({
      id: user.id,
      email: user.email,
      role: profile?.role ?? "reader",
      display_name: profile?.display_name ?? user.email ?? "User",
    });
  } catch (err) {
    return handleRouteError(err, "/api/me");
  }
}
