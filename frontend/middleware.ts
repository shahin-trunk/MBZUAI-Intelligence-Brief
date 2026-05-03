import { NextResponse, type NextRequest } from "next/server";
import {
  getAuthCookieBase,
  readRawAuthCookie,
  resolveValidSession,
} from "@/lib/auth/session";
import {
  applySessionRefreshIfNeeded,
  clearAuthSessionCookies,
} from "@/lib/auth/server-session";

/**
 * Edge-compatible auth middleware — zero npm dependencies beyond Next.js.
 * Validates the Supabase session by reading auth cookies and calling the
 * Supabase Auth REST API directly via fetch (available in Edge Runtime).
 */
export async function middleware(request: NextRequest) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

  // Routes that don't require auth
  const publicPaths = ["/login", "/auth/callback", "/test"];
  const isPublicPath = publicPaths.some((path) =>
    request.nextUrl.pathname.startsWith(path)
  );

  // --- Read Supabase auth cookie ---
  // Cookie name follows the pattern: sb-<project-ref>-auth-token
  // May be chunked into .0, .1, .2, ... for large tokens
  const cookieBase = getAuthCookieBase(supabaseUrl);
  const rawCookie = readRawAuthCookie(
    cookieBase,
    (name) => request.cookies.get(name)?.value
  );

  // --- Validate session via Supabase REST API ---
  let isAuthenticated = false;
  let refreshedSession = null;

  if (rawCookie) {
    try {
      const resolved = await resolveValidSession(
        rawCookie,
        supabaseUrl,
        supabaseAnonKey
      );
      isAuthenticated = resolved.ok;
      if (resolved.ok && resolved.refreshed) {
        refreshedSession = resolved.session;
      }
    } catch {
      // Malformed cookie — treat as unauthenticated
    }
  }

  // --- Redirect logic ---
  if (!isAuthenticated && !isPublicPath) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    const response = NextResponse.redirect(url);
    clearAuthSessionCookies(response.cookies, supabaseUrl);
    return response;
  }

  if (isAuthenticated && request.nextUrl.pathname === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return applySessionRefreshIfNeeded(
      NextResponse.redirect(url),
      supabaseUrl,
      refreshedSession,
      Boolean(refreshedSession)
    );
  }

  return applySessionRefreshIfNeeded(
    NextResponse.next(),
    supabaseUrl,
    refreshedSession,
    Boolean(refreshedSession)
  );
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api/|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
