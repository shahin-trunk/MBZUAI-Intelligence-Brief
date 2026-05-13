"use client";

type LearnLang = "fr" | "ar";

interface LearningReadingPassageProps {
  script: string;
  language: LearnLang;
  currentTime: number;
  isPlaying: boolean;
}

export default function LearningReadingPassage({
  script,
  language,
}: LearningReadingPassageProps) {
  const isArabic = language === "ar";

  return (
    <div
      className={`rounded-2xl border border-rule bg-bg-surface px-5 py-6 sm:px-7 sm:py-8 ${
        isArabic ? "text-right" : "text-left"
      }`}
    >
      <p
        className={`font-body leading-relaxed text-text-primary ${
          isArabic
            ? "text-[18px] sm:text-[20px]"
            : "text-[18px] sm:text-[20px]"
        }`}
        style={{ lineHeight: isArabic ? 2.0 : 1.75 }}
      >
        {script}
      </p>
    </div>
  );
}
