"use client";

import { useRef, useEffect, useState } from "react";
import { ChevronUp, Play, Pause } from "lucide-react";
import type { PhraseGrammar } from "@/lib/types/brief";

interface PhraseGrammarDrawerProps {
  grammar: PhraseGrammar;
  script4AudioUrl?: string;
  script4Text?: string;
  isOpen: boolean;
  onToggle: () => void;
  language: "fr" | "ar";
}

export default function PhraseGrammarDrawer({
  grammar,
  script4AudioUrl,
  isOpen,
  onToggle,
  language,
}: PhraseGrammarDrawerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!script4AudioUrl) return;

    const audio = new Audio(script4AudioUrl);
    audioRef.current = audio;

    const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
    const handleLoadedMetadata = () => setDuration(audio.duration);
    const handleEnded = () => setIsPlaying(false);
    const handleError = () => setIsPlaying(false);

    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("error", handleError);

    return () => {
      audio.pause();
      audio.removeAttribute("src");
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("error", handleError);
    };
  }, [script4AudioUrl]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  if (!isOpen) {
    return null;
  }

  const grammarFields: { key: keyof PhraseGrammar; label: string }[] = [
    { key: "morphology", label: "Morphology" },
    { key: "etymology", label: "Etymology" },
    { key: "conjugation", label: "Conjugation" },
    { key: "register", label: "Register" },
    { key: "phonetic_guide", label: "Pronunciation" },
    { key: "usage_notes", label: "Usage Notes" },
  ];

  const activeFields = grammarFields.filter(
    (f) => grammar[f.key] && grammar[f.key]!.length > 0,
  );

  return (
    <div className="mt-6 animate-slide-up">
      {/* Audio playback for Script4 */}
      {script4AudioUrl && (
        <div className="flex items-center gap-3 mb-4 pb-3 border-b border-border-subtle">
          <button
            onClick={togglePlay}
            className="flex items-center justify-center w-8 h-8 rounded-full bg-accent-primary/10 text-accent-primary hover:bg-accent-primary/20 transition-colors cursor-pointer"
          >
            {isPlaying ? (
              <Pause className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4" />
            )}
          </button>
          <div className="flex-1 h-1 bg-border-subtle rounded-full overflow-hidden">
            <div
              className="h-full bg-accent-primary transition-all duration-200"
              style={{
                width: duration > 0 ? `${(currentTime / duration) * 100}%` : "0%",
              }}
            />
          </div>
          <span className="text-xs text-text-secondary/60 font-mono">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
        </div>
      )}

      {/* Grammar metadata cards */}
      <div className="space-y-3">
        {activeFields.map(({ key, label }, idx) => (
          <div
            key={key}
            className="rounded-xl border border-border-subtle bg-surface/40 p-4"
            style={{ animationDelay: `${idx * 150}ms` }}
          >
            <div className="flex items-start gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary/60 shrink-0 w-24">
                {label}
              </span>
              <span
                dir={language === "ar" ? "rtl" : "ltr"}
                className="font-body text-[15px] text-text-primary"
              >
                {grammar[key]}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Collapse button */}
      <div className="flex justify-center mt-4">
        <button
          onClick={onToggle}
          className="flex items-center gap-1 text-sm text-text-secondary/60 hover:text-text-primary transition-colors cursor-pointer"
        >
          <ChevronUp className="w-4 h-4" />
          Collapse
        </button>
      </div>
    </div>
  );
}

function formatTime(seconds: number): string {
  if (!seconds || !isFinite(seconds)) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
