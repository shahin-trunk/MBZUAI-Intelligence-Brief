"use client";

import { PortalSidebar } from "@/components/internal/PortalSidebar";

export function PortalChrome({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div className="hidden lg:block">
        <PortalSidebar>{children}</PortalSidebar>
      </div>
      <div className="lg:hidden">{children}</div>
    </>
  );
}
