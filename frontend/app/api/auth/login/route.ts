import { NextRequest, NextResponse } from "next/server";

import { setAuthSessionCookies } from "@/lib/auth/server-session";
import type { AuthSession } from "@/lib/auth/session";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const email = typeof body.email === "string" ? body.email.trim() : "";
    const password = typeof body.password === "string" ? body.password : "";

    if (!email || !password) {
      return NextResponse.json(
        { error: "Email and password are required" },
        { status: 400 }
      );
    }

    const authRes = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: SUPABASE_ANON_KEY,
      },
      body: JSON.stringify({ email, password }),
    });

    if (!authRes.ok) {
      const bodyText = await authRes.text().catch(() => "");
      return NextResponse.json(
        { error: bodyText || "Sign in failed" },
        { status: authRes.status }
      );
    }

    const session = (await authRes.json()) as AuthSession;
    if (!session?.access_token || !session?.refresh_token) {
      return NextResponse.json(
        { error: "Invalid auth session returned" },
        { status: 500 }
      );
    }

    const response = NextResponse.json({ success: true });
    setAuthSessionCookies(response.cookies, SUPABASE_URL, session);
    return response;
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 }
    );
  }
}
