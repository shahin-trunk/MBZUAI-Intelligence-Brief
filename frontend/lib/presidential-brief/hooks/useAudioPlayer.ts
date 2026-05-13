"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { formatTime } from "@/lib/utils";

type Speed = 1 | 1.25 | 1.5 | 2;
type Language = "en" | "fr" | "ar";

export interface AudioPlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  speed: Speed;
  language: Language;
  hasEnglishAudio: boolean;
  hasFrenchAudio: boolean;
  isLoading: boolean;
  isUnavailable: boolean;
  formattedTime: string;
  formattedDuration: string;
  progress: number;
}

export interface AudioPlayerActions {
  togglePlayPause: () => void;
  seek: (time: number) => void;
  cycleSpeed: () => void;
  setLanguage: (lang: Language) => void;
  audioRef: React.RefObject<HTMLAudioElement | null>;
  /** Per-item audio: register available item audio URLs */
  setItemAudioUrls: (urls: Record<string, string>) => void;
  /** Per-item audio: play audio for a specific item by ID */
  playItemAudio: (itemId: string | null) => void;
  /** ID of the currently playing item (null if playing narrative audio) */
  currentAudioItemId: string | null;
}

const SPEED_CYCLE: Speed[] = [1, 1.25, 1.5, 2];

export function useAudioPlayer(
  audioUrlEn: string | undefined,
  audioUrlFr: string | undefined,
  options?: { onItemEnded?: () => void }
): AudioPlayerState & AudioPlayerActions {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState<Speed>(1);
  const [language, setLanguageState] = useState<Language>("en");
  const [isLoading, setIsLoading] = useState(false);
  // Per-item audio state
  const [itemAudioUrls, setItemAudioUrlsState] = useState<Record<string, string>>({});
  const [currentItemId, setCurrentItemId] = useState<string | null>(null);
  const pendingAutoPlayRef = useRef(false);

  const hasEnglishAudio = Boolean(audioUrlEn);
  const hasFrenchAudio = Boolean(audioUrlFr);

  // Derive current URL: item audio takes precedence over narrative audio
  const narrativeUrl = language === "en" ? audioUrlEn : audioUrlFr;
  const currentUrl = currentItemId && itemAudioUrls[currentItemId]
    ? itemAudioUrls[currentItemId]
    : narrativeUrl;
  const isUnavailable = !currentUrl;

  // Initialize audio element
  useEffect(() => {
    if (!currentUrl) {
      // No URL — reset state
      setDuration(0);
      setCurrentTime(0);
      setIsPlaying(false);
      setIsLoading(false);
      return;
    }

    const audio = new Audio(currentUrl);
    // "metadata" often leaves large gaps unbuffered; paused seeks then fail until enough data loads.
    audio.preload = "auto";
    audioRef.current = audio;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onSeeked = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => {
      setDuration(audio.duration);
      setIsLoading(false);
      // Auto-play if triggered by playItemAudio (per-item mode)
      if (pendingAutoPlayRef.current) {
        pendingAutoPlayRef.current = false;
        audio.play().then(() => {
          setIsPlaying(true);
          setIsLoading(false);
        }).catch(() => {
          setIsLoading(false);
        });
      }
    };
    const onEnded = () => {
      setIsPlaying(false);
      options?.onItemEnded?.();
    };
    const onWaiting = () => setIsLoading(true);
    const onCanPlay = () => setIsLoading(false);

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("seeked", onSeeked);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("waiting", onWaiting);
    audio.addEventListener("canplay", onCanPlay);

    return () => {
      audio.pause();
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("seeked", onSeeked);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("waiting", onWaiting);
      audio.removeEventListener("canplay", onCanPlay);
      audio.src = "";
    };
  }, [currentUrl]);

  // Sync playback rate when speed changes
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = speed;
    }
  }, [speed]);

  const togglePlayPause = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || isUnavailable) return;

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      setIsLoading(true);
      audio.play().then(() => {
        setIsPlaying(true);
        setIsLoading(false);
      }).catch(() => {
        setIsLoading(false);
      });
    }
  }, [isPlaying, isUnavailable]);

  const seek = useCallback((time: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    const d = audio.duration;
    const maxT = Number.isFinite(d) && d > 0 ? d : Number.POSITIVE_INFINITY;
    const clamped = Math.max(0, Math.min(time, maxT));
    audio.currentTime = clamped;
    setCurrentTime(audio.currentTime);
    queueMicrotask(() => {
      const a = audioRef.current;
      if (a) setCurrentTime(a.currentTime);
    });
  }, []);

  const cycleSpeed = useCallback(() => {
    setSpeed((prev) => {
      const idx = SPEED_CYCLE.indexOf(prev);
      return SPEED_CYCLE[(idx + 1) % SPEED_CYCLE.length];
    });
  }, []);

  // Register per-item audio URLs
  const setItemAudioUrls = useCallback((urls: Record<string, string>) => {
    setItemAudioUrlsState(urls);
  }, []);

  // Play audio for a specific item; null stops per-item playback (falls back to narrative)
  const playItemAudio = useCallback((itemId: string | null) => {
    setCurrentItemId(itemId);
    if (itemId !== null) {
      pendingAutoPlayRef.current = true;
    }
  }, []);

  const setLanguage = useCallback(
    (lang: Language) => {
      if (lang === language) return;
      const savedTime = audioRef.current?.currentTime ?? 0;
      const wasPlaying = isPlaying;

      // Pause current playback — new audio element will be created by effect
      if (audioRef.current) {
        audioRef.current.pause();
        setIsPlaying(false);
      }

      setLanguageState(lang);

      // After language switch, the effect will re-create the audio element.
      // We need to seek and optionally resume after it loads metadata.
      // We store these as refs so the effect can use them.
      pendingSeekRef.current = savedTime;
      pendingPlayRef.current = wasPlaying;
    },
    [language, isPlaying]
  );

  const pendingSeekRef = useRef<number | null>(null);
  const pendingPlayRef = useRef<boolean>(false);

  // After language switch, seek to saved position when metadata loads
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onLoaded = () => {
      if (pendingSeekRef.current !== null) {
        audio.currentTime = pendingSeekRef.current;
        setCurrentTime(pendingSeekRef.current);
        pendingSeekRef.current = null;
      }
      if (pendingPlayRef.current) {
        pendingPlayRef.current = false;
        audio.play().then(() => setIsPlaying(true)).catch(() => {});
      }
    };

    audio.addEventListener("loadedmetadata", onLoaded);
    return () => audio.removeEventListener("loadedmetadata", onLoaded);
  }, [language]); // re-attach when language changes (new audio element)

  const progress = duration > 0 ? currentTime / duration : 0;
  const formattedTime = formatTime(currentTime);
  const formattedDuration = duration > 0 ? formatTime(duration) : "--:--";

  return {
    isPlaying,
    currentTime,
    duration,
    speed,
    language,
    hasEnglishAudio,
    hasFrenchAudio,
    isLoading,
    isUnavailable,
    formattedTime,
    formattedDuration,
    progress,
    togglePlayPause,
    seek,
    cycleSpeed,
    setLanguage,
    audioRef,
    setItemAudioUrls,
    playItemAudio,
    currentAudioItemId: currentItemId,
  };
}
