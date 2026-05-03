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
}

/**
 * Bidirectional audio-visual sync hook.
 *
 * Composes with (does not wrap) useAudioPlayer.
 * Uses a syncSource ownership flag to prevent feedback loops:
 * - When audio advances a card, syncSource='audio' suppresses seek
 * - When user swipes, syncSource='user' suppresses auto-advance
 * - Reset to null after 500ms
 */
export function useAudioCardSync({
  player,
  segments,
  activeCardIndex,
  setActiveCardIndex,
  feedIndexToStoryIndex,
  storyIndexToFeedIndex,
  totalStoryCards,
}: UseAudioCardSyncOptions) {
  const [syncMode, setSyncMode] = useState<SyncMode>("auto");
  const syncSourceRef = useRef<SyncSource>(null);
  const syncResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seekDebounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastCardIndexRef = useRef(activeCardIndex);

  // Derive effective segments (fallback to equal duration if missing)
  const effectiveSegments = useEffectiveSegments(segments, player.duration, totalStoryCards);

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
  }, [activeCardIndex, effectiveSegments, feedIndexToStoryIndex, player, setSyncSource]);

  // Audio time crosses segment boundary → advance card
  useEffect(() => {
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
 */
function useEffectiveSegments(
  segments: AudioSegment[] | undefined,
  duration: number,
  totalItems: number
): AudioSegment[] | null {
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
