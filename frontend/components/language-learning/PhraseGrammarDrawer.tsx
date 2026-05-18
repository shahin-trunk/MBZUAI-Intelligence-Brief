"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Play, Pause, X, Loader2, AlertCircle, ChevronDown } from "lucide-react";
import type { PhraseGrammar } from "@/lib/types/brief";
import { registerAudio, unregisterAudio, killAllPageAudio } from "@/hooks/useSectionAudio";

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
    killAllPageAudio();
    setIsLoading(true);
    setHasError(false);

    const audio = new Audio(script4AudioUrl);
    audio.preload = "auto";
    registerAudio(audio);
    audioRef.current = audio;

    const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
      setIsLoading(false);
    };
    const handleCanPlayThrough = () => setIsLoading(false);
    const handleEnded = () => {
      setIsPlaying(false);
      unregisterAudio(audio);
    };
    const handleError = () => {
      setIsPlaying(false);
      setIsLoading(false);
      setHasError(true);
      unregisterAudio(audio);
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
      unregisterAudio(audio);
      audio.removeAttribute("src");
      audio.load();
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
      killAllPageAudio();
      registerAudio(audioRef.current);
      audioRef.current.play();
      setIsPlaying(true);
    }
  }, [isPlaying]);

  useEffect(() => {
    if (isOpen) {
      setTranslateY(0);
      setIsDragging(false);
    }
  }, [isOpen]);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    setTouchStartY(e.touches[0].clientY);
    setIsDragging(true);
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isDragging || touchStartY === null) return;
    const deltaY = e.touches[0].clientY - touchStartY;
    if (deltaY > 0) setTranslateY(deltaY);
  }, [isDragging, touchStartY]);

  const handleTouchEnd = useCallback(() => {
    if (translateY > 100) {
      onToggle();
    } else {
      setTranslateY(0);
    }
    setTouchStartY(null);
    setIsDragging(false);
  }, [translateY, onToggle]);

  if (!isOpen) return null;

  const grammarFields: { key: keyof PhraseGrammar; label: string }[] = [
    { key: "syntax", label: "Sentence Structure" },
    { key: "phonetic_features", label: "Phonetic Features" },
    { key: "morphology", label: "Morphology" },
    { key: "etymology", label: "Etymology" },
    { key: "conjugation", label: "Conjugation" },
    { key: "register", label: "Register" },
    { key: "phonetic_guide", label: "Pronunciation" },
    { key: "usage_notes", label: "Usage Notes" },
    { key: "cognate_note", label: "English Cognates" },
  ];

  const activeFields = grammarFields.filter((f) => {
    const val = grammar[f.key];
    if (!val) return false;
    if (Array.isArray(val)) return val.length > 0;
    return typeof val === "string" && val.length > 0;
  });

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 animate-in fade-in duration-300"
        onClick={onToggle}
        aria-hidden="true"
      />

      {/* Bottom sheet */}
      <div
        ref={containerRef}
        className="fixed bottom-0 left-0 right-0 z-50 animate-in slide-in-from-bottom duration-500 sm:relative sm:animate-in sm:slide-in-from-bottom-4 sm:duration-300 sm:mt-6 sm:mx-auto sm:max-w-[560px] sm:rounded-2xl"
        style={{
          transform: translateY > 0 ? `translateY(${translateY}px)` : undefined,
          transition: isDragging ? "none" : "transform 0.35s cubic-bezier(0.32, 0.72, 0, 1)",
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        role="dialog"
        aria-modal="true"
        aria-label="Grammar deep dive"
      >
        {/* Mobile */}
        <div className="sm:hidden bg-gray-950 border-t border-gray-800/50 rounded-t-3xl max-h-[85vh] flex flex-col shadow-2xl">
          {/* Handle */}
          <div className="flex justify-center py-3 border-b border-gray-800/20">
            <div className="w-10 h-1 rounded-full bg-gray-700/40" />
          </div>

          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800/20">
            <h3 className="font-ui text-xs font-semibold text-gray-300 uppercase tracking-wider">
              Deep Dive
            </h3>
            <button
              onClick={onToggle}
              className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-gray-800/50 transition-colors"
              aria-label="Close"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>

          {/* Script4 audio */}
          {script4AudioUrl && (
            <div className="px-5 py-3 border-b border-gray-800/20">
              {hasError ? (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/20">
                  <AlertCircle className="w-3.5 h-3.5 text-red-400/70 shrink-0" />
                  <p className="text-[11px] text-gray-400">Audio unavailable</p>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <button
                    onClick={togglePlay}
                    disabled={isLoading}
                    className="flex items-center justify-center w-9 h-9 rounded-full bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 transition-colors shrink-0 disabled:opacity-50"
                    aria-label={isPlaying ? "Pause" : "Play"}
                  >
                    {isLoading ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : isPlaying ? (
                      <Pause className="w-3.5 h-3.5" />
                    ) : (
                      <Play className="w-3.5 h-3.5" />
                    )}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="h-1 bg-gray-800/40 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 transition-all duration-200 rounded-full"
                        style={{ width: duration > 0 ? `${(currentTime / duration) * 100}%` : "0%" }}
                      />
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-[9px] text-gray-500 font-mono">{formatTime(currentTime)}</span>
                      <span className="text-[9px] text-gray-500 font-mono">{formatTime(duration)}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Script4 narration */}
          {script4Text && (
            <div className="px-5 py-4 border-b border-gray-800/20 bg-indigo-500/[0.03]">
              <span className="font-ui text-[9px] uppercase tracking-[0.15em] text-indigo-400/60 block mb-2">
                Narration
              </span>
              <p className="font-body text-[13px] text-gray-300 leading-relaxed">
                {script4Text}
              </p>
            </div>
          )}

          {/* Grammar fields */}
          <div className="divide-y divide-gray-800/10 overflow-y-auto flex-1" style={{ maxHeight: "calc(85vh - 220px)" }}>
            {activeFields.length > 0 && (
              <div className="px-5 py-2">
                <span className="font-ui text-[9px] uppercase tracking-[0.15em] text-gray-500">
                  Grammar Breakdown
                </span>
              </div>
            )}
            {activeFields.map(({ key, label }, idx) => {
              const value = grammar[key];
              if (key === "key_words" && Array.isArray(value)) {
                return (
                  <div key={key} className="px-5 py-3 animate-in fade-in duration-300" style={{ animationDelay: `${idx * 80}ms` }}>
                    <span className="font-ui text-[9px] uppercase tracking-[0.15em] text-gray-500 block mb-2.5">
                      {label}
                    </span>
                    <div className="space-y-2">
                      {value.map((kw, i) => (
                        <div key={i} className="flex items-baseline gap-2">
                          <code className="font-mono text-[12px] text-indigo-300 font-semibold" dir={language === "ar" ? "rtl" : "ltr"}>
                            {kw.word}
                          </code>
                          <span className="font-body text-[11px] text-gray-400">— {kw.note}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }
              return (
                <div key={key} className="px-5 py-3 animate-in fade-in duration-300" style={{ animationDelay: `${idx * 80}ms` }}>
                  <span className="font-ui text-[9px] uppercase tracking-[0.15em] text-gray-500 block mb-1">
                    {label}
                  </span>
                  <p dir={language === "ar" ? "rtl" : "ltr"} className="font-body text-[12px] text-gray-300 leading-relaxed">
                    {String(value)}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="h-4" />
        </div>

        {/* Desktop */}
        <div className="hidden sm:block rounded-2xl border border-gray-800/50 bg-gray-950/90 backdrop-blur-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800/20">
            <h3 className="font-ui text-xs font-semibold text-gray-300 uppercase tracking-wider">
              Deep Dive
            </h3>
            <button onClick={onToggle} className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-gray-800/50 transition-colors" aria-label="Close">
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>

          {script4AudioUrl && (
            <div className="px-5 py-3 border-b border-gray-800/20">
              {hasError ? (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/20">
                  <AlertCircle className="w-3.5 h-3.5 text-red-400/70 shrink-0" />
                  <p className="text-[11px] text-gray-400">Audio unavailable</p>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <button onClick={togglePlay} disabled={isLoading} className="flex items-center justify-center w-9 h-9 rounded-full bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 transition-colors shrink-0 disabled:opacity-50" aria-label={isPlaying ? "Pause" : "Play"}>
                    {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="h-1 bg-gray-800/40 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-500 transition-all duration-200 rounded-full" style={{ width: duration > 0 ? `${(currentTime / duration) * 100}%` : "0%" }} />
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-[9px] text-gray-500 font-mono">{formatTime(currentTime)}</span>
                      <span className="text-[9px] text-gray-500 font-mono">{formatTime(duration)}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {script4Text && (
            <div className="px-5 py-4 border-b border-gray-800/20 bg-indigo-500/[0.03]">
              <span className="font-ui text-[9px] uppercase tracking-[0.15em] text-indigo-400/60 block mb-2">Narration</span>
              <p className="font-body text-[13px] text-gray-300 leading-relaxed">{script4Text}</p>
            </div>
          )}

          <div className="divide-y divide-gray-800/10 max-h-[50vh] overflow-y-auto">
            {activeFields.length > 0 && (
              <div className="px-5 py-2">
                <span className="font-ui text-[9px] uppercase tracking-[0.15em] text-gray-500">Grammar Breakdown</span>
              </div>
            )}
            {activeFields.map(({ key, label }, idx) => {
              const value = grammar[key];
              if (key === "key_words" && Array.isArray(value)) {
                return (
                  <div key={key} className="px-5 py-3 animate-in fade-in duration-300" style={{ animationDelay: `${idx * 80}ms` }}>
                    <span className="font-ui text-[9px] uppercase tracking-[0.15em] text-gray-500 block mb-2.5">{label}</span>
                    <div className="space-y-2">
                      {value.map((kw, i) => (
                        <div key={i} className="flex items-baseline gap-2">
                          <code className="font-mono text-[12px] text-indigo-300 font-semibold" dir={language === "ar" ? "rtl" : "ltr"}>{kw.word}</code>
                          <span className="font-body text-[11px] text-gray-400">— {kw.note}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }
              return (
                <div key={key} className="px-5 py-3 animate-in fade-in duration-300" style={{ animationDelay: `${idx * 80}ms` }}>
                  <span className="font-ui text-[9px] uppercase tracking-[0.15em] text-gray-500 block mb-1">{label}</span>
                  <p dir={language === "ar" ? "rtl" : "ltr"} className="font-body text-[12px] text-gray-300 leading-relaxed">{String(value)}</p>
                </div>
              );
            })}
          </div>

          <div className="flex justify-center px-5 py-3 border-t border-gray-800/10">
            <button onClick={onToggle} className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-300 transition-colors">
              <ChevronDown className="w-3.5 h-3.5" />
              <span>Close</span>
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
