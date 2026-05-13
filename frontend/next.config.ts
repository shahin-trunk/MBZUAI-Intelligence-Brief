import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  serverExternalPackages: ["pdfjs-dist", "pdf-parse"],
  // outputFileTracingRoot only needed for Docker standalone; not compatible with Vercel
  devIndicators: false,
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "www.google.com",
        pathname: "/s2/favicons/**",
      },
      {
        protocol: "https",
        hostname: "**.supabase.co",
        pathname: "/storage/v1/object/**",
      },
    ],
  },
  redirects: async () => [
    // Legacy /internal/* routes → flat
    {
      source: "/internal/:path*",
      destination: "/:path*",
      permanent: true,
    },
    // Legacy month-scoped root, e.g. /2026-03 → /
    {
      source: "/:month(\\d{4}-\\d{2})",
      destination: "/",
      permanent: true,
    },
    // Legacy month-scoped sub-routes, e.g. /2026-03/brief/today → /brief/today
    {
      source: "/:month(\\d{4}-\\d{2})/:path*",
      destination: "/:path*",
      permanent: true,
    },
  ],
};

export default nextConfig;
