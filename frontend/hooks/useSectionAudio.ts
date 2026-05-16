"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";

export interface SectionAudioState {
  currentSectionIndex: number;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  speed: number;
  isLoading: boolean;
  overallProgress: number;
  totalDuration: number;
  elapsedTotal: number;
  sectionProgress: number;
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

// ---------------------------------------------------------------------------
// Global Audio Registry — tracks ALL Audio objects across the app (DOM + non-DOM)
// ---------------------------------------------------------------------------
const GLOBAL_AUDIO_REGISTRY = new Set<HTMLAudioElement>();

export function registerAudio(el: HTMLAudioElement) {
  GLOBAL_AUDIO_REGISTRY.add(el);
}

export function unregisterAudio(el: HTMLAudioElement) {
  GLOBAL_AUDIO_REGISTRY.delete(el);
}

/**
 * Kill every <audio> and Audio object on the page.
 * Prevents echo from brief-page audio bleeding through client-side navigation.
 */
function killAllPageAudio() {
  if (typeof document === "undefined") return;
  // Kill DOM-attached audio elements
  document.querySelectorAll("audio").forEach((el) => {
    el.pause();
    el.removeAttribute("src");
    el.load();
  });
  // Kill non-DOM Audio objects that other hooks created via `new Audio()`
  GLOBAL_AUDIO_REGISTRY.forEach((audio) => {
    try {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    } catch {
      // Already destroyed
    }
  });
  GLOBAL_AUDIO_REGISTRY.clear();
}

export function useSectionAudio(
  sectionAudioUrls: (string | undefined)[],
  options?: {
    autoAdvance?: boolean;
    estimatedDurations?: number[];
    onSectionComplete?: (index: number) => void;
    onAllComplete?: () => void;
  },
): SectionAudioState & SectionAudioActions {
  const {
    autoAdvance = true,
    estimatedDurations,
    onSectionComplete,
    onAllComplete,
  } = options ?? {};

  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  // Counter to force effect re-run even when index stays the same
  const [epoch, setEpoch] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const pendingPlayRef = useRef(false);
  const sectionUrlsRef = useRef(sectionAudioUrls);
  sectionUrlsRef.current = sectionAudioUrls;

  const urlsKey = sectionAudioUrls.map((u) => u ?? "").join("|");

  const onSectionCompleteRef = useRef(onSectionComplete);
  onSectionCompleteRef.current = onSectionComplete;
  const onAllCompleteRef = useRef(onAllComplete);
  onAllCompleteRef.current = onAllComplete;

  const estimatedDurationsRef = useRef(estimatedDurations);
  estimatedDurationsRef.current = estimatedDurations;

  // On first mount: kill ALL audio on the page (brief player, stale elements)
  useEffect(() => {
    killAllPageAudio();
    return () => {
      // On unmount: destroy our audio element completely
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.removeAttribute("src");
        audioRef.current.load();
        audioRef.current = null;
      }
    };
  }, []);

  const findNextWithAudio = useCallback(
    (startIdx: number): number | null => {
      let target = startIdx;
      while (target < sectionUrlsRef.current.length && !sectionUrlsRef.current[target]) {
        target++;
      }
      return target < sectionUrlsRef.current.length ? target : null;
    },
    [],
  );

  // Main effect: set up audio for current section
  // `epoch` in deps ensures re-run even when index stays at 0
  useEffect(() => {
    const url = sectionUrlsRef.current[currentSectionIndex];

    // Destroy previous audio element entirely
    if (audioRef.current) {
      const old = audioRef.current;
      old.pause();
      old.removeAttribute("src");
      old.load();
      unregisterAudio(old);
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

    // Create a FRESH audio element each time — no singleton tricks
    const audio = new Audio();
    audio.preload = "auto";
    audio.playbackRate = speed;
    registerAudio(audio);
    audioRef.current = audio;

    const onLoadedMetadata = () => {
      // Guard: only act if this is still the active audio
      if (audioRef.current !== audio) return;
      setDuration(audio.duration);
      setIsLoading(false);
      if (pendingPlayRef.current) {
        pendingPlayRef.current = false;
        audio.play().then(() => {
          if (audioRef.current === audio) setIsPlaying(true);
        }).catch(() => {});
      }
    };

    const onTimeUpdate = () => {
      if (audioRef.current === audio) setCurrentTime(audio.currentTime);
    };

    const onEnded = () => {
      if (audioRef.current !== audio) return;
      setIsPlaying(false);
      onSectionCompleteRef.current?.(currentSectionIndex);

      if (autoAdvance) {
        const nextIdx = findNextWithAudio(currentSectionIndex + 1);
        if (nextIdx !== null) {
          pendingPlayRef.current = true;
          setCurrentSectionIndex(nextIdx);
        } else {
          onAllCompleteRef.current?.();
        }
      }
    };

    const onWaiting = () => { if (audioRef.current === audio) setIsLoading(true); };
    const onCanPlay = () => { if (audioRef.current === audio) setIsLoading(false); };
    const onError = () => {
      if (audioRef.current !== audio) return;
      setIsLoading(false);
      setIsPlaying(false);
      if (autoAdvance) {
        const nextIdx = findNextWithAudio(currentSectionIndex + 1);
        if (nextIdx !== null) {
          pendingPlayRef.current = true;
          setCurrentSectionIndex(nextIdx);
        }
      }
    };

    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("waiting", onWaiting);
    audio.addEventListener("canplay", onCanPlay);
    audio.addEventListener("error", onError);

    // Set src AFTER adding listeners so loadedmetadata is never missed
    audio.src = url;
    audio.load();

    return () => {
      unregisterAudio(audio);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("waiting", onWaiting);
      audio.removeEventListener("canplay", onCanPlay);
      audio.removeEventListener("error", onError);
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      if (audioRef.current === audio) audioRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSectionIndex, urlsKey, autoAdvance, epoch]);

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = speed;
  }, [speed]);

  const totalDuration = useMemo(() => {
    if (!estimatedDurations || estimatedDurations.length === 0) return 0;
    return estimatedDurations.reduce((sum, d) => sum + (d || 0), 0);
  }, [estimatedDurations]);

  const elapsedTotal = useMemo(() => {
    if (!estimatedDurations || estimatedDurations.length === 0) return 0;
    let elapsed = 0;
    for (let i = 0; i < currentSectionIndex; i++) {
      elapsed += estimatedDurations[i] || 0;
    }
    elapsed += currentTime;
    return elapsed;
  }, [estimatedDurations, currentSectionIndex, currentTime]);

  const overallProgress = useMemo(() => {
    if (totalDuration <= 0) return 0;
    return Math.min(1, Math.max(0, elapsedTotal / totalDuration));
  }, [elapsedTotal, totalDuration]);

  const sectionProgress = useMemo(() => {
    if (duration <= 0) return 0;
    return Math.min(1, Math.max(0, currentTime / duration));
  }, [currentTime, duration]);

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
    const audio = audioRef.current;
    if (audio && !audio.paused) {
      audio.pause();
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

  // playSection uses epoch counter to force effect re-run even at same index
  const playSection = useCallback((index: number) => {
    if (index < 0 || index >= sectionUrlsRef.current.length) return;
    pendingPlayRef.current = true;
    setCurrentSectionIndex(index);
    setEpoch((e) => e + 1); // Force effect re-run
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
    overallProgress,
    totalDuration,
    elapsedTotal,
    sectionProgress,
    playSection,
    togglePlayPause,
    pause,
    nextSection,
    prevSection,
    seek,
    cycleSpeed,
  };
}
