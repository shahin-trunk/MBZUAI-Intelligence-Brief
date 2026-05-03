"use client";

import { useEffect, useState } from "react";
import type { Brief } from "@/lib/types/brief";
import { useAuth } from "@/lib/auth/AuthProvider";
import BriefHeader from "@/components/brief/BriefHeader";
import BriefTopBar from "@/components/brief/BriefTopBar";
import { CardReader } from "./CardReader";
import { DesktopBriefReview } from "./DesktopBriefReview";

interface BriefCardExperienceProps {
  brief: Brief;
  prevDate?: string | null;
  nextDate?: string | null;
  audioUrl?: string;
  audioScript?: string;
  audioUrlFr?: string;
  audioScriptFr?: string;
  audioStatus?: string;
}

export function BriefCardExperience({
  brief,
  prevDate,
  nextDate,
  audioUrl,
  audioScript,
  audioUrlFr,
  audioScriptFr,
  audioStatus,
}: BriefCardExperienceProps) {
  const { isAdmin } = useAuth();
  const [viewMode, setViewMode] = useState<"review" | "swipe">("swipe");
  const [hasChosenMode, setHasChosenMode] = useState(false);

  useEffect(() => {
    if (hasChosenMode) return;
    const mediaQuery = window.matchMedia("(min-width: 1024px)");

    const applyPreferredMode = () => {
      setViewMode(mediaQuery.matches ? "review" : "swipe");
    };

    applyPreferredMode();
    mediaQuery.addEventListener("change", applyPreferredMode);
    return () => {
      mediaQuery.removeEventListener("change", applyPreferredMode);
    };
  }, [hasChosenMode]);

  function switchMode(mode: "review" | "swipe") {
    setHasChosenMode(true);
    setViewMode(mode);
  }

  return (
    <div className="min-h-screen bg-bg-primary">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 md:px-8 py-6">
        <BriefTopBar
          prevDate={prevDate}
          nextDate={nextDate}
          briefDate={brief.brief_date}
          isAdmin={isAdmin}
        />
        <BriefHeader
          brief={brief}
          audioUrl={audioUrl}
          audioScript={audioScript}
          audioUrlFr={audioUrlFr}
          audioScriptFr={audioScriptFr}
          audioStatus={audioStatus}
        />
        <div className="mt-6 flex items-center justify-end">
          <div className="inline-flex rounded-xl border border-border-secondary bg-surface-secondary p-1">
            <button
              onClick={() => switchMode("review")}
              className={
                viewMode === "review"
                  ? "rounded-lg bg-accent-primary/10 px-3 py-2 text-sm text-accent-primary"
                  : "rounded-lg px-3 py-2 text-sm text-text-muted hover:text-text-primary"
              }
            >
              Review
            </button>
            <button
              onClick={() => switchMode("swipe")}
              className={
                viewMode === "swipe"
                  ? "rounded-lg bg-accent-primary/10 px-3 py-2 text-sm text-accent-primary"
                  : "rounded-lg px-3 py-2 text-sm text-text-muted hover:text-text-primary"
              }
            >
              Swipe
            </button>
          </div>
        </div>
      </div>
      <div className="mx-auto max-w-5xl px-0 sm:px-4">
        {viewMode === "review" ? (
          <DesktopBriefReview
            brief={brief}
            onSwitchToSwipe={() => switchMode("swipe")}
          />
        ) : (
          <CardReader
            brief={brief}
            onSwitchToList={() => switchMode("review")}
          />
        )}
      </div>
    </div>
  );
}
