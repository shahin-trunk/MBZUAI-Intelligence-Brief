"use client";

import { useRef, useCallback } from "react";

const LONG_PRESS_MS = 500;
const MOVE_TOLERANCE = 10; // px — finger can drift this much without canceling

interface UseLongPressOptions {
  onLongPress: () => void;
  onClick?: () => void;
}

/**
 * Reusable long-press hook with movement tolerance.
 * Returns touch handlers to spread onto a container element.
 * If onLongPress fires, onClick is suppressed for that gesture.
 */
export function useLongPress({ onLongPress, onClick }: UseLongPressOptions) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const touchStart = useRef({ x: 0, y: 0 });
  const didLongPress = useRef(false);

  const clear = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      didLongPress.current = false;
      touchStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      clear();
      timer.current = setTimeout(() => {
        didLongPress.current = true;
        onLongPress();
      }, LONG_PRESS_MS);
    },
    [onLongPress, clear],
  );

  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      const dx = e.touches[0].clientX - touchStart.current.x;
      const dy = e.touches[0].clientY - touchStart.current.y;
      if (Math.abs(dx) > MOVE_TOLERANCE || Math.abs(dy) > MOVE_TOLERANCE) {
        clear();
      }
    },
    [clear],
  );

  const onTouchEnd = useCallback(() => {
    clear();
  }, [clear]);

  const handleClick = useCallback(() => {
    if (!didLongPress.current && onClick) {
      onClick();
    }
  }, [onClick]);

  return {
    handlers: { onTouchStart, onTouchMove, onTouchEnd },
    handleClick,
  };
}
