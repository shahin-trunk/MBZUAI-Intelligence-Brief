"use client";

import React from "react";
import { BookOpen, Languages, MessageSquareText, GraduationCap, ListChecks } from "lucide-react";
import type { LearningPhrase } from "@/lib/types/brief";
import InlinePhrasesReveal from "@/components/language-learning/InlinePhrasesReveal";

interface AutoFlowSectionProps {
  section: {
    id: string;
    type: string;
    title: string;
    title_en: string;
    script: string;
    key_phrases?: LearningPhrase[];
  };
  sectionProgress: number;
  language: "fr" | "ar";
  children?: React.ReactNode;
}

const SECTION_ICON: Record<string, React.ReactNode> = {
  narrative: <Languages className="h-3.5 w-3.5" />,
  grammar: <BookOpen className="h-3.5 w-3.5" />,
  vocabulary: <GraduationCap className="h-3.5 w-3.5" />,
  phrase_focus: <MessageSquareText className="h-3.5 w-3.5" />,
  summary: <ListChecks className="h-3.5 w-3.5" />,
};

export default function AutoFlowSection({
  section,
  sectionProgress,
  language,
  children,
}: AutoFlowSectionProps) {
  const isRTL = language === "ar";

  const showPhrases =
    sectionProgress >= 0.4 &&
    section.key_phrases &&
    section.key_phrases.length > 0;

  const icon = SECTION_ICON[section.type] || SECTION_ICON.narrative;

  return (
    <div
      dir={isRTL ? "rtl" : "ltr"}
      className="w-full animate-in fade-in duration-500 fill-mode-both"
    >
      {/* Section header */}
      <div className="flex items-center justify-center gap-2 mb-6">
        <span className="text-text-muted/50">{icon}</span>
        <p className="font-ui text-[11px] uppercase tracking-widest text-text-muted/60">
          {section.title_en}
        </p>
      </div>

      {/* Narrative text (passed as children) */}
      {children}

      {/* Inline phrases — revealed at 40% section progress */}
      {section.key_phrases && section.key_phrases.length > 0 && (
        <div className="mt-8">
          <div className="mx-auto mb-6 h-px w-16 bg-rule/15" />
          <InlinePhrasesReveal
            phrases={section.key_phrases as LearningPhrase[]}
            isVisible={!!showPhrases}
            language={language}
          />
        </div>
      )}
    </div>
  );
}
