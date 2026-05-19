"use client";

import { ArrowLeft } from "lucide-react";

type LearnLang = "fr" | "ar";

interface LearningHeaderProps {
  backHref: string;
  language: LearnLang;
  onLanguageChange: (lang: LearnLang) => void;
  hasFr: boolean;
  hasAr: boolean;
}

export default function LearningHeader({
  backHref,
  language,
  onLanguageChange,
  hasFr,
  hasAr,
}: LearningHeaderProps) {
  const showBothLangs = hasFr && hasAr;

  return (
    <header
      className="sticky top-0 z-30 bg-transparent"
      style={{ paddingTop: "calc(0.75rem + env(safe-area-inset-top))" }}
    >
      <div className="flex items-center justify-between px-5">
        {/* Back button */}
        <a
          href={backHref}
          className="flex h-10 w-10 sm:h-9 sm:w-9 items-center justify-center rounded-full bg-bg-surface border border-rule hover:bg-bg-surface-2 transition-all duration-200"
          aria-label="Back to briefing"
        >
          <ArrowLeft className="h-4 w-4 text-text-secondary" strokeWidth={1.5} />
        </a>

        {/* Language toggle pill */}
        {showBothLangs ? (
          <div className="flex items-center overflow-hidden rounded-full bg-bg-surface border border-rule">
            <button
              type="button"
              onClick={() => onLanguageChange("fr")}
              className={`flex h-9 sm:h-7 items-center justify-center gap-1 px-4 sm:px-3 font-ui text-[13px] sm:text-[11px] font-medium transition-all ${
                language === "fr"
                  ? "bg-accent/15 text-accent-primary"
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
              className={`flex h-9 sm:h-7 items-center justify-center gap-1 px-4 sm:px-3 font-ui text-[13px] sm:text-[11px] font-medium transition-all ${
                language === "ar"
                  ? "bg-accent/15 text-accent-primary"
                  : "text-text-muted hover:text-text-secondary"
              }`}
              aria-label="Arabic"
              aria-pressed={language === "ar"}
            >
              AR
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 rounded-full bg-bg-surface px-3 py-1 border border-rule">
            <span className="font-ui text-[11px] font-medium text-text-muted">
              {language === "fr" ? "French" : "Arabic"}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
