"use client";

import { useState } from "react";
import { useSpring, animated } from "@react-spring/web";
import { useDrag } from "@use-gesture/react";
import type { BriefItem } from "@/lib/types/brief";
import { CardFace } from "./CardFace";
import { CardExpanded } from "./CardExpanded";

interface SwipeableCardProps {
  item: BriefItem;
  entityLogo?: { logoUrl: string | null; category: string } | null;
  isTop: boolean;
  stackOffset: number;
  onDismiss: () => void;
  onSave: () => void;
  onExpand: () => void;
  onResearch?: () => void;
}

const SWIPE_THRESHOLD = 100;
const VELOCITY_THRESHOLD = 0.3;

export function SwipeableCard({
  item,
  entityLogo,
  isTop,
  stackOffset,
  onDismiss,
  onSave,
  onExpand,
  onResearch,
}: SwipeableCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [gone, setGone] = useState(false);

  const [{ x, y, rot, scale }, api] = useSpring(() => ({
    x: 0,
    y: 0,
    rot: 0,
    scale: isTop ? 1 : 0.95 - stackOffset * 0.03,
    config: { friction: 30, tension: 200 },
  }));

  const bind = useDrag(
    ({ active, movement: [mx, my], velocity: [vx, vy], direction: [dx] }) => {
      if (!isTop || gone || expanded) return;

      if (!active) {
        // Release — check thresholds
        if (Math.abs(mx) > SWIPE_THRESHOLD && vx > VELOCITY_THRESHOLD) {
          // Horizontal swipe
          setGone(true);
          const flyOut = dx > 0 ? 600 : -600;
          api.start({
            x: flyOut,
            rot: flyOut / 20,
            config: { friction: 50, tension: 200 },
          });
          setTimeout(() => {
            if (dx > 0) onSave();
            else onDismiss();
          }, 250);
        } else if (my < -150 && vy > VELOCITY_THRESHOLD) {
          // Swipe up = expand
          setExpanded(true);
          onExpand();
        } else {
          // Snap back
          api.start({ x: 0, y: 0, rot: 0 });
        }
      } else {
        // Dragging
        api.start({
          x: mx,
          y: Math.min(0, my), // Only allow upward drag
          rot: mx / 30,
          immediate: true,
        });
      }
    },
    { filterTaps: true, enabled: isTop && !expanded },
  );

  if (expanded) {
    return (
      <CardExpanded
        item={item}
        onClose={() => setExpanded(false)}
        onResearch={onResearch}
      />
    );
  }

  // Color overlay based on swipe direction
  const swipeX = x.get?.() ?? 0;
  const leftOpacity = Math.max(0, Math.min(1, -swipeX / 200));
  const rightOpacity = Math.max(0, Math.min(1, swipeX / 200));

  return (
    <animated.div
      {...bind()}
      style={{
        x,
        y,
        rotateZ: rot.to((r: number) => `${r}deg`),
        scale,
        touchAction: "none",
        position: "absolute",
        inset: 0,
        zIndex: isTop ? 10 : 10 - stackOffset,
        top: stackOffset * 8,
      }}
      className="will-change-transform"
    >
      <div className="relative h-full rounded-2xl border border-border-primary bg-surface-secondary shadow-2xl overflow-hidden">
        {/* Swipe direction overlays */}
        <div
          className="absolute inset-0 bg-red-500/10 pointer-events-none rounded-2xl transition-opacity"
          style={{ opacity: leftOpacity }}
        />
        <div
          className="absolute inset-0 bg-amber-500/10 pointer-events-none rounded-2xl transition-opacity"
          style={{ opacity: rightOpacity }}
        />

        {/* Swipe labels */}
        {leftOpacity > 0.2 && (
          <div className="absolute top-8 left-6 z-20 px-3 py-1 rounded-lg border-2 border-red-400 text-red-400 font-bold text-sm -rotate-12">
            SKIP
          </div>
        )}
        {rightOpacity > 0.2 && (
          <div className="absolute top-8 right-6 z-20 px-3 py-1 rounded-lg border-2 border-amber-400 text-amber-400 font-bold text-sm rotate-12">
            SAVE
          </div>
        )}

        <CardFace item={item} entityLogo={entityLogo} />

        {/* Swipe up hint */}
        <div className="absolute bottom-6 left-0 right-0 text-center">
          <p className="text-[10px] text-text-muted/50 animate-pulse">
            ↑ swipe up for analysis
          </p>
        </div>
      </div>
    </animated.div>
  );
}
