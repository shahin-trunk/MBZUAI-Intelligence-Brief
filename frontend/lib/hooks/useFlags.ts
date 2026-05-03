"use client";

import { useState, useEffect, useCallback } from "react";
import type { Flag } from "@/lib/types/brief";
import { useAuth } from "@/lib/auth/AuthProvider";
import { useToast } from "@/lib/contexts/ToastContext";

interface UseFlagsReturn {
  flags: Flag[];
  isLoading: boolean;
  toggleFlag: (itemId: string) => Promise<void>;
  hasFlag: (itemId: string) => boolean;
}

const FLAG_TYPE = "important" as const;

export function useFlags(briefDate: string): UseFlagsReturn {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [flags, setFlags] = useState<Flag[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      setFlags([]);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setFlags([]);

    async function load() {
      try {
        const res = await fetch(
          `/api/flags?brief_date=${encodeURIComponent(briefDate)}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error("Failed to fetch flags");
        const data = await res.json();
        if (!cancelled) {
          setFlags(data.flags);
        }
      } catch {
        // Silently handle
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [user, briefDate]);

  const hasFlag = useCallback(
    (itemId: string): boolean => {
      return flags.some(
        (f) => f.item_id === itemId && f.flag_type === FLAG_TYPE
      );
    },
    [flags]
  );

  const toggleFlag = useCallback(
    async (itemId: string) => {
      if (!user) return;

      const existing = flags.find(
        (f) => f.item_id === itemId && f.flag_type === FLAG_TYPE
      );

      if (existing) {
        // Optimistic remove
        setFlags((prev) => prev.filter((f) => f.id !== existing.id));
        try {
          const res = await fetch("/api/flags", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              item_id: itemId,
              brief_date: briefDate,
              flag_type: FLAG_TYPE,
            }),
          });

          if (!res.ok) throw new Error("Failed to toggle flag");

          const data = await res.json();
          if (data.action !== "removed") {
            throw new Error("Unexpected flag response");
          }

          showToast("Flag removed", "info");
        } catch {
          setFlags((prev) => {
            const hasCurrentFlag = prev.some(
              (f) => f.item_id === itemId && f.flag_type === FLAG_TYPE
            );
            return hasCurrentFlag ? prev : [...prev, existing];
          });
          showToast("Failed to update flag — please try again", "error");
        }
        return;
      }

      // Optimistic add
      const tempId = `temp-${Date.now()}-${itemId}`;
      const tempFlag: Flag = {
        id: tempId,
        user_id: user.id,
        item_id: itemId,
        brief_date: briefDate,
        flag_type: FLAG_TYPE,
        created_at: new Date().toISOString(),
      };
      setFlags((prev) => [...prev, tempFlag]);

      try {
        const res = await fetch("/api/flags", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            item_id: itemId,
            brief_date: briefDate,
            flag_type: FLAG_TYPE,
          }),
        });

        if (!res.ok) throw new Error("Failed to toggle flag");

        const data = await res.json();
        if (data.action !== "created" || !data.flag) {
          throw new Error("Unexpected flag response");
        }

        setFlags((prev) =>
          prev.map((f) => (f.id === tempId ? data.flag : f))
        );
        showToast("Item flagged", "success");
      } catch {
        setFlags((prev) => prev.filter((f) => f.id !== tempId));
        showToast("Failed to update flag — please try again", "error");
      }
    },
    [user, flags, briefDate, showToast]
  );

  return { flags, isLoading, toggleFlag, hasFlag };
}
