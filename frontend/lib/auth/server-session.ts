import type { NextResponse } from "next/server";
import type { ResponseCookies } from "next/dist/compiled/@edge-runtime/cookies";

import {
  AUTH_COOKIE_MAX_AGE_SECONDS,
  chunkCookieValue,
  encodeAuthSession,
  getAuthCookieBase,
  type AuthSession,
} from "@/lib/auth/session";

function buildCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}

function setCookieValue(
  cookies: ResponseCookies,
  name: string,
  value: string,
  maxAge: number
) {
  cookies.set(name, value, buildCookieOptions(maxAge));
}

export function setAuthSessionCookies(
  cookies: ResponseCookies,
  supabaseUrl: string,
  session: AuthSession
) {
  const cookieBase = getAuthCookieBase(supabaseUrl);
  const encoded = encodeAuthSession(session);
  const chunks = chunkCookieValue(encoded);

  setCookieValue(cookies, cookieBase, "", 0);
  for (let i = 0; i < 8; i += 1) {
    setCookieValue(cookies, `${cookieBase}.${i}`, "", 0);
  }

  if (chunks.length === 1) {
    setCookieValue(cookies, cookieBase, chunks[0], AUTH_COOKIE_MAX_AGE_SECONDS);
    return;
  }

  chunks.forEach((chunk, index) => {
    setCookieValue(
      cookies,
      `${cookieBase}.${index}`,
      chunk,
      AUTH_COOKIE_MAX_AGE_SECONDS
    );
  });
}

export function clearAuthSessionCookies(
  cookies: ResponseCookies,
  supabaseUrl: string
) {
  const cookieBase = getAuthCookieBase(supabaseUrl);
  setCookieValue(cookies, cookieBase, "", 0);
  for (let i = 0; i < 8; i += 1) {
    setCookieValue(cookies, `${cookieBase}.${i}`, "", 0);
  }
}

export function applySessionRefreshIfNeeded(
  response: NextResponse,
  supabaseUrl: string,
  session: AuthSession | null,
  refreshed: boolean
) {
  if (refreshed && session) {
    setAuthSessionCookies(response.cookies, supabaseUrl, session);
  }
  return response;
}
