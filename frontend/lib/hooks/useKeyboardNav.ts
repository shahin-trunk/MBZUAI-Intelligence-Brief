"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import type { BriefItem } from "@/lib/types/brief";

interface UseKeyboardNavOptions {
  allItems: BriefItem[];
  sectionNames: string[];
  prevDate: string | null;
  nextDate: string | null;
  setExpandedItemId: (id: string | null) => void;
  setAnnotationPanelOpen: (open: boolean) => void;
}

export function useKeyboardNav({
  allItems,
  sectionNames,
  prevDate,
  nextDate,
  setExpandedItemId,
  setAnnotationPanelOpen,
}: UseKeyboardNavOptions): { showHelp: boolean; setShowHelp: (v: boolean) => void } {
  const [activeIndex, setActiveIndex] = useState(-1);
  const [showHelp, setShowHelp] = useState(false);
  const router = useRouter();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Disabled when typing in form elements
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      ) {
        return;
      }

      switch (e.key) {
        case "j": {
          e.preventDefault();
          const nextIndex = Math.min(activeIndex + 1, allItems.length - 1);
          setActiveIndex(nextIndex);
          const id = allItems[nextIndex]?.id;
          if (id) {
            const el = document.querySelector(`[data-item-id="${id}"]`);
            if (el) {
              el.scrollIntoView({ behavior: "smooth", block: "center" });
              el.classList.add("flash-highlight");
              el.addEventListener("animationend", () => {
                el.classList.remove("flash-highlight");
              }, { once: true });
            }
            setExpandedItemId(id);
          }
          break;
        }

        case "k": {
          e.preventDefault();
          const prevIndex = Math.max(activeIndex - 1, 0);
          setActiveIndex(prevIndex);
          const id = allItems[prevIndex]?.id;
          if (id) {
            const el = document.querySelector(`[data-item-id="${id}"]`);
            if (el) {
              el.scrollIntoView({ behavior: "smooth", block: "center" });
              el.classList.add("flash-highlight");
              el.addEventListener("animationend", () => {
                el.classList.remove("flash-highlight");
              }, { once: true });
            }
            setExpandedItemId(id);
          }
          break;
        }

        case "ArrowLeft": {
          e.preventDefault();
          if (prevDate) {
            router.push(`/brief/${prevDate}`);
          }
          break;
        }

        case "ArrowRight": {
          e.preventDefault();
          if (nextDate) {
            router.push(`/brief/${nextDate}`);
          }
          break;
        }

        case "1":
        case "2":
        case "3":
        case "4":
        case "5": {
          e.preventDefault();
          const idx = parseInt(e.key, 10) - 1;
          if (sectionNames[idx]) {
            const sectionId = `section-${sectionNames[idx].toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
            document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth" });
          }
          break;
        }

        case "Escape": {
          e.preventDefault();
          setAnnotationPanelOpen(false);
          setShowHelp(false);
          break;
        }

        case "?": {
          e.preventDefault();
          setShowHelp((prev) => !prev);
          break;
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [
    activeIndex,
    allItems,
    sectionNames,
    prevDate,
    nextDate,
    setExpandedItemId,
    setAnnotationPanelOpen,
    router,
  ]);

  return { showHelp, setShowHelp };
}
