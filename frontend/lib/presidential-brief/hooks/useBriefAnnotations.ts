"use client";

import { useCallback, useMemo } from "react";
import type { Annotation } from "@/lib/types/brief";
import { useAnnotations } from "@/lib/hooks/useAnnotations";

interface BriefAnnotationState {
  getForItem: (itemId: string) => Annotation[];
  addAnnotation: (itemId: string, briefDate: string, text: string) => Promise<void>;
  updateAnnotation: (id: string, text: string) => Promise<void>;
  deleteAnnotation: (id: string) => Promise<void>;
  getCount: () => number;
  getStorySheetDraft: (itemId: string) => string;
  saveStorySheetNote: (
    itemId: string,
    briefDate: string,
    text: string
  ) => Promise<void>;
}

function latestAnnotationForItem(annotations: Annotation[], itemId: string) {
  return annotations.find((annotation) => annotation.item_id === itemId) ?? null;
}

export function useBriefAnnotations(briefDate: string): BriefAnnotationState {
  const {
    annotations,
    addAnnotation,
    updateAnnotation,
    deleteAnnotation,
    getAnnotationsForItem,
  } = useAnnotations(briefDate);

  const getForItem = useCallback(
    (itemId: string) => getAnnotationsForItem(itemId),
    [getAnnotationsForItem]
  );

  const getCount = useCallback(() => annotations.length, [annotations.length]);

  const getStorySheetDraft = useCallback(
    (itemId: string) => latestAnnotationForItem(annotations, itemId)?.note_text ?? "",
    [annotations]
  );

  const saveStorySheetNote = useCallback(
    async (itemId: string, _briefDate: string, text: string) => {
      const existing = latestAnnotationForItem(annotations, itemId);
      const trimmed = text.trim();

      if (!trimmed) {
        if (existing) {
          await deleteAnnotation(existing.id);
        }
        return;
      }

      if (existing) {
        await updateAnnotation(existing.id, trimmed);
        return;
      }

      await addAnnotation(itemId, trimmed);
    },
    [annotations, addAnnotation, deleteAnnotation, updateAnnotation]
  );

  return useMemo(
    () => ({
      getForItem,
      addAnnotation: async (itemId: string, _briefDate: string, text: string) =>
        addAnnotation(itemId, text),
      updateAnnotation,
      deleteAnnotation,
      getCount,
      getStorySheetDraft,
      saveStorySheetNote,
    }),
    [
      addAnnotation,
      deleteAnnotation,
      getCount,
      getForItem,
      getStorySheetDraft,
      saveStorySheetNote,
      updateAnnotation,
    ]
  );
}
