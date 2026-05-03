"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth/AuthProvider";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  GitBranch,
  FlaskConical,
  Scale,
  Trash2,
  Users,
  Radar,
  Activity,
  Image,
  ArrowLeft,
  Menu,
  X,
} from "lucide-react";

const navItems = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/admin/pipeline", label: "Pipeline", icon: GitBranch },
  { href: "/admin/enrichment", label: "Enrichment", icon: FlaskConical },
  { href: "/admin/rationalization", label: "Rationalization", icon: Scale },
  { href: "/admin/drops", label: "Drop Log", icon: Trash2 },
  { href: "/admin/scout-watchlist", label: "Scout Watchlist", icon: Radar },
  { href: "/admin/scout-analytics", label: "Scout Analytics", icon: Activity },
  { href: "/admin/logos", label: "Logos", icon: Image },
  { href: "/admin/users", label: "Users", icon: Users },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isAdmin, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Redirect non-admin users
  useEffect(() => {
    if (!isLoading && (!user || !isAdmin)) {
      router.replace("/");
    }
  }, [isLoading, user, isAdmin, router]);

  // Don't render until we've confirmed admin status
  if (isLoading || !user || !isAdmin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-primary">
        <div className="font-mono text-sm text-text-muted">Loading...</div>
      </div>
    );
  }

  function isActive(href: string, exact?: boolean) {
    if (exact) return pathname === href;
    return pathname.startsWith(href);
  }

  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-[200px] bg-bg-secondary border-r border-border-primary flex flex-col transition-transform duration-200 lg:translate-x-0 lg:static lg:z-auto",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Sidebar header */}
        <div className="flex items-center justify-between px-4 h-14 border-b border-border-primary">
          <span className="font-mono text-[12px] font-bold tracking-[0.15em] text-sig-high uppercase">
            Admin
          </span>
          <div className="flex items-center gap-2">
            <Link
              href="/brief/today"
              className="hidden lg:inline-flex items-center gap-1.5 rounded-sm px-2 py-1 font-mono text-[12px] text-text-muted transition-colors hover:bg-bg-tertiary/50 hover:text-text-primary"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Portal
            </Link>
            <button
              type="button"
              className="lg:hidden text-text-muted hover:text-text-primary"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-3 space-y-0.5 px-2">
          {navItems.map((item) => {
            const active = isActive(item.href, item.exact);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-sm font-mono text-[14px] transition-colors duration-150",
                  active
                    ? "bg-bg-tertiary text-text-bright border-l-2 border-l-accent-primary"
                    : "text-text-muted hover:text-text-primary hover:bg-bg-tertiary/50"
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* Mobile header bar */}
        <div className="lg:hidden flex items-center justify-between h-14 px-4 border-b border-border-primary bg-bg-secondary">
          <div className="flex items-center min-w-0">
            <button
              type="button"
              className="text-text-muted hover:text-text-primary mr-3"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="font-mono text-[12px] font-bold tracking-[0.15em] text-sig-high uppercase">
              Admin
            </span>
          </div>
          <Link
            href="/brief/today"
            className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 font-mono text-[12px] text-text-muted transition-colors hover:bg-bg-tertiary/50 hover:text-text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Portal
          </Link>
        </div>

        {/* Page content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
