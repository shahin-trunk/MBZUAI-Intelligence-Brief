"use client";

import {
  useRef,
  useState,
  useCallback,
  useEffect,
  useLayoutEffect,
} from "react";

const AXIS_LOCK_PX = 12;
/** Flick past this speed (px/ms, finger moving up = negative vy) → commit next/prev */
const FLING_VY_NEXT = -0.38;
const FLING_VY_PREV = 0.38;
const COMMIT_PX = 95;
/** After crossing threshold: quicker finish so the deck “locks” without a long tail */
const WHEEL_IDLE_MS = 105;
/** When already deep past commit, stop scrolling → snap sooner (still 1:1 while moving) */
const WHEEL_IDLE_DEEP_MS = 58;
const WHEEL_DEEP_PX = COMMIT_PX * 1.38;
/**
 * Next/prev: shorter + decisive ease — reads as “card stacks on top” / “top card peels away”.
 * Bounce: slightly softer return to center.
 */
/** iOS-like snap: quick settle, slight ease-out (closer to screen-record / reel apps). */
const TRANSITION_SNAP =
  "transform 320ms cubic-bezier(0.2, 0.0, 0.2, 1), opacity 320ms cubic-bezier(0.2, 0.0, 0.2, 1)";
const TRANSITION_BOUNCE =
  "transform 380ms cubic-bezier(0.25, 0.82, 0.2, 1), opacity 380ms cubic-bezier(0.25, 0.82, 0.2, 1)";
/** Trackpad: map wheel delta to drag (tune for 1:1 feel with hand) */
const WHEEL_SENSITIVITY = 0.92;
/**
 * Next-card rest position uses `H - CARD_PEEK_PX + CARD_STACK_OFFSET_PX`.
 * Keep `CARD_PEEK_PX - CARD_STACK_OFFSET_PX` constant when tuning spacing so the
 * visible strip (~74px) stays the same across breakpoints.
 */
const CARD_PEEK_PX = 82;
const CARD_STACK_OFFSET_PX = 8;

type AxisLock = null | "h" | "v";
type SnapKind = null | "next" | "prev" | "bounce";

export interface CardDeckStackProps {
  slideCount: number;
  activeIndex: number;
  onActiveIndexChange: (index: number) => void;
  renderSlide: (index: number) => React.ReactNode;
}

/**
 * Stacked deck: vertical drag follows the finger — the active card translates
 * with the gesture (not “shrink in place”); the next/prev card moves in sync
 * from its peek/rest position. Trackpad: same drag mapping, snap after idle.
 */
export default function CardDeckStack({
  slideCount,
  activeIndex,
  onActiveIndexChange,
  renderSlide,
}: CardDeckStackProps) {
  const deckRef = useRef<HTMLDivElement>(null);
  const [deckH, setDeckH] = useState(0);

  const [dragY, setDragY] = useState(0);
  const [isSnapping, setIsSnapping] = useState(false);
  const [snapKind, setSnapKind] = useState<SnapKind>(null);

  const dragYRef = useRef(0);
  const isSnappingRef = useRef(false);
  const snapKindRef = useRef<SnapKind>(null);
  const wheelIdleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Fallback: if transitionend never fires (Safari / subpixel / H resize), still unlock + advance
  const snapFallbackRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const snapTransitionSettledRef = useRef(false);
  // Tracks which direction the user committed to — prevents z-index flickering near 0
  const dragDirRef = useRef<"next" | "prev" | null>(null);

  const startY = useRef(0);
  const startX = useRef(0);
  const axisLockRef = useRef<AxisLock>(null);
  /** Recent touch samples for flick velocity (time ms, clientY). */
  const touchTrailRef = useRef<{ t: number; y: number }[]>([]);

  const canNext = activeIndex < slideCount - 1;
  const canPrev = activeIndex > 0;

  const rubber = useCallback(
    (y: number) => {
      if (y < 0 && !canNext) return y * 0.22;
      if (y > 0 && !canPrev) return y * 0.22;
      return y;
    },
    [canNext, canPrev]
  );

  const rubberRef = useRef(rubber);
  rubberRef.current = rubber;

  const H = deckH || 500;
  const HRef = useRef(H);
  HRef.current = H;

  const canNextRef = useRef(canNext);
  const canPrevRef = useRef(canPrev);
  const activeIndexRef = useRef(activeIndex);
  canNextRef.current = canNext;
  canPrevRef.current = canPrev;
  activeIndexRef.current = activeIndex;

  useLayoutEffect(() => {
    const el = deckRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setDeckH(el.offsetHeight));
    ro.observe(el);
    setDeckH(el.offsetHeight);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    dragYRef.current = dragY;
  }, [dragY]);

  useEffect(() => {
    dragYRef.current = 0;
    setDragY(0);
    isSnappingRef.current = false;
    snapKindRef.current = null;
    setIsSnapping(false);
    setSnapKind(null);
    axisLockRef.current = null;
    dragDirRef.current = null;
    snapTransitionSettledRef.current = false;
    if (wheelIdleRef.current) {
      clearTimeout(wheelIdleRef.current);
      wheelIdleRef.current = null;
    }
    if (snapFallbackRef.current) {
      clearTimeout(snapFallbackRef.current);
      snapFallbackRef.current = null;
    }
  }, [activeIndex]);

  useEffect(() => {
    snapKindRef.current = snapKind;
  }, [snapKind]);

  const clearWheelIdle = useCallback(() => {
    if (wheelIdleRef.current) {
      clearTimeout(wheelIdleRef.current);
      wheelIdleRef.current = null;
    }
  }, []);

  const clearSnapFallback = useCallback(() => {
    if (snapFallbackRef.current) {
      clearTimeout(snapFallbackRef.current);
      snapFallbackRef.current = null;
    }
  }, []);

  const settleSnapTransition = useCallback(() => {
    if (snapTransitionSettledRef.current || !isSnappingRef.current) return;
    snapTransitionSettledRef.current = true;
    clearSnapFallback();

    const kind = snapKindRef.current;
    const idx = activeIndexRef.current;

    if (kind === "next" && canNextRef.current) {
      setDragY(0);
      dragYRef.current = 0;
      isSnappingRef.current = false;
      setIsSnapping(false);
      setSnapKind(null);
      snapKindRef.current = null;
      dragDirRef.current = null;
      onActiveIndexChange(idx + 1);
      return;
    }
    if (kind === "prev" && canPrevRef.current) {
      setDragY(0);
      dragYRef.current = 0;
      isSnappingRef.current = false;
      setIsSnapping(false);
      setSnapKind(null);
      snapKindRef.current = null;
      dragDirRef.current = null;
      onActiveIndexChange(idx - 1);
      return;
    }
    isSnappingRef.current = false;
    setIsSnapping(false);
    setSnapKind(null);
    snapKindRef.current = null;
    dragDirRef.current = null;
    setDragY(0);
    dragYRef.current = 0;
  }, [onActiveIndexChange, clearSnapFallback]);

  const scheduleSnapFallback = useCallback(() => {
    clearSnapFallback();
    snapTransitionSettledRef.current = false;
    snapFallbackRef.current = setTimeout(() => {
      snapFallbackRef.current = null;
      settleSnapTransition();
    }, 480);
  }, [clearSnapFallback, settleSnapTransition]);

  const finishVertical = useCallback(() => {
    if (isSnappingRef.current) return;
    clearWheelIdle();
    const y = dragYRef.current;
    const h = HRef.current;

    if (y < -COMMIT_PX && canNextRef.current) {
      snapKindRef.current = "next";
      isSnappingRef.current = true;
      snapTransitionSettledRef.current = false;
      setSnapKind("next");
      setIsSnapping(true);
      setDragY(-h);
      dragYRef.current = -h;
      scheduleSnapFallback();
      return;
    }
    if (y > COMMIT_PX && canPrevRef.current) {
      snapKindRef.current = "prev";
      isSnappingRef.current = true;
      snapTransitionSettledRef.current = false;
      setSnapKind("prev");
      setIsSnapping(true);
      setDragY(h);
      dragYRef.current = h;
      scheduleSnapFallback();
      return;
    }
    snapKindRef.current = "bounce";
    isSnappingRef.current = true;
    snapTransitionSettledRef.current = false;
    setSnapKind("bounce");
    setIsSnapping(true);
    setDragY(0);
    dragYRef.current = 0;
    scheduleSnapFallback();
  }, [clearWheelIdle, scheduleSnapFallback]);

  const finishVerticalRef = useRef(finishVertical);
  finishVerticalRef.current = finishVertical;

  useEffect(() => {
    const el = deckRef.current;
    if (!el || slideCount <= 0) return;

    const onWheel = (e: WheelEvent) => {
      if (isSnappingRef.current || slideCount <= 1) return;

      e.preventDefault();

      let delta = e.deltaY;
      if (e.deltaMode === 1) delta *= 16;
      if (e.deltaMode === 2) delta *= el.offsetHeight || HRef.current;

      // Scroll "down" (typical trackpad next) → negative dragY (same as finger up)
      // Clamp to one card height so fast scrolling can't skip multiple cards
      setDragY((prev) => {
        const raw = prev - delta * WHEEL_SENSITIVITY;
        const clamped = Math.max(-HRef.current, Math.min(HRef.current, raw));
        const next = rubberRef.current(clamped);
        dragYRef.current = next;
        // Latch direction once past a small threshold — prevents z-index flicker near 0
        if (next < -AXIS_LOCK_PX) dragDirRef.current = "next";
        else if (next > AXIS_LOCK_PX) dragDirRef.current = "prev";
        else dragDirRef.current = null;
        return next;
      });

      clearWheelIdle();
      const deep =
        Math.abs(dragYRef.current) >= WHEEL_DEEP_PX &&
        ((dragYRef.current < 0 && canNextRef.current) ||
          (dragYRef.current > 0 && canPrevRef.current));
      const idleMs = deep ? WHEEL_IDLE_DEEP_MS : WHEEL_IDLE_MS;
      wheelIdleRef.current = setTimeout(() => {
        wheelIdleRef.current = null;
        finishVerticalRef.current();
      }, idleMs);
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", onWheel);
      clearWheelIdle();
    };
  }, [slideCount, clearWheelIdle]);

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (isSnappingRef.current) return;
      clearWheelIdle();
      const t = e.touches[0];
      startX.current = t.clientX;
      startY.current = t.clientY;
      axisLockRef.current = null;
      touchTrailRef.current = [{ t: performance.now(), y: t.clientY }];
    },
    [clearWheelIdle]
  );

  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (isSnappingRef.current) return;
      const t = e.touches[0];
      const dx = t.clientX - startX.current;
      const dy = t.clientY - startY.current;

      let lock = axisLockRef.current;
      if (lock === null) {
        if (Math.abs(dx) > AXIS_LOCK_PX || Math.abs(dy) > AXIS_LOCK_PX) {
          lock = Math.abs(dx) > Math.abs(dy) ? "h" : "v";
          axisLockRef.current = lock;
        }
      }

      if (lock === "h") return;

      if (lock === "v") {
        e.preventDefault();
        const now = performance.now();
        const t = e.touches[0];
        const trail = touchTrailRef.current;
        trail.push({ t: now, y: t.clientY });
        while (trail.length > 1 && now - trail[0]!.t > 140) trail.shift();

        const nextY = rubber(dy);
        dragYRef.current = nextY;
        // Latch direction once past threshold
        if (nextY < -AXIS_LOCK_PX) dragDirRef.current = "next";
        else if (nextY > AXIS_LOCK_PX) dragDirRef.current = "prev";
        else dragDirRef.current = null;
        setDragY(nextY);
      }
    },
    [rubber]
  );

  const onTouchEnd = useCallback(() => {
    if (isSnappingRef.current) return;
    const wasVertical = axisLockRef.current === "v";
    axisLockRef.current = null;
    if (!wasVertical) return;

    const trail = touchTrailRef.current;
    touchTrailRef.current = [];
    if (trail.length >= 2) {
      const a = trail[0]!;
      const b = trail[trail.length - 1]!;
      const dt = Math.max(8, b.t - a.t);
      const vy = (b.y - a.y) / dt;
      if (vy < FLING_VY_NEXT && canNextRef.current && dragYRef.current > -COMMIT_PX) {
        dragYRef.current = -COMMIT_PX - 40;
        setDragY(dragYRef.current);
      } else if (vy > FLING_VY_PREV && canPrevRef.current && dragYRef.current < COMMIT_PX) {
        dragYRef.current = COMMIT_PX + 40;
        setDragY(dragYRef.current);
      }
    }

    finishVertical();
  }, [finishVertical]);

  const handleTransitionEnd = useCallback(
    (e: React.TransitionEvent) => {
      if (e.target !== e.currentTarget) return;
      if (e.propertyName !== "transform" && e.propertyName !== "opacity") return;
      if (!isSnappingRef.current) return;

      settleSnapTransition();
    },
    [settleSnapTransition]
  );

  /** How far through a full-card travel the gesture is (0 → 1). */
  const travel = Math.min(1, Math.abs(dragY) / H);
  /**
   * Keep scale at 1 while dragging — any shrink makes the card look shorter and the
   * gap to the next card *grow* even though peek math is linear.
   */
  const outgoingScale = 1;
  const outgoingOpacity = Math.max(0.38, 1 - 0.32 * travel);
  const outgoingTY = dragY;

  /** Next card stays full size and rides up with the stack (no “both cards shrink” effect). */
  const incomingScaleNext = 1;

  const peek = canNext ? CARD_PEEK_PX : 0;
  const stackOff = canNext ? CARD_STACK_OFFSET_PX : 0;
  const nextTranslateY =
    peek === 0
      ? H + Math.min(0, dragY)
      : H - peek + stackOff + dragY;

  const incomingScalePrev = 1;

  const prevIndex = activeIndex - 1;
  const nextIndex = activeIndex + 1;

  /** Next sheet above current as soon as user moves up — matches “under-card” coming forward. */
  const nextOnTop =
    snapKind === "next" ||
    (snapKind === null && canNext && dragY < -4);
  const prevOnTop =
    snapKind === "prev" ||
    (snapKind === null && canPrev && dragY > 4);

  const transitionStyle =
    isSnapping && snapKind === "bounce"
      ? TRANSITION_BOUNCE
      : isSnapping
        ? TRANSITION_SNAP
        : "none";

  if (slideCount <= 0) {
    return <div className="min-h-0 flex-1 bg-bg-primary" />;
  }

  return (
    <div
      ref={deckRef}
      className="relative min-h-0 flex-1 touch-none overflow-hidden bg-bg-primary"
      style={{ touchAction: "none" }}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      {nextIndex < slideCount && (
        <div
          className="pointer-events-none absolute inset-0 overflow-hidden bg-transparent"
          style={{ zIndex: nextOnTop ? 30 : 5 }}
        >
          <div
            className="pointer-events-auto h-full min-h-0 w-full bg-transparent"
            style={{
              transform: `translateY(${nextTranslateY}px) scale(${incomingScaleNext})`,
              transition: transitionStyle,
              transformOrigin: "50% 50%",
            }}
          >
            {renderSlide(nextIndex)}
          </div>
        </div>
      )}

      <div
        className="pointer-events-none absolute inset-0 overflow-hidden bg-transparent"
        style={{ zIndex: 20 }}
      >
        <div
          className="pointer-events-auto h-full min-h-0 w-full bg-transparent"
          style={{
            transform: `translateY(${outgoingTY}px) scale(${outgoingScale})`,
            opacity: outgoingOpacity,
            transition: transitionStyle,
            transformOrigin: "50% 50%",
            willChange: isSnapping || Math.abs(dragY) > 2 ? "transform, opacity" : undefined,
          }}
          onTransitionEnd={handleTransitionEnd}
        >
          {renderSlide(activeIndex)}
        </div>
      </div>

      {prevIndex >= 0 && (
        <div
          className="pointer-events-none absolute inset-0 overflow-hidden bg-transparent"
          style={{ zIndex: prevOnTop ? 30 : 5 }}
        >
          <div
            className="pointer-events-auto h-full min-h-0 w-full bg-transparent"
            style={{
              transform: `translateY(${-H + Math.max(0, dragY)}px) scale(${incomingScalePrev})`,
              transition: transitionStyle,
              transformOrigin: "50% 50%",
            }}
          >
            {renderSlide(prevIndex)}
          </div>
        </div>
      )}
    </div>
  );
}
