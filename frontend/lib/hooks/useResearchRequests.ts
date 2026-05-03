"use client";

import { useState, useEffect, useCallback } from "react";
import type { ResearchRequest } from "@/lib/types/brief";
import { useAuth } from "@/lib/auth/AuthProvider";
import { useToast } from "@/lib/contexts/ToastContext";

interface UseResearchRequestsReturn {
  requests: ResearchRequest[];
  isLoading: boolean;
  submitRequest: (itemId: string, requestNote?: string) => Promise<void>;
  getRequestForItem: (itemId: string) => ResearchRequest | undefined;
  hasPendingRequest: (itemId: string) => boolean;
}

export function useResearchRequests(
  briefDate: string
): UseResearchRequestsReturn {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [requests, setRequests] = useState<ResearchRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      setRequests([]);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setRequests([]);

    async function load() {
      try {
        const res = await fetch(
          `/api/research-requests?brief_date=${encodeURIComponent(briefDate)}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error("Failed to fetch research requests");
        const data = await res.json();
        if (!cancelled) {
          setRequests(data.requests);
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

  const getRequestForItem = useCallback(
    (itemId: string): ResearchRequest | undefined => {
      return requests.find((r) => r.item_id === itemId);
    },
    [requests]
  );

  const hasPendingRequest = useCallback(
    (itemId: string): boolean => {
      return requests.some(
        (r) =>
          r.item_id === itemId &&
          (r.status === "pending" || r.status === "in_progress")
      );
    },
    [requests]
  );

  const submitRequest = useCallback(
    async (itemId: string, requestNote?: string) => {
      if (!user) {
        const error = new Error("You must be signed in to request research");
        showToast(error.message, "error");
        throw error;
      }

      // Optimistic add
      const tempId = `temp-${Date.now()}`;
      const optimistic: ResearchRequest = {
        id: tempId,
        user_id: user.id,
        item_id: itemId,
        brief_date: briefDate,
        request_note: requestNote,
        status: "pending",
        created_at: new Date().toISOString(),
      };

      setRequests((prev) => [optimistic, ...prev]);

      try {
        const res = await fetch("/api/research-requests", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            item_id: itemId,
            brief_date: briefDate,
            request_note: requestNote,
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || "Failed to submit request");
        }

        const data = await res.json();
        setRequests((prev) =>
          prev.map((r) => (r.id === tempId ? data.request : r))
        );
        showToast("Research request submitted", "success");
      } catch (err) {
        // Rollback
        setRequests((prev) => prev.filter((r) => r.id !== tempId));
        const error =
          err instanceof Error
            ? err
            : new Error("Failed to submit — please try again");
        showToast(error.message, "error");
        throw error;
      }
    },
    [user, briefDate, showToast]
  );

  return {
    requests,
    isLoading,
    submitRequest,
    getRequestForItem,
    hasPendingRequest,
  };
}
