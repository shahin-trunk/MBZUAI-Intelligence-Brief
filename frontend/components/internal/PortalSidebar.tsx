"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth/AuthProvider";

/* ─── Custom inline SVG icons ─────────────────────────────────────────────── */
/* 16x16 viewBox, 1.5px stroke, currentColor                                  */

function IconBrief({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="1.5" width="10" height="13" rx="1" />
      <line x1="5.5" y1="5" x2="10.5" y2="5" />
      <line x1="5.5" y1="7.5" x2="10.5" y2="7.5" />
      <line x1="5.5" y1="10" x2="8.5" y2="10" />
    </svg>
  );
}

function IconFaculty({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M8 1.5L1.5 5.5L8 9.5L14.5 5.5L8 1.5Z" />
      <path d="M3 7.5v4l5 3 5-3v-4" />
    </svg>
  );
}

function IconResearch({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="7" cy="7" r="5" />
      <line x1="10.5" y1="10.5" x2="14" y2="14" />
      <line x1="7" y1="4.5" x2="7" y2="9.5" />
      <line x1="4.5" y1="7" x2="9.5" y2="7" />
    </svg>
  );
}

function IconVisibility({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="8" cy="8" r="6.5" />
      <ellipse cx="8" cy="8" rx="3" ry="6.5" />
      <line x1="1.5" y1="8" x2="14.5" y2="8" />
    </svg>
  );
}

function IconAdmin({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="2" y="2" width="12" height="12" rx="2" />
      <line x1="2" y1="6" x2="14" y2="6" />
      <line x1="6" y1="6" x2="6" y2="14" />
    </svg>
  );
}

function IconManualEntry({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M11.5 2.5a1.4 1.4 0 0 1 2 2L6 12l-3 .5.5-3 8-7Z" />
      <path d="M9.5 4.5l2 2" />
    </svg>
  );
}

function IconCuration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M2 2.5h12l-4.5 6v5l-3-1.75V8.5L2 2.5Z" />
    </svg>
  );
}

/* ─── Feature flags ──────────────────────────────────────────────────────── */

/** Set to true to restore the Institutional Performance section in the sidebar. */
const SHOW_INSTITUTIONAL_PERFORMANCE = false;

/* ─── Navigation data ─────────────────────────────────────────────────────── */

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  activeCheck: (pathname: string) => boolean;
  showAlertDot?: boolean;
}

const STRATEGIC_ITEMS: NavItem[] = [
  {
    label: "Daily Brief",
    href: "/brief/today",
    icon: IconBrief,
    activeCheck: (p) => p.startsWith("/brief"),
  },
  {
    label: "Curation",
    href: "/curation",
    icon: IconCuration,
    activeCheck: (p) => p.startsWith("/curation"),
  },
];

const PERFORMANCE_ITEMS: NavItem[] = [
  {
    label: "Faculty Excellence",
    href: "/faculty-excellence",
    icon: IconFaculty,
    activeCheck: (p) => p === "/faculty-excellence",
  },
  {
    label: "Research Impact",
    href: "/research-impact",
    icon: IconResearch,
    activeCheck: (p) => p === "/research-impact",
  },
  {
    label: "Visibility & Influence",
    href: "/visibility",
    icon: IconVisibility,
    activeCheck: (p) => p === "/visibility",
  },
];

/* ─── Component ───────────────────────────────────────────────────────────── */

interface PortalSidebarProps {
  children: React.ReactNode;
}

function NavLink({
  item,
  pathname,
  onClick,
}: {
  item: NavItem;
  pathname: string;
  onClick?: () => void;
}) {
  const active = item.activeCheck(pathname);
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      onClick={onClick}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 mx-1.5 rounded-lg font-sans text-[13px] transition-colors duration-150 min-h-[44px]",
        active
          ? "bg-[rgba(212,168,67,0.10)] text-sig-high font-medium"
          : "text-text-secondary hover:bg-[rgba(255,255,255,0.04)]"
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 shrink-0",
          active ? "text-sig-high" : "text-text-dim"
        )}
      />
      <span className="flex min-w-0 items-center gap-2">
        <span>{item.label}</span>
        {item.showAlertDot ? (
          <span
            className="inline-block h-2 w-2 shrink-0 rounded-full bg-sig-high"
            aria-label={`${item.label} has new items`}
            title={`${item.label} has new items`}
          />
        ) : null}
      </span>
    </Link>
  );
}

function SidebarSectionLabel({ title }: { title: string }) {
  return (
    <div className="px-3 pt-4 pb-1">
      <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-text-dim">
        {title}
      </span>
    </div>
  );
}

export function PortalSidebar({ children }: PortalSidebarProps) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isAdmin } = useAuth();
  const [hasPendingResearchRequests, setHasPendingResearchRequests] = useState(false);

  useEffect(() => {
    if (!isAdmin) {
      setHasPendingResearchRequests(false);
      return;
    }

    let cancelled = false;

    async function fetchResearchRequestStatus() {
      try {
        const res = await fetch("/api/admin/research", { cache: "no-store" });
        if (!res.ok) {
          return;
        }

        const json = await res.json();
        const requests = Array.isArray(json.requests) ? json.requests : [];
        const hasPending = requests.some(
          (request: { status?: string }) => request.status === "pending"
        );

        if (!cancelled) {
          setHasPendingResearchRequests(hasPending);
        }
      } catch {
        if (!cancelled) {
          setHasPendingResearchRequests(false);
        }
      }
    }

    void fetchResearchRequestStatus();

    return () => {
      cancelled = true;
    };
  }, [isAdmin, pathname]);

  const strategicItems = isAdmin
    ? [
        ...STRATEGIC_ITEMS,
        {
          label: "Manual Entry",
          href: "/manual-entry",
          icon: IconManualEntry,
          activeCheck: (p: string) => p === "/manual-entry",
        },
        {
          label: "Research Requests",
          href: "/research-requests",
          icon: IconResearch,
          activeCheck: (p: string) => p === "/research-requests",
          showAlertDot: hasPendingResearchRequests,
        },
        {
          label: "Admin",
          href: "/admin",
          icon: IconAdmin,
          activeCheck: (p: string) => p.startsWith("/admin"),
        },
      ]
    : STRATEGIC_ITEMS;

  return (
    <div className="flex min-h-screen bg-bg-primary">
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
          "fixed inset-y-0 left-0 z-50 w-[248px] bg-bg-primary border-r border-border-sidebar flex flex-col transition-transform duration-200 lg:translate-x-0 lg:static lg:z-auto pt-[env(safe-area-inset-top,0px)]",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Sidebar header */}
        <div className="flex items-center justify-between px-4 h-14 border-b border-border-sidebar">
          <span className="font-mono text-[12px] font-bold tracking-[0.15em] text-sig-high uppercase">
            Intelligence Portal
          </span>
          <button
            type="button"
            className="lg:hidden text-text-muted hover:text-text-primary"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="h-4 w-4">
              <line x1="3" y1="3" x2="13" y2="13" />
              <line x1="13" y1="3" x2="3" y2="13" />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-1 px-2">
          {/* Strategic Intelligence section */}
          <SidebarSectionLabel title="Strategic Intelligence" />
          {strategicItems.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              pathname={pathname}
              onClick={() => setSidebarOpen(false)}
            />
          ))}

          {SHOW_INSTITUTIONAL_PERFORMANCE && (
            <>
              {/* Divider */}
              <div className="h-px bg-border-sidebar mx-3 my-3" />

              {/* Institutional Performance section */}
              <SidebarSectionLabel title="Institutional Performance" />
              {PERFORMANCE_ITEMS.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  pathname={pathname}
                  onClick={() => setSidebarOpen(false)}
                />
              ))}
            </>
          )}

        </nav>
      </aside>

      {/* Main content */}
      <div className="flex min-h-0 flex-1 flex-col min-w-0">
        {/* Mobile header bar */}
        <div className="lg:hidden flex items-center min-h-14 px-4 py-2 border-b border-border-sidebar bg-bg-primary pt-[env(safe-area-inset-top,0px)]">
          <button
            type="button"
            className="text-text-muted hover:text-text-primary mr-3"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="h-5 w-5">
              <line x1="2" y1="4" x2="14" y2="4" />
              <line x1="2" y1="8" x2="14" y2="8" />
              <line x1="2" y1="12" x2="14" y2="12" />
            </svg>
          </button>
          <span className="font-mono text-[12px] font-bold tracking-[0.15em] text-sig-high uppercase">
            Intelligence Portal
          </span>
        </div>

        {/* Page content */}
        <main className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
