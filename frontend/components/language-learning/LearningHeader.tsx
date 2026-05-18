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
          className="flex h-9 w-9 items-center justify-center rounded-full bg-white/5 backdrop-blur-sm border border-white/10 hover:bg-white/10 transition-all duration-200"
          aria-label="Back to briefing"
        >
          <ArrowLeft className="h-4 w-4 text-gray-300" strokeWidth={1.5} />
        </a>

        {/* Language toggle pill */}
        {showBothLangs ? (
          <div className="flex items-center overflow-hidden rounded-full bg-white/5 backdrop-blur-sm border border-white/10">
            <button
              type="button"
              onClick={() => onLanguageChange("fr")}
              className={`flex h-7 items-center justify-center gap-1 px-3 font-ui text-[11px] font-medium transition-all ${
                language === "fr"
                  ? "bg-indigo-500/20 text-indigo-300"
                  : "text-gray-400 hover:text-gray-300"
              }`}
              aria-label="French"
              aria-pressed={language === "fr"}
            >
              FR
            </button>
            <div className="h-3 w-px bg-white/10" />
            <button
              type="button"
              onClick={() => onLanguageChange("ar")}
              className={`flex h-7 items-center justify-center gap-1 px-3 font-ui text-[11px] font-medium transition-all ${
                language === "ar"
                  ? "bg-indigo-500/20 text-indigo-300"
                  : "text-gray-400 hover:text-gray-300"
              }`}
              aria-label="Arabic"
              aria-pressed={language === "ar"}
            >
              AR
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 rounded-full bg-white/5 backdrop-blur-sm px-3 py-1 border border-white/10">
            <span className="font-ui text-[11px] font-medium text-gray-400">
              {language === "fr" ? "French" : "Arabic"}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
