"use client";

import { Bookmark, BookmarkCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface PhraseBookmarkProps {
  phraseId: string;
  phraseText: string;
  language: "fr" | "ar";
}

export default function PhraseBookmark({
  phraseId,
  phraseText,
  language,
}: PhraseBookmarkProps) {
  const [isBookmarked, setIsBookmarked] = useState(false);

  const bookmarkKey = `ll-bookmark-${language}-${phraseId}`;

  // Load bookmark state on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(bookmarkKey);
      setIsBookmarked(saved === "true");
    } catch {
      // Ignore
    }
  }, [bookmarkKey]);

  const toggleBookmark = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      const newState = !isBookmarked;
      setIsBookmarked(newState);
      try {
        localStorage.setItem(bookmarkKey, String(newState));
      } catch {
        // Ignore
      }
    },
    [isBookmarked, bookmarkKey],
  );

  return (
    <button
      type="button"
      onClick={toggleBookmark}
      className={`flex items-center justify-center h-8 w-8 rounded-full transition-all duration-200 ${
        isBookmarked
          ? "bg-accent-primary/15 text-accent-primary hover:bg-accent-primary/20"
          : "bg-bg-surface/40 text-text-muted/60 hover:text-text-secondary hover:bg-bg-surface/60"
      }`}
      aria-label={isBookmarked ? "Remove bookmark" : "Bookmark phrase"}
      title={isBookmarked ? "Saved to bookmarks" : "Save for later review"}
    >
      {isBookmarked ? (
        <BookmarkCheck className="h-4 w-4" />
      ) : (
        <Bookmark className="h-4 w-4" />
      )}
    </button>
  );
}
