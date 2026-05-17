"use client";

import { useEffect } from "react";

interface KeyboardShortcutConfig {
  onPrevious?: () => void;
  onNext?: () => void;
  onPlayPause?: () => void;
  onReplay?: () => void;
  onCloseGrammar?: () => void;
  onToggleLanguage?: () => void;
  enabled: boolean;
}

export function useKeyboardShortcuts({
  onPrevious,
  onNext,
  onPlayPause,
  onReplay,
  onCloseGrammar,
  onToggleLanguage,
  enabled,
}: KeyboardShortcutConfig) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't handle if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      switch (e.key) {
        case "ArrowLeft":
          e.preventDefault();
          onPrevious?.();
          break;
        case "ArrowRight":
          e.preventDefault();
          onNext?.();
          break;
        case " ":
          e.preventDefault();
          onPlayPause?.();
          break;
        case "r":
        case "R":
          if (e.metaKey || e.ctrlKey) {
            e.preventDefault();
            onReplay?.();
          }
          break;
        case "Escape":
          e.preventDefault();
          onCloseGrammar?.();
          break;
        case "l":
        case "L":
          if (e.metaKey || e.ctrlKey) {
            e.preventDefault();
            onToggleLanguage?.();
          }
          break;
        case "?":
          // Show keyboard shortcuts help
          e.preventDefault();
          console.log(`
Keyboard Shortcuts:
←/→ - Previous/Next phrase
Space - Play/Pause
Esc - Close grammar drawer
⌘/Ctrl+R - Replay lesson
⌘/Ctrl+L - Toggle language
? - Show this help
          `);
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, onPrevious, onNext, onPlayPause, onReplay, onCloseGrammar, onToggleLanguage]);
}
