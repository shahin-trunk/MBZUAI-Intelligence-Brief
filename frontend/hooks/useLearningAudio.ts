"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { formatTime } from "@/lib/utils";

interface LearningAudioState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  speed: number;
  isLoading: boolean;
  formattedTime: string;
  formattedDuration: string;
}

interface LearningAudioActions {
  togglePlayPause: () => void;
  seek: (time: number) => void;
  cycleSpeed: () => void;
  stepBack: () => void;
  stepForward: () => void;
}

const SPEED_CYCLE = [0.5, 0.75, 1] as const;

export function useLearningAudio(
  audioUrl: string | undefined,
): LearningAudioState & LearningAudioActions {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState<number>(1);
  const [isLoading, setIsLoading] = useState(false);

  // Initialize audio element when URL changes
  useEffect(() => {
    if (!audioUrl) {
      setDuration(0);
      setCurrentTime(0);
      setIsPlaying(false);
      setIsLoading(false);
      return;
    }

    const audio = new Audio(audioUrl);
    audio.preload = "auto";
    audioRef.current = audio;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => {
      setDuration(audio.duration);
      setIsLoading(false);
    };
    const onEnded = () => setIsPlaying(false);
    const onWaiting = () => setIsLoading(true);
    const onCanPlay = () => setIsLoading(false);
    const onError = () => {
      setIsLoading(false);
      setIsPlaying(false);
    };

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("waiting", onWaiting);
    audio.addEventListener("canplay", onCanPlay);
    audio.addEventListener("error", onError);

    return () => {
      audio.pause();
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("waiting", onWaiting);
      audio.removeEventListener("canplay", onCanPlay);
      audio.removeEventListener("error", onError);
      audio.src = "";
    };
  }, [audioUrl]);

  // Sync playback rate when speed changes
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = speed;
    }
  }, [speed]);

  const togglePlayPause = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !audioUrl) return;

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      setIsLoading(true);
      audio
        .play()
        .then(() => {
          setIsPlaying(true);
          setIsLoading(false);
        })
        .catch(() => {
          setIsLoading(false);
        });
    }
  }, [isPlaying, audioUrl]);

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

  const stepBack = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      seek(Math.max(0, audio.currentTime - 5));
    }
  }, [seek]);

  const stepForward = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      const d = audio.duration;
      const maxT = Number.isFinite(d) && d > 0 ? d : 3600;
      seek(Math.min(maxT, audio.currentTime + 5));
    }
  }, [seek]);

  const cycleSpeed = useCallback(() => {
    setSpeed((prev) => {
      const idx = SPEED_CYCLE.indexOf(prev as typeof SPEED_CYCLE[number]);
      if (idx < 0) return SPEED_CYCLE[0];
      return SPEED_CYCLE[(idx + 1) % SPEED_CYCLE.length];
    });
  }, []);

  return {
    isPlaying,
    currentTime,
    duration,
    speed,
    isLoading,
    formattedTime: formatTime(currentTime),
    formattedDuration: duration > 0 ? formatTime(duration) : "--:--",
    togglePlayPause,
    seek,
    cycleSpeed,
    stepBack,
    stepForward,
  };
}
