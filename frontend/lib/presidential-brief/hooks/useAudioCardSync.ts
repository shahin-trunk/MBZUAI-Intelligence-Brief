"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { AudioPlayerState, AudioPlayerActions } from "./useAudioPlayer";
import type { AudioSegment } from "@/lib/types/brief";

type SyncSource = "audio" | "user" | null;
type SyncMode = "auto" | "manual";

interface UseAudioCardSyncOptions {
  player: AudioPlayerState & AudioPlayerActions;
  segments: AudioSegment[] | undefined;
  activeCardIndex: number;
  setActiveCardIndex: (index: number) => void;
  /** Only sync story cards — map feed index to story index */
  feedIndexToStoryIndex: (feedIndex: number) => number;
  storyIndexToFeedIndex: (storyIndex: number) => number;
  totalStoryCards: number;
  /**
   * Per-item audio mode — item IDs in story-card order.
   * When provided with >0 entries, replaces segment-based sync
   * with per-item audio source swapping.
   */
  itemAudioIds?: string[];
  /**
   * When true, skip auto-play on card change (used when restoring
   * slide position from URL param on mount).
   */
  skipAutoPlay?: boolean;
}

/**
 * Bidirectional audio-visual sync hook.
 *
 * Supports two modes:
 * 1. **Narrative** (segments-based, existing behavior):
 *    - One long audio file with time-based segments
 *    - Card swipe → seek to segment start
 *    - Segment boundary crossed → auto-advance card
 *
 * 2. **Per-item** (itemAudioIds provided):
 *    - Each story card has its own audio file
 *    - Card swipe → play that item's audio via player.playItemAudio()
 *    - Audio ends naturally → auto-advance to next story card
 */
export function useAudioCardSync({
  player,
  segments,
  activeCardIndex,
  setActiveCardIndex,
  feedIndexToStoryIndex,
  storyIndexToFeedIndex,
  totalStoryCards,
  itemAudioIds,
  skipAutoPlay,
}: UseAudioCardSyncOptions) {
  const [syncMode, setSyncMode] = useState<SyncMode>("auto");
  const syncSourceRef = useRef<SyncSource>(null);
  const syncResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seekDebounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastCardIndexRef = useRef(activeCardIndex);

  const hasPerItemAudio = itemAudioIds !== undefined && itemAudioIds.length > 0;

  // Ref to avoid auto-playing on initial mount (e.g., returning from Learn page)
  const isInitialMountRef = useRef(true);
  // Stable ref to player.playItemAudio to avoid unstable `player` object in deps
  const playItemAudioRef = useRef(player.playItemAudio);
  playItemAudioRef.current = player.playItemAudio;

  // ── Per-item mode ──────────────────────────────────────────────────────

  // Card change → play item audio (skip auto-play on initial mount or when skipAutoPlay is true)
  useEffect(() => {
    if (!hasPerItemAudio) return;

    const storyIdx = feedIndexToStoryIndex(activeCardIndex);
    const itemId = (storyIdx >= 0 && storyIdx < itemAudioIds.length)
      ? itemAudioIds[storyIdx]
      : null;

    if (isInitialMountRef.current || skipAutoPlay) {
      isInitialMountRef.current = false;
      console.log("[AudioSync] mount/restore: register item", itemId, "no autoplay");
      // On mount/restore: register the active item (sets currentUrl) but don't auto-play
      playItemAudioRef.current(itemId, false);
      return;
    }

    console.log("[AudioSync] card change: playItemAudio", itemId);
    playItemAudioRef.current(itemId);
  }, [
    activeCardIndex,
    hasPerItemAudio,
    feedIndexToStoryIndex,
    itemAudioIds,
    skipAutoPlay,
  ]);

  // Audio ended naturally → advance to next story card
  const wasPlayingRef = useRef(player.isPlaying);
  useEffect(() => {
    if (!hasPerItemAudio || syncMode !== "auto") return;

    const wasPlaying = wasPlayingRef.current;
    wasPlayingRef.current = player.isPlaying;

    // Audio was playing and now stopped near the end → it ended naturally
    if (
      wasPlaying &&
      !player.isPlaying &&
      player.currentAudioItemId !== null &&
      player.duration > 0 &&
      player.currentTime >= player.duration - 0.3
    ) {
      const currentStoryIdx = feedIndexToStoryIndex(activeCardIndex);
      if (currentStoryIdx >= 0) {
        const nextStoryIdx = currentStoryIdx + 1;
        if (nextStoryIdx < totalStoryCards) {
          const nextFeedIdx = storyIndexToFeedIndex(nextStoryIdx);
          if (nextFeedIdx >= 0) {
            setActiveCardIndex(nextFeedIdx);
          }
        }
      }
    }
  }, [
    player.isPlaying,
    player.currentAudioItemId,
    player.currentTime,
    player.duration,
    hasPerItemAudio,
    syncMode,
    activeCardIndex,
    feedIndexToStoryIndex,
    storyIndexToFeedIndex,
    setActiveCardIndex,
    totalStoryCards,
  ]);

  // ── Narrative mode (segment-based, existing behavior) ──────────────────

  // Derive effective segments (fallback to equal duration if missing)
  const effectiveSegments = useEffectiveSegments(
    hasPerItemAudio ? null : segments,
    player.duration,
    totalStoryCards,
  );

  const setSyncSource = useCallback((source: SyncSource) => {
    syncSourceRef.current = source;
    if (syncResetTimer.current) clearTimeout(syncResetTimer.current);
    if (source !== null) {
      syncResetTimer.current = setTimeout(() => {
        syncSourceRef.current = null;
      }, 500);
    }
  }, []);

  // User swipes card → seek audio (with debounce)
  useEffect(() => {
    if (hasPerItemAudio) return;
    if (activeCardIndex === lastCardIndexRef.current) return;
    lastCardIndexRef.current = activeCardIndex;

    // If audio drove this card change, don't seek back
    if (syncSourceRef.current === "audio") return;

    const storyIndex = feedIndexToStoryIndex(activeCardIndex);
    if (storyIndex < 0 || !effectiveSegments || storyIndex >= effectiveSegments.length) return;

    setSyncSource("user");

    // Debounce seek to handle fast swiping
    if (seekDebounceTimer.current) clearTimeout(seekDebounceTimer.current);
    seekDebounceTimer.current = setTimeout(() => {
      const segment = effectiveSegments[storyIndex];
      if (segment) {
        player.seek(segment.start);
      }
    }, 300);
  }, [
    activeCardIndex,
    effectiveSegments,
    feedIndexToStoryIndex,
    player,
    setSyncSource,
    hasPerItemAudio,
  ]);

  // Audio time crosses segment boundary → advance card
  useEffect(() => {
    if (hasPerItemAudio) return;
    if (!player.isPlaying || syncMode !== "auto") return;
    if (syncSourceRef.current === "user") return;
    if (!effectiveSegments || effectiveSegments.length === 0) return;

    const storyIndex = feedIndexToStoryIndex(activeCardIndex);
    if (storyIndex < 0 || storyIndex >= effectiveSegments.length) return;

    const currentSegment = effectiveSegments[storyIndex];
    if (!currentSegment) return;

    // Check if current time has crossed the segment boundary (with 100ms tolerance)
    if (player.currentTime >= currentSegment.end - 0.1) {
      const nextStoryIndex = storyIndex + 1;
      if (nextStoryIndex < effectiveSegments.length) {
        setSyncSource("audio");
        const nextFeedIndex = storyIndexToFeedIndex(nextStoryIndex);
        if (nextFeedIndex >= 0) {
          setActiveCardIndex(nextFeedIndex);
        }
      }
    }
  }, [
    player.currentTime,
    player.isPlaying,
    syncMode,
    activeCardIndex,
    effectiveSegments,
    feedIndexToStoryIndex,
    storyIndexToFeedIndex,
    setActiveCardIndex,
    setSyncSource,
    hasPerItemAudio,
  ]);

  // Cleanup timers
  useEffect(() => {
    return () => {
      if (syncResetTimer.current) clearTimeout(syncResetTimer.current);
      if (seekDebounceTimer.current) clearTimeout(seekDebounceTimer.current);
    };
  }, []);

  const toggleSyncMode = useCallback(() => {
    setSyncMode((prev) => (prev === "auto" ? "manual" : "auto"));
  }, []);

  return { syncMode, toggleSyncMode };
}

/**
 * Derive effective segments: use provided segments or fall back to equal-duration.
 * Returns null when segments is explicitly null (per-item mode).
 */
function useEffectiveSegments(
  segments: AudioSegment[] | null | undefined,
  duration: number,
  totalItems: number,
): AudioSegment[] | null {
  if (segments === null) return null; // per-item mode
  if (segments && segments.length > 0) return segments;
  if (duration <= 0 || totalItems <= 0) return null;

  // Fallback: equal-duration segments
  const segDuration = duration / totalItems;
  return Array.from({ length: totalItems }, (_, i) => ({
    item_id: `fallback-${i}`,
    start: i * segDuration,
    end: (i + 1) * segDuration,
  }));
}
