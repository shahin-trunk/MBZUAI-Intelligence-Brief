"use client";

import { useState, useEffect, useRef, useCallback } from "react";

export interface SectionAudioState {
  /** Index of the currently active section in the playlist */
  currentSectionIndex: number;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  speed: number;
  isLoading: boolean;
}

export interface SectionAudioActions {
  playSection: (index: number) => void;
  togglePlayPause: () => void;
  pause: () => void;
  nextSection: () => void;
  prevSection: () => void;
  seek: (time: number) => void;
  cycleSpeed: () => void;
}

const SPEED_CYCLE = [0.75, 1, 1.25];

/**
 * Manages an ordered playlist of section audio URLs with auto-advance.
 *
 * When one section's audio ends, fires `onSectionComplete` and optionally
 * advances to the next section (if `autoAdvance` is true).
 */
export function useSectionAudio(
  /** Ordered audio URLs per section. `undefined` entries = no audio for that section. */
  sectionAudioUrls: (string | undefined)[],
  options?: {
    autoAdvance?: boolean;
    onSectionComplete?: (index: number) => void;
    onAllComplete?: () => void;
  },
): SectionAudioState & SectionAudioActions {
  const { autoAdvance = true, onSectionComplete, onAllComplete } = options ?? {};

  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const pendingPlayRef = useRef(false);
  const sectionUrlsRef = useRef(sectionAudioUrls);
  sectionUrlsRef.current = sectionAudioUrls;

  // Stable callback refs
  const onSectionCompleteRef = useRef(onSectionComplete);
  onSectionCompleteRef.current = onSectionComplete;
  const onAllCompleteRef = useRef(onAllComplete);
  onAllCompleteRef.current = onAllComplete;

  // Create / swap audio element when section changes
  useEffect(() => {
    const url = sectionAudioUrls[currentSectionIndex];

    // Tear down previous
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.removeAttribute("src");
      audioRef.current.load();
      audioRef.current = null;
    }

    setCurrentTime(0);
    setDuration(0);
    setIsPlaying(false);

    if (!url) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    const audio = new Audio(url);
    audio.preload = "auto";
    audio.playbackRate = speed;
    audioRef.current = audio;

    const onLoadedMetadata = () => {
      setDuration(audio.duration);
      setIsLoading(false);
      if (pendingPlayRef.current) {
        pendingPlayRef.current = false;
        audio.play().then(() => setIsPlaying(true)).catch(() => {});
      }
    };

    const onTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
    };

    const onEnded = () => {
      setIsPlaying(false);
      onSectionCompleteRef.current?.(currentSectionIndex);

      if (autoAdvance) {
        const nextIdx = currentSectionIndex + 1;
        // Find the next section that has audio
        let target = nextIdx;
        while (target < sectionUrlsRef.current.length && !sectionUrlsRef.current[target]) {
          target++;
        }
        if (target < sectionUrlsRef.current.length) {
          pendingPlayRef.current = true;
          setCurrentSectionIndex(target);
        } else {
          onAllCompleteRef.current?.();
        }
      }
    };

    const onWaiting = () => setIsLoading(true);
    const onCanPlay = () => setIsLoading(false);
    const onError = () => {
      setIsLoading(false);
      setIsPlaying(false);
    };

    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("waiting", onWaiting);
    audio.addEventListener("canplay", onCanPlay);
    audio.addEventListener("error", onError);

    return () => {
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("waiting", onWaiting);
      audio.removeEventListener("canplay", onCanPlay);
      audio.removeEventListener("error", onError);
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSectionIndex, sectionAudioUrls, autoAdvance]);

  // Keep playback rate in sync with speed state
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = speed;
    }
  }, [speed]);

  const togglePlayPause = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().then(() => setIsPlaying(true)).catch(() => {});
    } else {
      audio.pause();
      setIsPlaying(false);
    }
  }, []);

  const pause = useCallback(() => {
    if (audioRef.current && !audioRef.current.paused) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  }, []);

  const seek = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  }, []);

  const cycleSpeed = useCallback(() => {
    setSpeed((prev) => {
      const idx = SPEED_CYCLE.indexOf(prev);
      return SPEED_CYCLE[(idx + 1) % SPEED_CYCLE.length];
    });
  }, []);

  const playSection = useCallback((index: number) => {
    if (index < 0 || index >= sectionUrlsRef.current.length) return;
    pendingPlayRef.current = true;
    setCurrentSectionIndex(index);
  }, []);

  const nextSection = useCallback(() => {
    let target = currentSectionIndex + 1;
    while (target < sectionUrlsRef.current.length && !sectionUrlsRef.current[target]) {
      target++;
    }
    if (target < sectionUrlsRef.current.length) {
      pendingPlayRef.current = true;
      setCurrentSectionIndex(target);
    }
  }, [currentSectionIndex]);

  const prevSection = useCallback(() => {
    // If >3s into current section, restart it; otherwise go to previous
    if (audioRef.current && audioRef.current.currentTime > 3) {
      audioRef.current.currentTime = 0;
      setCurrentTime(0);
      return;
    }
    let target = currentSectionIndex - 1;
    while (target >= 0 && !sectionUrlsRef.current[target]) {
      target--;
    }
    if (target >= 0) {
      pendingPlayRef.current = true;
      setCurrentSectionIndex(target);
    }
  }, [currentSectionIndex]);

  return {
    currentSectionIndex,
    isPlaying,
    currentTime,
    duration,
    speed,
    isLoading,
    playSection,
    togglePlayPause,
    pause,
    nextSection,
    prevSection,
    seek,
    cycleSpeed,
  };
}
