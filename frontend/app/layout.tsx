import type { Metadata, Viewport } from "next";
import {
  Literata,
  Noto_Sans,
  IBM_Plex_Mono,
} from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { ToastProvider } from "@/lib/contexts/ToastContext";
import { ToastContainer } from "@/components/ui/toast";
import { NativeBootstrap } from "@/components/NativeBootstrap";
import "flag-icons/css/flag-icons.min.css";
import "./globals.css";

const literata = Literata({
  variable: "--font-heading",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
});

const notoSansBody = Noto_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
});

const notoSansUi = Noto_Sans({
  variable: "--font-ui",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Intelligence Dashboard — MBZUAI",
  description: "Presidential Daily Intelligence Brief Portal",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${literata.variable} ${notoSansBody.variable} ${notoSansUi.variable} ${ibmPlexMono.variable} min-h-screen bg-bg-primary text-text-primary antialiased`}
        style={{
          paddingBottom: "var(--safe-area-bottom)",
        }}
      >
        <NativeBootstrap />
        <AuthProvider>
          <ToastProvider>
            <TooltipProvider>{children}</TooltipProvider>
            <ToastContainer />
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
