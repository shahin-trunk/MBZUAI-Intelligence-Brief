/**
 * Client-side swipe / read feedback (mock). Replace with API types when backend exists.
 * @see api_later — POST /brief/:date/card-feedback
 */
export type SwipeActionKind = "read" | "negative";

/** Which deck the swipe belonged to (for undo + future API). */
export type CardSwipeFeedTab = "news" | "followup";

export interface SwipeHistoryEntry {
  previousIndex: number;
  kind: SwipeActionKind;
  /** Story item id when the swiped card was a story; null for divider/end skips */
  itemId: string | null;
  feedTab: CardSwipeFeedTab;
}

/** Payload shape for a future API (not wired). */
export interface RecordCardFeedbackBody {
  brief_date: string;
  item_id: string;
  kind: "negative";
  recorded_at: string;
}
