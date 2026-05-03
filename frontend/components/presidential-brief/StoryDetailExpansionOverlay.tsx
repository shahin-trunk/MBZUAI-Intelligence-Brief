"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import type { BriefItem } from "@/lib/types/brief";
import StoryDetailDrawerContent from "./StoryDetailDrawerContent";
import { useLockBodyScroll } from "@/lib/hooks/useLockBodyScroll";

const EASE = "cubic-bezier(0.32, 0.72, 0, 1)";

export interface StoryDetailExpansionOverlayProps {
  item: BriefItem;
  /** Kept for API compatibility; enter/exit animation is slide only. */
  originRect: DOMRect;
  isFlagged: boolean;
  onDismiss: () => void;
  /** Current text for this article’s notepad (story detail sheet). */
  getStorySheetNoteText: () => string;
  /** Persist or clear (empty string removes stored note). Reject to show error toast and keep sheet open. */
  onSaveStorySheetNote: (text: string) => void | Promise<void>;
}

export default function StoryDetailExpansionOverlay({
  item,
  originRect,
  isFlagged,
  onDismiss,
  getStorySheetNoteText,
  onSaveStorySheetNote,
}: StoryDetailExpansionOverlayProps) {
  void originRect;
  const [visualExpanded, setVisualExpanded] = useState(false);
  const visualExpandedRef = useRef(false);
  const closeRequested = useRef(false);
  const dismissed = useRef(false);

  useEffect(() => {
    visualExpandedRef.current = visualExpanded;
  }, [visualExpanded]);

  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const transitionMs = reduceMotion ? 0 : 380;

  /* Slide up: one frame off-screen, then translate to 0. */
  /* eslint-disable react-hooks/set-state-in-effect */
  useLayoutEffect(() => {
    closeRequested.current = false;
    dismissed.current = false;
    if (reduceMotion) {
      setVisualExpanded(true);
      return;
    }
    let raf1 = 0;
    let raf2 = 0;
    raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => setVisualExpanded(true));
    });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
    };
  }, [item.id, reduceMotion]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useLockBodyScroll();

  const requestClose = useCallback(() => {
    if (closeRequested.current) return;
    closeRequested.current = true;
    if (reduceMotion) {
      onDismiss();
      return;
    }
    if (!visualExpandedRef.current) {
      onDismiss();
      return;
    }
    setVisualExpanded(false);
  }, [onDismiss, reduceMotion]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") requestClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [requestClose]);

  const handleShellTransitionEnd = (
    e: React.TransitionEvent<HTMLDivElement>
  ) => {
    if (e.target !== e.currentTarget) return;
    if (e.propertyName !== "transform") return;
    if (
      !closeRequested.current ||
      visualExpandedRef.current ||
      dismissed.current
    ) {
      return;
    }
    dismissed.current = true;
    onDismiss();
  };

  const shellTransform = visualExpanded
    ? "translate3d(0,0,0)"
    : "translate3d(0,100%,0)";

  const shellTransition =
    transitionMs > 0 ? `transform ${transitionMs}ms ${EASE}` : "none";

  const backdropOpacity = visualExpanded ? 1 : 0;
  const backdropTransition =
    transitionMs > 0 ? `opacity ${transitionMs}ms ${EASE}` : "none";

  if (typeof document === "undefined") return null;

  const node = (
    <div className="pointer-events-none fixed inset-0 z-[56]">
      <button
        type="button"
        aria-label="Close"
        className="pointer-events-auto absolute inset-0 bg-black/30 transition-opacity"
        style={{
          opacity: backdropOpacity,
          transition: backdropTransition,
        }}
        onClick={requestClose}
      />
      <div
        role="dialog"
        aria-modal
        aria-labelledby="story-detail-expansion-title"
        className="pointer-events-auto fixed left-0 top-0 flex h-[100dvh] min-h-0 w-full max-w-none flex-col overflow-hidden bg-bg-surface shadow-[0_25px_80px_rgba(0,0,0,0.22)]"
        style={{
          zIndex: 1,
          transform: shellTransform,
          transition: shellTransition,
          willChange: transitionMs > 0 ? "transform" : undefined,
        }}
        onTransitionEnd={handleShellTransitionEnd}
      >
        <span id="story-detail-expansion-title" className="sr-only">
          {item.headline}
        </span>
        <StoryDetailDrawerContent
          item={item}
          isFlagged={isFlagged}
          onClose={requestClose}
          getStorySheetNoteText={getStorySheetNoteText}
          onSaveStorySheetNote={onSaveStorySheetNote}
        />
      </div>
    </div>
  );

  return createPortal(node, document.body);
}
