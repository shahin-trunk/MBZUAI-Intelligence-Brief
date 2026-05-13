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
}

const toggleBtn =
  "flex h-10 items-center justify-center rounded-full px-4 font-ui text-[13px] font-medium transition-colors";

export default function LearningHeader({
  backHref,
  headline,
  language,
  onLanguageChange,
  hasFr,
  hasAr,
}: LearningHeaderProps) {
  return (
    <header className="sticky top-0 z-10 border-b border-rule bg-bg-primary/95 backdrop-blur-sm">
      <div className="flex items-center justify-between px-3 py-2.5 sm:px-5 sm:py-3">
        {/* Back button */}
        <a
          href={backHref}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-rule bg-bg-surface text-text-primary transition-colors hover:bg-bg-surface-2"
          aria-label="Back to briefing"
        >
          <ArrowLeft className="h-5 w-5" strokeWidth={1.75} />
        </a>

        {/* English headline reference (subtle) */}
        <p className="mx-3 line-clamp-1 text-center font-ui text-[12px] text-text-muted sm:mx-4 sm:text-[13px]">
          {headline}
        </p>

        {/* Language toggle */}
        <div className="flex shrink-0 items-center overflow-hidden rounded-full border border-rule bg-bg-surface">
          {hasFr && (
            <button
              type="button"
              disabled={!hasFr}
              onClick={() => onLanguageChange("fr")}
              className={`${toggleBtn} ${
                language === "fr"
                  ? "bg-accent-primary text-white"
                  : "text-text-secondary hover:text-text-primary"
              }`}
              aria-label="French"
              aria-pressed={language === "fr"}
            >
              FR
            </button>
          )}
          {hasAr && (
            <button
              type="button"
              disabled={!hasAr}
              onClick={() => onLanguageChange("ar")}
              className={`${toggleBtn} ${
                language === "ar"
                  ? "bg-accent-primary text-white"
                  : "text-text-secondary hover:text-text-primary"
              }`}
              aria-label="Arabic"
              aria-pressed={language === "ar"}
            >
              AR
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
