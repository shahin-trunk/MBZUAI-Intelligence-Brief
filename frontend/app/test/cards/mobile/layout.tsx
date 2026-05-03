import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "Card Reader — Mobile Test",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function MobileTestLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-dvh w-screen overflow-hidden bg-[#0a0a0a] text-white">
      {children}
    </div>
  );
}
