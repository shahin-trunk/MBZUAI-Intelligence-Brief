import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { setAuthSessionCookies } from "@/lib/auth/server-session";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/";

  if (code) {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      const response = NextResponse.redirect(`${origin}${next}`);
      if (data.session?.access_token && data.session?.refresh_token) {
        setAuthSessionCookies(
          response.cookies,
          process.env.NEXT_PUBLIC_SUPABASE_URL!,
          {
            access_token: data.session.access_token,
            refresh_token: data.session.refresh_token,
            expires_at: data.session.expires_at,
            expires_in: data.session.expires_in,
            token_type: data.session.token_type,
          }
        );
      }
      return response;
    }
  }

  // If code is missing or exchange failed, redirect to login with error
  return NextResponse.redirect(`${origin}/login`);
}
