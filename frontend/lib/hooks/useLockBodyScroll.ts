"use client";

import { useEffect } from "react";

/**
 * Ref-counted body scroll lock.
 *
 * Prior approach: each component called `document.body.style.overflow = "hidden"`
 * on mount and restored the previously-captured value on unmount. That breaks
 * when locks overlap — the second component captures "hidden" as its "previous"
 * value and clobbers the restore when the first component cleans up. Result:
 * scroll stays frozen on whatever page you navigate to next, until refresh.
 *
 * This module keeps one counter across all callers. Only the first locker
 * snapshots and writes the "hidden" style; only the last unlocker restores.
 * Multiple components can call this safely in any order.
 */

let lockCount = 0;
let snapshot: {
  body: string;
  html: string;
  overscroll: string;
} | null = null;

function acquire() {
  if (typeof document === "undefined") return;
  if (lockCount === 0) {
    const body = document.body;
    const html = document.documentElement;
    snapshot = {
      body: body.style.overflow,
      html: html.style.overflow,
      overscroll: body.style.overscrollBehaviorY,
    };
    body.style.overflow = "hidden";
    html.style.overflow = "hidden";
    body.style.overscrollBehaviorY = "none";
  }
  lockCount += 1;
}

function release() {
  if (typeof document === "undefined") return;
  lockCount = Math.max(0, lockCount - 1);
  if (lockCount === 0 && snapshot) {
    const body = document.body;
    const html = document.documentElement;
    body.style.overflow = snapshot.body;
    html.style.overflow = snapshot.html;
    body.style.overscrollBehaviorY = snapshot.overscroll;
    snapshot = null;
  }
}

/**
 * Lock body scroll while the calling component is mounted.
 * Safe to compose — multiple callers refcount correctly.
 * Pass `enabled=false` to conditionally disable without unmounting.
 */
export function useLockBodyScroll(enabled: boolean = true) {
  useEffect(() => {
    if (!enabled) return;
    acquire();
    return release;
  }, [enabled]);
}
