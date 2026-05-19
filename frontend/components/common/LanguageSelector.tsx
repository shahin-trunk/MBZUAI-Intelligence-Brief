"use client";

import { useCallback } from "react";
import { cn } from "@/lib/utils";
import { CountryFlag } from "./CountryFlag";

export type AudioLanguage = "en" | "fr" | "ar";

interface LanguageOption {
  lang: AudioLanguage;
  label: string;
  flagCode: string;
}

const LANGUAGES: LanguageOption[] = [
  { lang: "en", label: "EN", flagCode: "us" },
  { lang: "fr", label: "FR", flagCode: "fr" },
  { lang: "ar", label: "AR", flagCode: "ae" },
];

interface LanguageSelectorProps {
  /** Currently active language. */
  language: AudioLanguage;
  /** Called when the user selects a language. */
  onLanguageChange: (lang: AudioLanguage) => void;
  /** Availability flags — disabled options will appear muted. */
  availability?: Partial<Record<AudioLanguage, boolean>>;
  /** Size variant. */
  size?: "sm" | "md";
  className?: string;
}

/**
 * A compact language selector that displays flag icons for EN / FR / AR.
 * Designed for use in the pinned audio bar and full-screen audio player.
 */
export function LanguageSelector({
  language,
  onLanguageChange,
  availability,
  size = "sm",
  className,
}: LanguageSelectorProps) {
  const handleClick = useCallback(
    (lang: AudioLanguage) => {
      if (lang !== language) {
        onLanguageChange(lang);
      }
    },
    [language, onLanguageChange],
  );

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border border-rule bg-bg-surface p-0.5 shadow-sm",
        className,
      )}
      role="group"
      aria-label="Audio language"
    >
      {LANGUAGES.map(({ lang, label, flagCode }) => {
        const isActive = language === lang;
        const isAvailable = availability?.[lang] ?? true;

        return (
          <button
            key={lang}
            type="button"
            onClick={() => handleClick(lang)}
            disabled={!isAvailable}
            aria-pressed={isActive}
            className={cn(
              "inline-flex items-center justify-center gap-1 rounded-full font-ui font-semibold transition-all duration-150",
              "disabled:cursor-not-allowed disabled:opacity-35",
              size === "sm"
                ? "min-h-7 min-w-[2.25rem] px-2 py-1 text-[11px] leading-none"
                : "min-h-8 min-w-[2.75rem] px-3 py-1.5 text-[13px]",
              isActive
                ? "bg-accent text-white shadow-sm"
                : "text-text-primary hover:bg-bg-surface-2",
            )}
          >
            <CountryFlag
              code={flagCode}
              className={cn(
                "shrink-0 rounded-[1px] object-cover",
                size === "sm" ? "h-3.5 w-3.5" : "h-[18px] w-[18px]",
              )}
              ariaLabel={label}
            />
            <span className="leading-none">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
