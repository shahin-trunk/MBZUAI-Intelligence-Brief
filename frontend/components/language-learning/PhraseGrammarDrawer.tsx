"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Play, Pause, X, Loader2, AlertCircle } from "lucide-react";
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
  script4Text,
  isOpen,
  onToggle,
  language,
}: PhraseGrammarDrawerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [touchStartY, setTouchStartY] = useState<number | null>(null);
  const [translateY, setTranslateY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!script4AudioUrl) return;

    setIsLoading(true);
    setHasError(false);

    const audio = new Audio(script4AudioUrl);
    audioRef.current = audio;
    audio.preload = "auto";

    const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
      setIsLoading(false);
    };
    const handleCanPlayThrough = () => {
      setIsLoading(false);
    };
    const handleEnded = () => setIsPlaying(false);
    const handleError = () => {
      setIsPlaying(false);
      setIsLoading(false);
      setHasError(true);
    };
    const handleLoadStart = () => {
      setIsLoading(true);
      setHasError(false);
    };

    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("canplaythrough", handleCanPlayThrough);
    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("error", handleError);
    audio.addEventListener("loadstart", handleLoadStart);

    return () => {
      audio.pause();
      audio.removeAttribute("src");
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("canplaythrough", handleCanPlayThrough);
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("error", handleError);
      audio.removeEventListener("loadstart", handleLoadStart);
    };
  }, [script4AudioUrl]);

  const togglePlay = useCallback(() => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  }, [isPlaying]);

  // Reset transform when opened
  useEffect(() => {
    if (isOpen) {
      setTranslateY(0);
      setIsDragging(false);
    }
  }, [isOpen]);

  // Swipe-to-dismiss handlers for mobile bottom sheet
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    setTouchStartY(e.touches[0].clientY);
    setIsDragging(true);
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isDragging || touchStartY === null) return;

    const deltaY = e.touches[0].clientY - touchStartY;
    // Only allow downward swipe (positive delta)
    if (deltaY > 0) {
      setTranslateY(deltaY);
    }
  }, [isDragging, touchStartY]);

  const handleTouchEnd = useCallback(() => {
    if (translateY > 100) {
      // Swiped far enough - close
      onToggle();
    } else {
      // Snap back to original position
      setTranslateY(0);
    }
    setTouchStartY(null);
    setIsDragging(false);
  }, [translateY, onToggle]);

  if (!isOpen) return null;

  const grammarFields: { key: keyof PhraseGrammar; label: string; icon: string }[] = [
    { key: "morphology", label: "Morphology", icon: "🔤" },
    { key: "etymology", label: "Etymology", icon: "📜" },
    { key: "conjugation", label: "Conjugation", icon: "🔀" },
    { key: "register", label: "Register", icon: "🎯" },
    { key: "phonetic_guide", label: "Pronunciation", icon: "🔊" },
    { key: "usage_notes", label: "Usage Notes", icon: "💡" },
  ];

  const activeFields = grammarFields.filter(
    (f) => grammar[f.key] && grammar[f.key]!.length > 0,
  );

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 animate-in fade-in duration-300 sm:bg-black/20"
        onClick={onToggle}
        aria-hidden="true"
      />

      {/* Bottom sheet container */}
      <div
        ref={containerRef}
        className="fixed bottom-0 left-0 right-0 z-50 animate-in slide-in-from-bottom duration-500 sm:relative sm:animate-in sm:slide-in-from-bottom-4 sm:duration-300 sm:mt-6 sm:mx-auto sm:max-w-[560px] sm:rounded-2xl"
        style={{
          transform: translateY > 0 ? `translateY(${translateY}px)` : undefined,
          transition: isDragging ? "none" : "transform 0.3s ease-out",
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        role="dialog"
        aria-modal="true"
        aria-label="Grammar deep dive panel"
      >
        {/* Mobile bottom sheet card */}
        <div className="sm:hidden bg-bg-surface border-t border-rule/30 rounded-t-3xl max-h-[85vh] flex flex-col shadow-2xl">
          {/* Drag handle */}
          <div className="flex justify-center py-3 border-b border-rule/10">
            <div className="w-10 h-1 rounded-full bg-rule/40" />
          </div>

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-rule/20">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-accent-primary animate-pulse" />
              <h3 className="font-ui text-sm font-semibold text-text-primary uppercase tracking-wide">
                Teacher's Deep Dive
              </h3>
            </div>
            <button
              onClick={onToggle}
              className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-bg-surface-2 transition-colors"
              aria-label="Close grammar panel"
            >
              <X className="w-4 h-4 text-text-secondary" />
            </button>
          </div>

          {/* Audio playback for Script4 - teacher's narration */}
          {script4AudioUrl && (
            <div className="px-4 py-3 border-b border-rule/20">
              {hasError ? (
                <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/20">
                  <AlertCircle className="w-4 h-4 text-red-500/70 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-text-secondary font-body">
                      Audio unavailable
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <button
                    onClick={togglePlay}
                    disabled={isLoading}
                    className="flex items-center justify-center w-10 h-10 rounded-full bg-accent-primary/10 text-accent-primary hover:bg-accent-primary/20 transition-colors cursor-pointer shrink-0 disabled:opacity-50"
                    aria-label={isPlaying ? "Pause narration" : "Play narration"}
                  >
                    {isLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : isPlaying ? (
                      <Pause className="w-4 h-4" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="h-1.5 bg-rule/20 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent-primary transition-all duration-200 rounded-full"
                        style={{
                          width: duration > 0 ? `${(currentTime / duration) * 100}%` : "0%",
                        }}
                      />
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-[10px] text-text-muted font-mono">
                        {formatTime(currentTime)}
                      </span>
                      <span className="text-[10px] text-text-muted font-mono">
                        {formatTime(duration)}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Script4: Teacher's deep narration — main content */}
          {script4Text && (
            <div className="px-4 py-4 border-b border-rule/20 bg-accent-primary/5">
              <div className="flex items-start gap-2 mb-2">
                <span className="text-xs" role="img" aria-label="teacher">👨‍🏫</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Teacher's Narration
                </span>
              </div>
              <p className="font-body text-[13px] sm:text-[14px] text-text-primary leading-relaxed">
                {script4Text}
              </p>
            </div>
          )}

          {/* Grammar breakdown cards — secondary content */}
          <div className="divide-y divide-rule/10 overflow-y-auto flex-1" style={{ maxHeight: "calc(85vh - 200px)" }}>
            {activeFields.length > 0 && (
              <div className="px-4 py-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Grammar Breakdown
                </span>
              </div>
            )}
            {activeFields.map(({ key, label, icon }, idx) => (
              <div
                key={key}
                className="px-4 py-3.5 animate-in fade-in duration-300"
                style={{ animationDelay: `${idx * 100}ms` }}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-bg-surface/80 border border-rule/20">
                    <span className="text-xs" role="img" aria-hidden>{icon}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block mb-1">
                      {label}
                    </span>
                    <p
                      dir={language === "ar" ? "rtl" : "ltr"}
                      className="font-body text-[13px] text-text-secondary leading-relaxed"
                    >
                      {grammar[key]}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Safe area padding for mobile */}
          <div className="h-4 sm:h-0" />
        </div>

        {/* Desktop card version */}
        <div className="hidden sm:block rounded-2xl border border-rule/50 bg-bg-surface/30 backdrop-blur-sm overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-rule/20">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-accent-primary animate-pulse" />
              <h3 className="font-ui text-sm font-semibold text-text-primary uppercase tracking-wide">
                Teacher's Deep Dive
              </h3>
            </div>
            <button
              onClick={onToggle}
              className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-bg-surface/50 transition-colors"
              aria-label="Close grammar panel"
            >
              <X className="w-4 h-4 text-text-secondary" />
            </button>
          </div>

          {/* Audio playback for Script4 - teacher's narration */}
          {script4AudioUrl && (
            <div className="px-5 py-3 border-b border-rule/20">
              {hasError ? (
                <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/20">
                  <AlertCircle className="w-4 h-4 text-red-500/70 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-text-secondary font-body">
                      Audio unavailable
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <button
                    onClick={togglePlay}
                    disabled={isLoading}
                    className="flex items-center justify-center w-10 h-10 rounded-full bg-accent-primary/10 text-accent-primary hover:bg-accent-primary/20 transition-colors cursor-pointer shrink-0 disabled:opacity-50"
                    aria-label={isPlaying ? "Pause narration" : "Play narration"}
                  >
                    {isLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : isPlaying ? (
                      <Pause className="w-4 h-4" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="h-1.5 bg-rule/20 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent-primary transition-all duration-200 rounded-full"
                        style={{
                          width: duration > 0 ? `${(currentTime / duration) * 100}%` : "0%",
                        }}
                      />
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-[10px] text-text-muted font-mono">
                        {formatTime(currentTime)}
                      </span>
                      <span className="text-[10px] text-text-muted font-mono">
                        {formatTime(duration)}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Script4: Teacher's deep narration — main content */}
          {script4Text && (
            <div className="px-5 py-4 border-b border-rule/20 bg-accent-primary/5">
              <div className="flex items-start gap-2 mb-2">
                <span className="text-xs" role="img" aria-label="teacher">👨‍🏫</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Teacher's Narration
                </span>
              </div>
              <p className="font-body text-[14px] text-text-primary leading-relaxed">
                {script4Text}
              </p>
            </div>
          )}

          {/* Grammar breakdown cards — secondary content */}
          <div className="divide-y divide-rule/10 max-h-[50vh] overflow-y-auto">
            {activeFields.length > 0 && (
              <div className="px-5 py-2">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Grammar Breakdown
                </span>
              </div>
            )}
            {activeFields.map(({ key, label, icon }, idx) => (
              <div
                key={key}
                className="px-5 py-3.5 animate-in fade-in duration-300"
                style={{ animationDelay: `${idx * 100}ms` }}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-bg-surface/80 border border-rule/20">
                    <span className="text-xs" role="img" aria-hidden>{icon}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block mb-1">
                      {label}
                    </span>
                    <p
                      dir={language === "ar" ? "rtl" : "ltr"}
                      className="font-body text-[14px] text-text-secondary leading-relaxed"
                    >
                      {grammar[key]}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="flex justify-center px-5 py-3 border-t border-rule/10">
            <button
              onClick={onToggle}
              className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-text-muted">
                <path d="M3 5L7 9L11 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Close deep dive
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

function formatTime(seconds: number): string {
  if (!seconds || !isFinite(seconds)) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
