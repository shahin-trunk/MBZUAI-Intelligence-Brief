"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";
import { hapticImpact } from "@/lib/presidential-brief/haptics";
import { useLockBodyScroll } from "@/lib/hooks/useLockBodyScroll";

interface DaySwipeContainerProps {
  children: React.ReactNode;
  prevDate: string | null;
  nextDate: string | null;
}

const SWIPE_THRESHOLD = 88;
/** Only swipes that *start* near screen edges count — avoids fighting the card deck. */
const EDGE_PX = 40;

export default function DaySwipeContainer({
  children,
  prevDate,
  nextDate,
}: DaySwipeContainerProps) {
  const router = useRouter();
  const startX = useRef(0);
  const startY = useRef(0);

  useLockBodyScroll();

  const handleTouchStart = (e: React.TouchEvent) => {
    startX.current = e.touches[0].clientX;
    startY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = async (e: React.TouchEvent) => {
    const dx = e.changedTouches[0].clientX - startX.current;
    const dy = e.changedTouches[0].clientY - startY.current;
    const vw =
      typeof window !== "undefined" ? window.innerWidth : 400;
    const fromLeftEdge = startX.current <= EDGE_PX;
    const fromRightEdge = startX.current >= vw - EDGE_PX;

    // Must be a clear horizontal swipe from an edge
    if (Math.abs(dx) <= SWIPE_THRESHOLD || Math.abs(dx) <= Math.abs(dy) * 2) {
      return;
    }

    if (dx > 0 && prevDate && fromLeftEdge) {
      await hapticImpact("light");
      router.push(`/brief/${prevDate}`);
    } else if (dx < 0 && nextDate && fromRightEdge) {
      await hapticImpact("light");
      router.push(`/brief/${nextDate}`);
    }
  };

  return (
    <div
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      className="flex h-[100dvh] min-h-0 flex-col overflow-hidden overscroll-none"
    >
      {children}
    </div>
  );
}
