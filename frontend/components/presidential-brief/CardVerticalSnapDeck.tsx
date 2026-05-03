"use client";

import {
  useRef,
  useCallback,
  useLayoutEffect,
  useImperativeHandle,
  forwardRef,
  useEffect,
} from "react";
import { BRIEF_STORY_CARD_MAX_WIDTH_CLASS } from "@/lib/presidential-brief/briefCardLayout";

/** Kept for compatibility with imports (vertical deck has no drag rail sync). */
export interface CardGestureFrame {
  dragX: number;
  dragY: number;
  active: boolean;
}

export interface CardVerticalSnapDeckHandle {
  scrollToSlide: (index: number, behavior?: ScrollBehavior) => void;
}

interface CardVerticalSnapDeckProps {
  slideCount: number;
  activeIndex: number;
  onActiveIndexChange: (index: number) => void;
  renderSlide: (index: number) => React.ReactNode;
}

/** Off-center slides scale down; center approaches 1 (scroll-linked). */
const SCALE_MIN = 0.82;
const SCALE_MAX = 1;
/** Dim slightly when off-center so outgoing cards read as receding. */
const OPACITY_MIN = 0.55;
const OPACITY_MAX = 1;
/**
 * Distance from slide midpoint to viewport center, as a fraction of viewport height,
 * at which scale/opacity reach their off-center minimum (linear ramp = even change while scrolling).
 */
const FOCUS_WINDOW = 0.62;

/**
 * After the last scroll event fires (scroll idle), apply a short CSS transition
 * so the card eases to its final scale/opacity rather than jumping.
 */
const SETTLE_TRANSITION = "transform 180ms cubic-bezier(0.25,0.46,0.45,0.94), opacity 180ms cubic-bezier(0.25,0.46,0.45,0.94)";
const SCROLL_IDLE_MS = 80;

function focusFromDistance(distPx: number, viewportH: number): number {
  if (viewportH <= 0) return 0;
  const t = Math.min(1, distPx / (viewportH * FOCUS_WINDOW));
  // Linear: avoids 1-t² flattening near center (felt like "small until snap, then jumps big").
  return Math.max(0, Math.min(1, 1 - t));
}

/**
 * Vertical scroll-snap deck with scroll-linked scale + opacity (incoming grows/fades in, outgoing shrinks/fades out).
 */
const CardVerticalSnapDeck = forwardRef<
  CardVerticalSnapDeckHandle,
  CardVerticalSnapDeckProps
>(function CardVerticalSnapDeck(
  { slideCount, activeIndex, onActiveIndexChange, renderSlide },
  ref
) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const innerRefs = useRef<(HTMLDivElement | null)[]>([]);
  const activeIndexRef = useRef(activeIndex);
  const syncingScrollRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const reduceMotionRef = useRef(false);
  /** Timer id for the scroll-idle settle transition. */
  const settleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const touchActiveRef = useRef(false);

  useLayoutEffect(() => {
    activeIndexRef.current = activeIndex;
  }, [activeIndex]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    reduceMotionRef.current = mq.matches;
    const onChange = () => {
      reduceMotionRef.current = mq.matches;
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const applySlideTransforms = useCallback((settling = false) => {
    const el = scrollRef.current;
    if (!el || slideCount <= 0) return;

    const vh = el.clientHeight;
    if (vh <= 0) return;

    const viewRect = el.getBoundingClientRect();
    const centerY = viewRect.top + vh / 2;

    for (let i = 0; i < slideCount; i++) {
      const inner = innerRefs.current[i];
      if (!inner) continue;
      const section = inner.parentElement;
      if (!section) continue;

      const r = section.getBoundingClientRect();
      const mid = r.top + r.height / 2;
      const dist = Math.abs(mid - centerY);

      if (reduceMotionRef.current) {
        inner.style.transform = "";
        inner.style.opacity = "";
        inner.style.zIndex = "";
        inner.style.transition = "";
        continue;
      }

      const focus = focusFromDistance(dist, vh);
      const scale = SCALE_MIN + (SCALE_MAX - SCALE_MIN) * focus;
      const opacity = OPACITY_MIN + (OPACITY_MAX - OPACITY_MIN) * focus;
      inner.style.transformOrigin = "center center";
      inner.style.transform = `scale(${scale})`;
      inner.style.opacity = String(opacity);
      inner.style.zIndex = String(Math.round(10 + focus * 20));
      // While finger is dragging: no transition (perfectly follows scroll).
      // After scroll idles (snap settled): ease to final value to avoid jump.
      inner.style.transition = settling ? SETTLE_TRANSITION : "none";
    }
  }, [slideCount]);

  const scheduleTransforms = useCallback(() => {
    if (rafRef.current !== null) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      applySlideTransforms(false);
    });
  }, [applySlideTransforms]);

  /** Called once scroll goes idle: re-apply with a settle easing so final value is smooth. */
  const scheduleSettle = useCallback(() => {
    if (settleTimerRef.current !== null) {
      clearTimeout(settleTimerRef.current);
    }
    settleTimerRef.current = setTimeout(() => {
      settleTimerRef.current = null;
      applySlideTransforms(true);
    }, SCROLL_IDLE_MS);
  }, [applySlideTransforms]);

  /**
   * On iOS, snap-mandatory suppresses scroll events during the drag phase.
   * We register native (non-React) touch listeners directly on the scroll element
   * so transforms update in real time while the finger is down.
   */
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const onTouchStart = () => {
      touchActiveRef.current = true;
      if (settleTimerRef.current !== null) {
        clearTimeout(settleTimerRef.current);
        settleTimerRef.current = null;
      }
    };

    const onTouchMove = () => {
      scheduleTransforms();
    };

    const onTouchEnd = () => {
      touchActiveRef.current = false;
      scheduleSettle();
    };

    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    el.addEventListener("touchend", onTouchEnd, { passive: true });
    el.addEventListener("touchcancel", onTouchEnd, { passive: true });

    return () => {
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("touchend", onTouchEnd);
      el.removeEventListener("touchcancel", onTouchEnd);
    };
  }, [scheduleTransforms, scheduleSettle]);

  useImperativeHandle(
    ref,
    () => ({
      scrollToSlide: (index: number, behavior: ScrollBehavior = "smooth") => {
        const el = scrollRef.current;
        if (!el) return;
        const h = el.clientHeight;
        if (h <= 0) return;
        const clamped = Math.max(0, Math.min(slideCount - 1, index));
        syncingScrollRef.current = true;
        el.scrollTo({ top: clamped * h, behavior });
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            syncingScrollRef.current = false;
            scheduleTransforms();
          });
        });
      },
    }),
    [slideCount, scheduleTransforms]
  );

  const handleScroll = useCallback(() => {
    if (!syncingScrollRef.current) {
      const el = scrollRef.current;
      if (el) {
        const h = el.clientHeight;
        if (h > 0) {
          const idx = Math.min(
            slideCount - 1,
            Math.max(0, Math.round(el.scrollTop / h))
          );
          if (idx !== activeIndexRef.current) {
            activeIndexRef.current = idx;
            onActiveIndexChange(idx);
          }
        }
      }
    }

    scheduleTransforms();
    scheduleSettle();
  }, [slideCount, onActiveIndexChange, scheduleTransforms, scheduleSettle]);

  useLayoutEffect(() => {
    scheduleTransforms();
  }, [slideCount, activeIndex, scheduleTransforms]);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const h = el.clientHeight;
      if (h <= 0) return;
      syncingScrollRef.current = true;
      el.scrollTop = activeIndexRef.current * h;
      requestAnimationFrame(() => {
        syncingScrollRef.current = false;
        scheduleTransforms();
      });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [slideCount, scheduleTransforms]);

  useEffect(
    () => () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      if (settleTimerRef.current !== null) clearTimeout(settleTimerRef.current);
    },
    []
  );

  if (slideCount <= 0) {
    return <div className="min-h-0 flex-1 bg-bg-primary" />;
  }

  innerRefs.current.length = slideCount;

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className={`relative min-h-0 min-w-0 flex-1 basis-0 overflow-y-auto overflow-x-hidden overscroll-y-contain snap-y snap-mandatory bg-bg-primary px-4 pb-0 pt-2 sm:pb-0 sm:pt-3 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden`}
      style={{ touchAction: "pan-y" }}
    >
      {Array.from({ length: slideCount }, (_, index) => (
        <section
          key={index}
          aria-roledescription="slide"
          aria-label={`Card ${index + 1} of ${slideCount}`}
          className="flex h-full min-h-0 shrink-0 snap-start snap-always flex-col items-stretch"
        >
          <div
            ref={(node) => {
              innerRefs.current[index] = node;
            }}
            className={`flex h-full min-h-0 w-full flex-1 flex-col will-change-transform ${BRIEF_STORY_CARD_MAX_WIDTH_CLASS}`}
          >
            {renderSlide(index)}
          </div>
        </section>
      ))}
    </div>
  );
});

export default CardVerticalSnapDeck;
