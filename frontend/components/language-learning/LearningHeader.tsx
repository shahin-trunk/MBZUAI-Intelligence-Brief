"use client";

import { ArrowLeft } from "lucide-react";

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
}: LearningHeaderProps) {
  const showBothLangs = hasFr && hasAr;

  return (
    <header
      className="sticky top-0 z-20 bg-bg-primary/80 backdrop-blur-xl"
      style={{ paddingTop: "calc(0.75rem + env(safe-area-inset-top))" }}
    >
      {/* Main row: back | counter | language toggle */}
      <div className="flex items-center justify-between px-4 pb-2">
        {/* Back button */}
        <a
          href={backHref}
          className="flex h-[44px] w-[44px] shrink-0 items-center justify-center"
          aria-label="Back to briefing"
        >
          <ArrowLeft
            className="h-5 w-5 text-text-primary"
            strokeWidth={1.75}
          />
        </a>

        {/* Section counter */}
        <span className="font-ui text-[13px] font-medium text-text-secondary tabular-nums">
          {currentSection} / {totalSections}
        </span>

        {/* Language toggle pill */}
        {showBothLangs ? (
          <div className="flex shrink-0 items-center overflow-hidden rounded-full border border-rule bg-bg-surface/50 backdrop-blur-sm">
            <button
              type="button"
              onClick={() => onLanguageChange("fr")}
              className={`flex h-8 items-center justify-center px-3 font-ui text-[12px] font-medium transition-colors ${
                language === "fr"
                  ? "text-accent-primary"
                  : "text-text-muted hover:text-text-secondary"
              }`}
              aria-label="French"
              aria-pressed={language === "fr"}
            >
              FR
            </button>
            <div className="h-3 w-px bg-rule" />
            <button
              type="button"
              onClick={() => onLanguageChange("ar")}
              className={`flex h-8 items-center justify-center px-3 font-ui text-[12px] font-medium transition-colors ${
                language === "ar"
                  ? "text-accent-primary"
                  : "text-text-muted hover:text-text-secondary"
              }`}
              aria-label="Arabic"
              aria-pressed={language === "ar"}
            >
              AR
            </button>
          </div>
        ) : (
          <div className="w-[44px]" />
        )}
      </div>

      {/* Headline subtitle */}
      <div className="px-4 pb-3">
        <p className="text-center font-body text-[12px] leading-snug text-text-muted truncate">
          {headline}
        </p>
      </div>
    </header>
  );
}
