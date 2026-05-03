import { PortalChrome } from "@/components/internal/PortalChrome";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <PortalChrome>{children}</PortalChrome>;
}
