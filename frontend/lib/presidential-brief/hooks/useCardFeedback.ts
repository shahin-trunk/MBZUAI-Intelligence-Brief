"use client";

import { useCallback, useState } from "react";
import type {
  SwipeActionKind,
  SwipeHistoryEntry,
  CardSwipeFeedTab,
} from "@/lib/presidential-brief/types/cardFeedback";

/**
 * Mock swipe outcomes + undo stack for the horizontal card deck.
 * TODO(api_later): sync negativeFeedbackIds / readIds with server.
 */
export type CardFeedbackApi = {
  negativeIds: ReadonlySet<string>;
  readIds: ReadonlySet<string>;
  recordSwipeCommit: (
    kind: SwipeActionKind,
    fromIndex: number,
    itemId: string | null,
    feedTab: CardSwipeFeedTab
  ) => void;
  undoLastSwipe: () => SwipeHistoryEntry | null;
  canUndoSwipe: boolean;
  recordNegativeFeedback: (itemId: string) => void;
};

export function useCardFeedback(): CardFeedbackApi {
  const [negativeIds, setNegativeIds] = useState<Set<string>>(() => new Set());
  const [readIds, setReadIds] = useState<Set<string>>(() => new Set());
  const [history, setHistory] = useState<SwipeHistoryEntry[]>([]);

  const recordSwipeCommit = useCallback(
    (
      kind: SwipeActionKind,
      fromIndex: number,
      itemId: string | null,
      feedTab: CardSwipeFeedTab
    ) => {
      if (itemId) {
        if (kind === "negative") {
          setNegativeIds((prev) => new Set(prev).add(itemId));
          // TODO(api_later): recordNegativeFeedback({ brief_date, item_id: itemId, kind: 'negative', recorded_at })
          if (process.env.NODE_ENV === "development") {
            console.log("[cardFeedback] negative", itemId);
          }
        } else {
          setReadIds((prev) => new Set(prev).add(itemId));
          if (process.env.NODE_ENV === "development") {
            console.log("[cardFeedback] read", itemId);
          }
        }
      }
      setHistory((h) => [
        ...h,
        { previousIndex: fromIndex, kind, itemId, feedTab },
      ]);
    },
    []
  );

  const undoLastSwipe = useCallback((): SwipeHistoryEntry | null => {
    const popped = { current: null as SwipeHistoryEntry | null };
    setHistory((h) => {
      if (h.length === 0) return h;
      popped.current = h[h.length - 1]!;
      return h.slice(0, -1);
    });
    const entry = popped.current;
    const id = entry?.itemId;
    if (entry && id) {
      if (entry.kind === "negative") {
        setNegativeIds((prev) => {
          const n = new Set(prev);
          n.delete(id);
          return n;
        });
      } else {
        setReadIds((prev) => {
          const n = new Set(prev);
          n.delete(id);
          return n;
        });
      }
    }
    return entry;
  }, []);

  const canUndoSwipe = history.length > 0;

  const recordNegativeFeedback = useCallback((itemId: string) => {
    setNegativeIds((prev) => new Set(prev).add(itemId));
    // TODO(api_later): same as recordSwipeCommit negative path
    if (process.env.NODE_ENV === "development") {
      console.log("[cardFeedback] recordNegativeFeedback", itemId);
    }
  }, []);

  return {
    negativeIds,
    readIds,
    recordSwipeCommit,
    undoLastSwipe,
    canUndoSwipe,
    recordNegativeFeedback,
  } satisfies CardFeedbackApi;
}
