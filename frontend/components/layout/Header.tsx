"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth/AuthProvider";

export function Header() {
  const pathname = usePathname();
  const { isAdmin } = useAuth();

  return (
    <header className="bg-bg-primary border-b border-border-accent">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-stretch justify-between">
          {/* Left: Logo + Portal link */}
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center shrink-0">
              <span className="font-mono text-[12px] font-bold tracking-[0.2em] text-sig-high bg-sig-high/10 px-2 py-1 rounded-sm">
                MBZUAI
              </span>
            </Link>

            <nav className="flex gap-4 self-stretch">
              <Link
                href="/"
                className="font-serif text-base tracking-tight transition-colors flex items-center border-b-2 -mb-px text-text-muted hover:text-text-primary border-b-transparent"
              >
                Portal
              </Link>
            </nav>
          </div>

          {/* Right: Utility nav */}
          <nav className="flex items-center gap-4">
            <Link
              href="/brief/today"
              className={cn(
                "font-mono text-[13px] transition-colors",
                "text-text-muted hover:text-text-primary"
              )}
            >
              Today&apos;s Brief
            </Link>
            <Link
              href="/flagged"
              className={cn(
                "font-mono text-[13px] transition-colors",
                pathname === "/flagged"
                  ? "text-text-bright"
                  : "text-text-muted hover:text-text-primary"
              )}
            >
              Flagged
            </Link>
            <Link
              href="/history"
              className={cn(
                "font-mono text-[13px] transition-colors",
                pathname.startsWith("/history")
                  ? "text-text-bright"
                  : "text-text-muted hover:text-text-primary"
              )}
            >
              Archive
            </Link>
            {isAdmin && (
              <Link
                href="/admin"
                className={cn(
                  "font-mono text-[13px] transition-colors",
                  pathname.startsWith("/admin")
                    ? "text-text-bright"
                    : "text-text-muted hover:text-text-primary"
                )}
              >
                Admin
              </Link>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
}
