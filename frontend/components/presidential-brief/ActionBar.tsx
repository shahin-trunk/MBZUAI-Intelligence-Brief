"use client";

import type { BriefItem } from "@/lib/types/brief";

interface ActionBarProps {
  item: BriefItem;
  isFlagged: boolean;
  onToggleFlag: () => void;
  onAnnotate?: () => void;
  annotationCount?: number;
}

export default function ActionBar({
  item,
  isFlagged,
  onToggleFlag,
  onAnnotate,
  annotationCount,
}: ActionBarProps) {
  return (
    <div className="flex gap-1">
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggleFlag();
        }}
        className={`flex items-center gap-1.5 rounded-[2px] px-2.5 py-1.5 font-ui text-[12px] transition-colors ${
          isFlagged
            ? "text-accent"
            : "text-text-muted hover:text-text-primary hover:bg-bg-surface-2"
        }`}
      >
        ⚑ {isFlagged ? "Flagged" : "Flag"}
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onAnnotate?.();
        }}
        className="flex items-center gap-1.5 rounded-[2px] px-2.5 py-1.5 font-ui text-[12px] text-text-muted transition-colors hover:text-text-primary hover:bg-bg-surface-2"
      >
        ✎ Annotate
        {annotationCount != null && annotationCount > 0
          ? ` (${annotationCount})`
          : ""}
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (navigator.share) {
            navigator
              .share({
                title: item.headline,
                url: item.source_url ?? window.location.href,
              })
              .catch(() => {});
          } else {
            navigator.clipboard
              .writeText(
                item.headline +
                  (item.source_url ? " " + item.source_url : "")
              )
              .catch(() => {});
            alert("Copied to clipboard");
          }
        }}
        className="flex items-center gap-1.5 rounded-[2px] px-2.5 py-1.5 font-ui text-[12px] text-text-muted transition-colors hover:text-text-primary hover:bg-bg-surface-2"
      >
        ↗ Share
      </button>
    </div>
  );
}
