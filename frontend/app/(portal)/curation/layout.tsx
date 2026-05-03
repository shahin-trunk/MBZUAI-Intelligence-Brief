"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function CurationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAnalyst, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAnalyst) {
      router.replace("/");
    }
  }, [isLoading, isAnalyst, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-pulse text-text-muted">Loading...</div>
      </div>
    );
  }

  if (!isAnalyst) return null;

  return <>{children}</>;
}
