"use client";

import { useEffect, useRef } from "react";

interface LearningAnalytics {
  itemId: string;
  language: "fr" | "ar";
  phraseIndex: number;
  scriptIndex: number;
  timestamp: number;
  event: "phrase_view" | "grammar_open" | "speed_change" | "lesson_complete" | "replay";
}

export function useLearningAnalytics(itemId: string | undefined) {
  const eventsRef = useRef<LearningAnalytics[]>([]);

  const trackEvent = (
    language: "fr" | "ar",
    phraseIndex: number,
    scriptIndex: number,
    event: LearningAnalytics["event"]
  ) => {
    if (!itemId) return;

    const analyticsEvent: LearningAnalytics = {
      itemId,
      language,
      phraseIndex,
      scriptIndex,
      timestamp: Date.now(),
      event,
    };

    eventsRef.current.push(analyticsEvent);

    // Send to analytics endpoint if configured
    if (process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT) {
      navigator.sendBeacon?.(
        process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT,
        JSON.stringify(analyticsEvent)
      );
    }

    // Log in development
    if (process.env.NODE_ENV === "development") {
      console.log("[Analytics]", analyticsEvent);
    }
  };

  // Save events to localStorage on unmount (for offline support)
  useEffect(() => {
    return () => {
      if (eventsRef.current.length > 0 && itemId) {
        try {
          const key = `ll-analytics-${itemId}`;
          const existing = JSON.parse(localStorage.getItem(key) || "[]");
          localStorage.setItem(
            key,
            JSON.stringify([...existing, ...eventsRef.current])
          );
        } catch {
          // Ignore localStorage errors
        }
      }
    };
  }, [itemId]);

  return { trackEvent };
}
