"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import type { Brief, BriefItem } from "@/lib/types/brief";
import { useAuth } from "@/lib/auth/AuthProvider";

interface UseReadStatusReturn {
  readItems: Set<string>;
  isLoading: boolean;
  markAsRead: (itemId: string) => void;
  isRead: (itemId: string) => boolean;
  getReadCount: (items: BriefItem[]) => number;
  totalRead: number;
  totalItems: number;
}

export function useReadStatus(
  briefDate: string,
  brief: Brief
): UseReadStatusReturn {
  const { user } = useAuth();
  const [readItems, setReadItems] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);

  // Total items across all sections
  const totalItems = useMemo(
    () => brief.sections.reduce((sum, s) => sum + s.items.length, 0),
    [brief.sections]
  );

  useEffect(() => {
    if (!user) {
      setReadItems(new Set());
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setReadItems(new Set());

    async function load() {
      try {
        const res = await fetch(
          `/api/read-status?brief_date=${encodeURIComponent(briefDate)}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error("Failed to fetch read status");
        const data = await res.json();
        if (!cancelled) {
          setReadItems(new Set(data.readItems));
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

  const isRead = useCallback(
    (itemId: string): boolean => readItems.has(itemId),
    [readItems]
  );

  const markAsRead = useCallback(
    (itemId: string) => {
      if (!user || readItems.has(itemId)) return;

      // Optimistic — update local set immediately
      setReadItems((prev) => {
        const next = new Set(prev);
        next.add(itemId);
        return next;
      });

      // Fire-and-forget POST — no await, no error handling
      fetch("/api/read-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        keepalive: true,
        body: JSON.stringify({ item_id: itemId, brief_date: briefDate }),
      })
        .then((res) => {
          if (!res.ok) {
            throw new Error("Failed to persist read status");
          }
        })
        .catch(() => {
          setReadItems((prev) => {
            const next = new Set(prev);
            next.delete(itemId);
            return next;
          });
        });
    },
    [user, readItems, briefDate]
  );

  const getReadCount = useCallback(
    (items: BriefItem[]): number => {
      return items.filter((item) => readItems.has(item.id)).length;
    },
    [readItems]
  );

  return {
    readItems,
    isLoading,
    markAsRead,
    isRead,
    getReadCount,
    totalRead: readItems.size,
    totalItems,
  };
}
