"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { Annotation, Flag, ResearchRequest, BriefItem } from "@/lib/types/brief";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface BriefInteractionValue {
  // Annotations
  annotations: Annotation[];
  addAnnotation: (itemId: string, noteText: string) => Promise<void>;
  updateAnnotation: (id: string, noteText: string) => Promise<void>;
  deleteAnnotation: (id: string) => Promise<void>;
  getAnnotationsForItem: (itemId: string) => Annotation[];

  // Flags
  flags: Flag[];
  toggleFlag: (itemId: string) => Promise<void>;
  hasFlag: (itemId: string) => boolean;

  // Research requests
  requests: ResearchRequest[];
  submitRequest: (itemId: string, requestNote?: string) => Promise<void>;
  getRequestForItem: (itemId: string) => ResearchRequest | undefined;
  hasPendingRequest: (itemId: string) => boolean;

  // Read status
  readItems: Set<string>;
  markAsRead: (itemId: string) => void;
  isRead: (itemId: string) => boolean;
  getReadCount: (items: BriefItem[]) => number;
  totalRead: number;
  totalItems: number;

  // Panel state
  annotationPanelOpen: boolean;
  setAnnotationPanelOpen: (open: boolean) => void;
  selectedItemId: string | null;
  setSelectedItemId: (id: string | null) => void;

  // Dialog state
  researchDialogItemId: string | null;
  setResearchDialogItemId: (id: string | null) => void;
  shareDialogItemId: string | null;
  setShareDialogItemId: (id: string | null) => void;

  // Helper to find a brief item by id (for dialogs)
  findItem: (itemId: string) => BriefItem | undefined;

  // Item expansion (external triggers: keyboard nav, dialogs, other UI actions)
  expandedItemId: string | null;
  setExpandedItemId: (id: string | null) => void;
}

// ─── Context ─────────────────────────────────────────────────────────────────

const BriefInteractionContext = createContext<BriefInteractionValue | undefined>(
  undefined
);

export function BriefInteractionProvider({
  value,
  children,
}: {
  value: BriefInteractionValue;
  children: ReactNode;
}) {
  return (
    <BriefInteractionContext.Provider value={value}>
      {children}
    </BriefInteractionContext.Provider>
  );
}

export function useBriefInteraction(): BriefInteractionValue {
  const ctx = useContext(BriefInteractionContext);
  if (ctx === undefined) {
    throw new Error(
      "useBriefInteraction must be used within a BriefInteractionProvider"
    );
  }
  return ctx;
}
