"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  role: "admin" | "analyst" | "editor" | "reader";
  display_name: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAdmin: boolean;
  isAnalyst: boolean;
  isLoading: boolean;
}

// ─── Context ─────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ─── Provider ────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadUser() {
      try {
        const meRes = await fetch("/api/me");

        if (!meRes.ok) {
          if (!cancelled) {
            setUser(null);
            setIsLoading(false);
          }
          return;
        }

        const profile = await meRes.json();

        const resolved: AuthUser = {
          id: profile.id,
          email: profile.email ?? "",
          role: (profile.role as AuthUser["role"]) ?? "reader",
          display_name: profile.display_name ?? profile.email ?? "User",
        };
        if (!cancelled) {
          setUser(resolved);
        }
      } catch {
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadUser();

    const onFocus = () => {
      void loadUser();
    };
    window.addEventListener("focus", onFocus);

    const interval = window.setInterval(() => {
      void loadUser();
    }, 5 * 60 * 1000);

    return () => {
      cancelled = true;
      window.removeEventListener("focus", onFocus);
      window.clearInterval(interval);
    };
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAdmin: user?.role === "admin",
        isAnalyst: user?.role === "analyst" || user?.role === "admin",
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
