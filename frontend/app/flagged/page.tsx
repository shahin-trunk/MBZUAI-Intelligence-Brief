"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/AuthProvider";
import { useToast } from "@/lib/contexts/ToastContext";
import {
  FlaggedList,
  type FlaggedArchiveItem,
} from "@/components/presidential-flagged/FlaggedList";

export default function FlaggedPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [flaggedItems, setFlaggedItems] = useState<FlaggedArchiveItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchFlags = useCallback(async () => {
    try {
      const res = await fetch("/api/flags/all");
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setFlaggedItems(data.flaggedItems ?? []);
    } catch {
      // silent
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void fetchFlags();
      return;
    }

    setFlaggedItems([]);
    setIsLoading(false);
  }, [user, fetchFlags]);

  async function handleUnflag(flagId: string, itemId: string, briefDate: string) {
    // Optimistic remove
    const prev = [...flaggedItems];
    setFlaggedItems((items) => items.filter((i) => i.id !== flagId));

    try {
      const res = await fetch("/api/flags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_id: itemId,
          brief_date: briefDate,
          flag_type: "important",
        }),
      });
      if (!res.ok) throw new Error("Failed");
      showToast("Flag removed", "info");
    } catch {
      setFlaggedItems(prev);
      showToast("Failed to remove flag", "error");
    }
  }

  return (
    <main className="min-h-screen bg-bg-primary">
      <FlaggedList
        items={flaggedItems}
        isLoading={isLoading}
        onUnflag={(flagId, itemId, briefDate) => {
          void handleUnflag(flagId, itemId, briefDate);
        }}
        onBack={() => router.back()}
      />
    </main>
  );
}
