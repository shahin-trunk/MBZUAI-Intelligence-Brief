"use client";

import { ArrowLeft, BookOpen } from "lucide-react";

type LearnLang = "fr" | "ar";

interface LearningHeaderProps {
  backHref: string;
  headline: string;
  language: LearnLang;
  onLanguageChange: (lang: LearnLang) => void;
  hasFr: boolean;
  hasAr: boolean;
  currentSection: number;
  totalSections: number;
  difficulty?: string;
  lessonSummary?: string;
  totalDuration?: number;
}

export default function LearningHeader({
  backHref,
  headline,
  language,
  onLanguageChange,
  hasFr,
  hasAr,
  currentSection,
  totalSections,
  difficulty,
  lessonSummary,
  totalDuration,
}: LearningHeaderProps) {
  const showBothLangs = hasFr && hasAr;

  const langLabel = language === "fr" ? "French" : "Arabic";
  const langEmoji = language === "fr" ? "🇫🇷" : "🇸🇦";

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const difficultyColor = (d?: string) => {
    switch (d) {
      case "beginner":
        return "text-emerald-600";
      case "advanced":
        return "text-amber-600";
      default:
        return "text-blue-600";
    }
  };

  return (
    <header
      className="sticky top-0 z-20 bg-bg-primary/90 backdrop-blur-xl border-b border-rule/30"
      style={{ paddingTop: "calc(0.5rem + env(safe-area-inset-top))" }}
    >
      {/* Main row: back | counter + meta | language toggle */}
      <div className="flex items-center justify-between px-4 pb-2">
        {/* Back button */}
        <a
          href={backHref}
          className="flex h-11 w-11 sm:h-[40px] sm:w-[40px] shrink-0 items-center justify-center rounded-full hover:bg-bg-surface transition-colors"
          aria-label="Back to briefing"
        >
          <ArrowLeft
            className="h-5 w-5 sm:h-4.5 sm:w-4.5 text-text-primary"
            strokeWidth={1.75}
          />
        </a>

        {/* Counter + difficulty badge */}
        <div className="flex items-center gap-2">
          <span className="font-ui text-[13px] font-medium text-text-secondary tabular-nums">
            {currentSection} / {totalSections}
          </span>
          {difficulty && (
            <span className={`font-ui text-[11px] font-semibold uppercase tracking-wide ${difficultyColor(difficulty)}`}>
              {difficulty}
            </span>
          )}
        </div>

        {/* Language toggle pill */}
        {showBothLangs ? (
          <div className="flex shrink-0 items-center overflow-hidden rounded-full border border-rule/50 bg-bg-surface/60 backdrop-blur-sm">
            <button
              type="button"
              onClick={() => onLanguageChange("fr")}
              className={`flex h-7 items-center justify-center gap-1 px-2.5 font-ui text-[11px] font-medium transition-all ${
                language === "fr"
                  ? "bg-accent-primary/10 text-accent-primary"
                  : "text-text-muted hover:text-text-secondary"
              }`}
              aria-label="French"
              aria-pressed={language === "fr"}
            >
              <span className="text-[10px]">🇫🇷</span>
              FR
            </button>
            <div className="h-3 w-px bg-rule/50" />
            <button
              type="button"
              onClick={() => onLanguageChange("ar")}
              className={`flex h-7 items-center justify-center gap-1 px-2.5 font-ui text-[11px] font-medium transition-all ${
                language === "ar"
                  ? "bg-accent-primary/10 text-accent-primary"
                  : "text-text-muted hover:text-text-secondary"
              }`}
              aria-label="Arabic"
              aria-pressed={language === "ar"}
            >
              <span className="text-[10px]">🇸🇦</span>
              AR
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 rounded-full border border-rule/50 bg-bg-surface/60 px-2.5 py-1">
            <span className="text-[10px]">{langEmoji}</span>
            <span className="font-ui text-[11px] font-medium text-text-secondary">
              {langLabel}
            </span>
          </div>
        )}
      </div>

      {/* Lesson summary + metadata */}
      {(lessonSummary || totalDuration) && (
        <div className="px-4 pb-2">
          <div className="flex items-start gap-2 rounded-lg bg-bg-surface/40 px-3 py-2">
            <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-primary/70" />
            <div className="min-w-0 flex-1">
              {lessonSummary && (
                <p className="font-body text-[12px] leading-snug text-text-secondary line-clamp-2">
                  {lessonSummary}
                </p>
              )}
              {totalDuration && (
                <p className="mt-1 font-ui text-[11px] text-text-muted">
                  {formatDuration(totalDuration)} lesson
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Headline subtitle */}
      <div className="px-4 pb-3">
        <p className="text-center font-body text-[11px] leading-snug text-text-muted truncate">
          {headline}
        </p>
      </div>
    </header>
  );
}
