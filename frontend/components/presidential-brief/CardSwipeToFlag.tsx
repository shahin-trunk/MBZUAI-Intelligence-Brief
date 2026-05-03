"use client";

import { useRef } from "react";

interface CardSwipeToFlagProps {
  children: React.ReactNode;
  isFlagged: boolean;
  onFlag: () => void;
  onUnflag: () => void;
  onLongPress?: () => void;
}

const LONG_PRESS_MS = 500;
const MOVE_TOLERANCE = 10;

/**
 * Story card touch shell: long-press opens context menu.
 */
export default function CardSwipeToFlag({
  children,
  onLongPress,
  ..._rest
}: CardSwipeToFlagProps) {
  void _rest;
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const didLongPress = useRef(false);
  const startX = useRef(0);
  const startY = useRef(0);

  const clearLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    const touch = e.touches[0];
    startX.current = touch.clientX;
    startY.current = touch.clientY;
    didLongPress.current = false;
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
    if (Math.abs(dx) > MOVE_TOLERANCE || Math.abs(dy) > MOVE_TOLERANCE) {
      clearLongPress();
    }
  };

  const handleTouchEnd = () => {
    clearLongPress();
  };

  const handleClick = (e: React.MouseEvent) => {
    if (didLongPress.current) {
      e.stopPropagation();
      e.preventDefault();
      didLongPress.current = false;
    }
  };

  return (
    <div
      className="relative flex h-full min-h-0 flex-1 flex-col overflow-visible"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchEnd}
      onClickCapture={handleClick}
    >
      {children}
    </div>
  );
}
