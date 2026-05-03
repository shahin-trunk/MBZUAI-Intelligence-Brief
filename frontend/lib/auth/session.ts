export interface AuthSession {
  access_token: string;
  refresh_token: string;
  expires_at?: number;
  expires_in?: number;
  token_type?: string;
}

export interface AuthUser {
  id: string;
  email?: string | null;
}

export const AUTH_COOKIE_CHUNK_SIZE = 3500;
export const AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

export function getAuthCookieBase(supabaseUrl: string): string {
  const projectRef = new URL(supabaseUrl).hostname.split(".")[0];
  return `sb-${projectRef}-auth-token`;
}

export function readRawAuthCookie(
  cookieBase: string,
  getCookie: (name: string) => string | undefined
): string {
  const single = getCookie(cookieBase);
  if (single) {
    return single;
  }

  let combined = "";
  for (let i = 0; ; i += 1) {
    const chunk = getCookie(`${cookieBase}.${i}`);
    if (!chunk) break;
    combined += chunk;
  }
  return combined;
}

export function parseAuthSession(rawCookie: string): AuthSession | null {
  if (!rawCookie) return null;

  try {
    const parsed = JSON.parse(rawCookie);
    if (parsed?.access_token && parsed?.refresh_token) {
      return parsed as AuthSession;
    }
  } catch {
    // Try URL-decoded payload next.
  }

  try {
    const parsed = JSON.parse(decodeURIComponent(rawCookie));
    if (parsed?.access_token && parsed?.refresh_token) {
      return parsed as AuthSession;
    }
  } catch {
    return null;
  }

  return null;
}

export function encodeAuthSession(session: AuthSession): string {
  return encodeURIComponent(JSON.stringify(session));
}

export function chunkCookieValue(value: string): string[] {
  if (value.length <= AUTH_COOKIE_CHUNK_SIZE) {
    return [value];
  }

  const chunks: string[] = [];
  for (let i = 0; i < value.length; i += AUTH_COOKIE_CHUNK_SIZE) {
    chunks.push(value.slice(i, i + AUTH_COOKIE_CHUNK_SIZE));
  }
  return chunks;
}

export async function validateAccessToken(
  supabaseUrl: string,
  supabaseAnonKey: string,
  accessToken: string
): Promise<{ ok: true; user: AuthUser } | { ok: false; message: string; status: number }> {
  const res = await fetch(`${supabaseUrl}/auth/v1/user`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      apikey: supabaseAnonKey,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    return {
      ok: false,
      message: body,
      status: res.status,
    };
  }

  const user = (await res.json()) as AuthUser;
  return { ok: true, user };
}

export async function refreshAuthSession(
  supabaseUrl: string,
  supabaseAnonKey: string,
  session: AuthSession
): Promise<AuthSession | null> {
  if (!session.refresh_token) {
    return null;
  }

  const res = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=refresh_token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: supabaseAnonKey,
    },
    body: JSON.stringify({
      refresh_token: session.refresh_token,
    }),
  });

  if (!res.ok) {
    return null;
  }

  const refreshed = (await res.json()) as AuthSession;
  if (!refreshed?.access_token || !refreshed?.refresh_token) {
    return null;
  }

  return refreshed;
}

export async function resolveValidSession(
  rawCookie: string,
  supabaseUrl: string,
  supabaseAnonKey: string
): Promise<
  | { ok: true; session: AuthSession; user: AuthUser; refreshed: boolean }
  | { ok: false; reason: "missing" | "invalid" | "expired" }
> {
  const session = parseAuthSession(rawCookie);
  if (!session?.access_token) {
    return { ok: false, reason: rawCookie ? "invalid" : "missing" };
  }

  const validated = await validateAccessToken(
    supabaseUrl,
    supabaseAnonKey,
    session.access_token
  );
  if (validated.ok) {
    return {
      ok: true,
      session,
      user: validated.user,
      refreshed: false,
    };
  }

  const refreshed = await refreshAuthSession(
    supabaseUrl,
    supabaseAnonKey,
    session
  );
  if (!refreshed) {
    return { ok: false, reason: "expired" };
  }

  const refreshedValidated = await validateAccessToken(
    supabaseUrl,
    supabaseAnonKey,
    refreshed.access_token
  );
  if (!refreshedValidated.ok) {
    return { ok: false, reason: "expired" };
  }

  return {
    ok: true,
    session: refreshed,
    user: refreshedValidated.user,
    refreshed: true,
  };
}
