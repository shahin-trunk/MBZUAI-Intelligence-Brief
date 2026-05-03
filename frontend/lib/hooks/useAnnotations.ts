"use client";

import { useState, useEffect, useCallback } from "react";
import type { Annotation } from "@/lib/types/brief";
import { useAuth } from "@/lib/auth/AuthProvider";
import { useToast } from "@/lib/contexts/ToastContext";

interface UseAnnotationsReturn {
  annotations: Annotation[];
  isLoading: boolean;
  addAnnotation: (itemId: string, noteText: string) => Promise<void>;
  updateAnnotation: (id: string, noteText: string) => Promise<void>;
  deleteAnnotation: (id: string) => Promise<void>;
  getAnnotationsForItem: (itemId: string) => Annotation[];
}

export function useAnnotations(briefDate: string): UseAnnotationsReturn {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      setAnnotations([]);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setAnnotations([]);

    async function load() {
      try {
        const res = await fetch(
          `/api/annotations?brief_date=${encodeURIComponent(briefDate)}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error("Failed to fetch annotations");
        const data = await res.json();
        if (!cancelled) {
          setAnnotations(data.annotations);
        }
      } catch {
        // Silently handle — annotations will be empty
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

  const addAnnotation = useCallback(
    async (itemId: string, noteText: string) => {
      if (!user) return;

      // Optimistic: create a temporary annotation
      const tempId = `temp-${Date.now()}`;
      const optimistic: Annotation = {
        id: tempId,
        user_id: user.id,
        item_id: itemId,
        brief_date: briefDate,
        note_text: noteText,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      setAnnotations((prev) => [optimistic, ...prev]);

      try {
        const res = await fetch("/api/annotations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            item_id: itemId,
            brief_date: briefDate,
            note_text: noteText,
          }),
        });

        if (!res.ok) throw new Error("Failed to save annotation");

        const data = await res.json();
        // Replace temp with real annotation
        setAnnotations((prev) =>
          prev.map((a) => (a.id === tempId ? data.annotation : a))
        );
        showToast("Annotation saved", "success");
      } catch {
        // Rollback
        setAnnotations((prev) => prev.filter((a) => a.id !== tempId));
        showToast("Failed to save — please try again", "error");
      }
    },
    [user, briefDate, showToast]
  );

  const updateAnnotation = useCallback(
    async (id: string, noteText: string) => {
      const original = annotations.find((a) => a.id === id);
      if (!original) return;

      // Optimistic update
      setAnnotations((prev) =>
        prev.map((a) =>
          a.id === id
            ? { ...a, note_text: noteText, updated_at: new Date().toISOString() }
            : a
        )
      );

      try {
        const res = await fetch(`/api/annotations/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ note_text: noteText }),
        });

        if (!res.ok) throw new Error("Failed to update annotation");

        const data = await res.json();
        setAnnotations((prev) =>
          prev.map((a) => (a.id === id ? data.annotation : a))
        );
        showToast("Annotation updated", "success");
      } catch {
        // Rollback
        setAnnotations((prev) =>
          prev.map((a) => (a.id === id ? original : a))
        );
        showToast("Failed to save — please try again", "error");
      }
    },
    [annotations, showToast]
  );

  const deleteAnnotation = useCallback(
    async (id: string) => {
      const original = annotations.find((a) => a.id === id);
      if (!original) return;

      // Optimistic delete
      setAnnotations((prev) => prev.filter((a) => a.id !== id));

      try {
        const res = await fetch(`/api/annotations/${id}`, {
          method: "DELETE",
        });

        if (!res.ok) throw new Error("Failed to delete annotation");

        showToast("Annotation deleted", "info");
      } catch {
        // Rollback
        setAnnotations((prev) => [...prev, original]);
        showToast("Failed to delete — please try again", "error");
      }
    },
    [annotations, showToast]
  );

  const getAnnotationsForItem = useCallback(
    (itemId: string): Annotation[] => {
      return annotations.filter((a) => a.item_id === itemId);
    },
    [annotations]
  );

  return {
    annotations,
    isLoading,
    addAnnotation,
    updateAnnotation,
    deleteAnnotation,
    getAnnotationsForItem,
  };
}
