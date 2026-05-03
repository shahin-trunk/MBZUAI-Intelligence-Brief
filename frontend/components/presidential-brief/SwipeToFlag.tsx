"use client";

import { useRef, useState } from "react";
import { hapticImpact } from "@/lib/presidential-brief/haptics";

interface SwipeToFlagProps {
  children: React.ReactNode;
  isFlagged: boolean;
  onFlag: () => void;
  onUnflag: () => void;
  onLongPress?: () => void;
}

const MAX_SWIPE = 80;
const SWIPE_THRESHOLD = 50;
const LONG_PRESS_MS = 500;
const MOVE_TOLERANCE = 10;
const SWIPE_DETECT_THRESHOLD = 15;

export default function SwipeToFlag({
  children,
  isFlagged,
  onFlag,
  onUnflag,
  onLongPress,
}: SwipeToFlagProps) {
  const [translateX, setTranslateX] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const startX = useRef(0);
  const startY = useRef(0);
  const currentX = useRef(0);
  const isHorizontal = useRef<boolean | null>(null);
  const triggered = useRef(false);

  // Long-press state
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const didLongPress = useRef(false);

  const clearLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  const snapBack = () => {
    setIsTransitioning(true);
    setTranslateX(0);
    setTimeout(() => setIsTransitioning(false), 200);
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    const touch = e.touches[0];
    startX.current = touch.clientX;
    startY.current = touch.clientY;
    currentX.current = 0;
    isHorizontal.current = null;
    triggered.current = false;
    didLongPress.current = false;
    setIsTransitioning(false);

    // Start long-press timer
    clearLongPress();
    if (onLongPress) {
      longPressTimer.current = setTimeout(() => {
        didLongPress.current = true;
        onLongPress();
      }, LONG_PRESS_MS);
    }
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    const dx = e.touches[0].clientX - startX.current;
    const dy = e.touches[0].clientY - startY.current;

    // Cancel long-press if moved beyond tolerance
    if (Math.abs(dx) > MOVE_TOLERANCE || Math.abs(dy) > MOVE_TOLERANCE) {
      clearLongPress();
    }

    // Determine scroll direction on first meaningful move
    if (isHorizontal.current === null && (Math.abs(dx) > SWIPE_DETECT_THRESHOLD || Math.abs(dy) > SWIPE_DETECT_THRESHOLD)) {
      isHorizontal.current = Math.abs(dx) > Math.abs(dy);
    }

    if (!isHorizontal.current) return;

    // Only allow left swipe (negative dx)
    if (dx > 0) return;

    currentX.current = dx;
    const clamped = Math.max(-MAX_SWIPE, dx);
    setTranslateX(clamped);
  };

  const handleTouchEnd = async () => {
    clearLongPress();

    if (isHorizontal.current && currentX.current < -SWIPE_THRESHOLD && !triggered.current) {
      triggered.current = true;
      await hapticImpact("medium");
      if (isFlagged) {
        onUnflag();
      } else {
        onFlag();
      }
    }

    if (isHorizontal.current) {
      snapBack();
    }
  };

  // Suppress click if long press just fired
  const handleClick = (e: React.MouseEvent) => {
    if (didLongPress.current) {
      e.stopPropagation();
      e.preventDefault();
      didLongPress.current = false;
    }
  };

  const revealWidth = Math.abs(translateX);
  const revealVisible = revealWidth > 4;

  return (
    <div className="relative overflow-hidden">
      {/* Reveal area (behind content) */}
      <div
        className="absolute inset-y-0 right-0 flex items-center justify-end pr-4"
        style={{
          width: `${revealWidth}px`,
          backgroundColor: isFlagged ? "color-mix(in srgb, var(--color-accent) 12%, transparent)" : "color-mix(in srgb, var(--color-accent) 8%, transparent)",
          transition: isTransitioning ? "width 200ms ease-out" : "none",
        }}
      >
        {revealVisible && (
          <div
            className="flex flex-col items-center gap-0.5"
            style={{ opacity: Math.min(1, (revealWidth - 4) / 30) }}
          >
            <span className="text-[14px]" style={{ color: "var(--color-accent)" }}>⚑</span>
            <span className="text-[9px] font-semibold uppercase tracking-wide" style={{ color: "var(--color-accent)" }}>
              {isFlagged ? "Unflag" : "Flag"}
            </span>
          </div>
        )}
      </div>

      {/* Content */}
      <div
        className="relative bg-bg-primary"
        style={{
          transform: `translateX(${translateX}px)`,
          transition: isTransitioning ? "transform 200ms ease-out" : "none",
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onClickCapture={handleClick}
      >
        {children}
      </div>
    </div>
  );
}
