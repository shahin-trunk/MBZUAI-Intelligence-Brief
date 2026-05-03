import { type NextRequest } from "next/server";
import {
  getAuthenticatedClient,
  handleRouteError,
  jsonOk,
  jsonError,
} from "@/lib/api/helpers";

/**
 * POST /api/push/register
 * Stores a device push token for the current user.
 * Body: { token: string, platform: "ios" | "android", environment?: "production" | "sandbox" }
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();
    const body = await request.json();
    const { token, platform, environment } = body;

    if (!token || !platform) {
      return jsonError("token and platform are required");
    }

    if (platform !== "ios" && platform !== "android") {
      return jsonError("platform must be 'ios' or 'android'");
    }

    const env = environment ?? "production";
    if (env !== "production" && env !== "sandbox") {
      return jsonError("environment must be 'production' or 'sandbox'");
    }

    const { error } = await supabase.from("push_tokens").upsert(
      {
        user_id: user.id,
        token,
        platform,
        environment: env,
      },
      { onConflict: "user_id,token,environment", ignoreDuplicates: true }
    );

    if (error) {
      console.error("push_tokens upsert error:", error.message);
      return jsonError(error.message, 500);
    }

    return jsonOk({ success: true });
  } catch (err) {
    return handleRouteError(err, "push/register POST");
  }
}
