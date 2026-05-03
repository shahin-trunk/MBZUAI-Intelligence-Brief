import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { createServiceClient } from "@/lib/supabase/server";
import {
  getAuthCookieBase,
  readRawAuthCookie,
  resolveValidSession,
} from "@/lib/auth/session";
import { setAuthSessionCookies, clearAuthSessionCookies } from "@/lib/auth/server-session";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

interface AuthUser {
  id: string;
  email: string;
}

/**
 * Validate the session cookie and return a service-role Supabase client
 * plus the authenticated user.
 *
 * Bypasses GoTrueClient entirely — reads the cookie, validates the
 * access_token via Supabase REST API, and uses the service-role client
 * for DB operations. Callers must add `.eq("user_id", user.id)` to
 * scope queries (since RLS is bypassed with service role).
 */
export async function getAuthenticatedClient() {
  try {
    const cookieStore = await cookies();

    const cookieBase = getAuthCookieBase(SUPABASE_URL);
    const raw = readRawAuthCookie(
      cookieBase,
      (name) => cookieStore.get(name)?.value
    );

    if (!raw) {
      console.error("[getAuthenticatedClient] no session cookie found");
      throw NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const resolved = await resolveValidSession(raw, SUPABASE_URL, SUPABASE_ANON_KEY);
    if (!resolved.ok) {
      clearAuthSessionCookies(cookieStore, SUPABASE_URL);
      throw NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    if (resolved.refreshed) {
      setAuthSessionCookies(cookieStore, SUPABASE_URL, resolved.session);
    }

    const user: AuthUser = {
      id: resolved.user.id,
      email: resolved.user.email ?? "",
    };

    // Service-role client bypasses RLS — callers must filter by user_id
    const supabase = createServiceClient();

    return { supabase, user };
  } catch (err) {
    // Re-throw NextResponse errors (401s) as-is
    if (err instanceof NextResponse) {
      throw err;
    }
    // Also handle the case where err is a Response-like object from NextResponse.json()
    if (err && typeof err === "object" && "status" in err) {
      throw err;
    }
    // Unexpected errors — log and return 500
    console.error("[getAuthenticatedClient] unexpected error:", err);
    throw NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

/** Return a JSON success response. */
export function jsonOk<T>(data: T, status = 200) {
  return NextResponse.json(data, { status });
}

/** Return a JSON error response. */
export function jsonError(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

function isResponseLike(value: unknown): value is Response {
  return !!value && typeof value === "object" && "status" in value;
}

/**
 * Convert unexpected route handler errors into a safe JSON response while
 * preserving auth/helper responses such as 401 NextResponse objects.
 */
export function handleRouteError(err: unknown, scope: string) {
  if (isResponseLike(err)) {
    return err;
  }

  console.error(`[${scope}] unexpected error:`, err);
  return jsonError("Internal server error", 500);
}
