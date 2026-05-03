"use client";

import { useState, type FormEvent } from "react";
import { createClient } from "@/lib/supabase/client";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

type LoginMode = "password" | "magic-link";

export default function LoginPage() {
  const [mode, setMode] = useState<LoginMode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePasswordLogin(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setError(body?.error_description ?? body?.error ?? body?.msg ?? "Sign in failed");
        setLoading(false);
        return;
      }

      // Redirect — cookie is written, AuthProvider will read it on next page.
      window.location.href = "/";
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Sign in failed — please try again"
      );
      setLoading(false);
    }
  }

  async function handleMagicLink(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMagicLinkSent(false);

    try {
      const supabase = createClient();

      const { error: signInError } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });

      if (signInError) {
        setError(signInError.message);
        setLoading(false);
        return;
      }

      setMagicLinkSent(true);
      setLoading(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to send magic link"
      );
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-primary px-4">
      <div className="w-full max-w-sm rounded-lg border border-border-primary bg-bg-secondary p-8 shadow-lg">
        <div className="mb-8 text-center">
          <h1 className="font-serif text-3xl text-text-bright">
            Intelligence Briefing
          </h1>
          <p className="mt-2 font-mono text-xs tracking-widest text-text-muted uppercase">
            MBZUAI
          </p>
        </div>

        {magicLinkSent ? (
          <div className="space-y-4">
            <div className="rounded-md border border-border-primary bg-bg-tertiary p-4 text-center">
              <p className="text-sm text-text-primary">
                Check your email for the login link
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setMagicLinkSent(false);
                setMode("password");
              }}
              className="w-full text-center font-mono text-[14px] text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            >
              &larr; Back to sign in
            </button>
          </div>
        ) : mode === "password" ? (
          <form onSubmit={handlePasswordLogin} className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-sm font-medium text-text-secondary"
              >
                Email
              </label>
              <Input
                id="email"
                type="email"
                placeholder="you@mbzuai.ac.ae"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                className="border-border-primary bg-bg-tertiary text-text-primary placeholder:text-text-muted"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-sm font-medium text-text-secondary"
              >
                Password
              </label>
              <Input
                id="password"
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading}
                className="border-border-primary bg-bg-tertiary text-text-primary placeholder:text-text-muted"
              />
            </div>

            {error && (
              <p className="text-sm text-red-400" role="alert">
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full"
            >
              {loading ? "Signing in..." : "Sign In"}
            </Button>

            <button
              type="button"
              onClick={() => {
                setError(null);
                setMode("magic-link");
              }}
              className="w-full text-center font-mono text-[14px] text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            >
              Use magic link instead
            </button>
          </form>
        ) : (
          <form onSubmit={handleMagicLink} className="space-y-4">
            <div>
              <label
                htmlFor="magic-email"
                className="mb-1.5 block text-sm font-medium text-text-secondary"
              >
                Email
              </label>
              <Input
                id="magic-email"
                type="email"
                placeholder="you@mbzuai.ac.ae"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                className="border-border-primary bg-bg-tertiary text-text-primary placeholder:text-text-muted"
              />
            </div>

            {error && (
              <p className="text-sm text-red-400" role="alert">
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full"
            >
              {loading ? "Sending..." : "Send Magic Link"}
            </Button>

            <button
              type="button"
              onClick={() => {
                setError(null);
                setMode("password");
              }}
              className="w-full text-center font-mono text-[14px] text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            >
              Use password instead
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
