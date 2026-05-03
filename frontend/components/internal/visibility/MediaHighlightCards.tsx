"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { MediaModal } from "./MediaModal";
import type { MediaHighlight } from "@/lib/types/internal-intelligence";

interface MediaHighlightCardsProps {
  highlights: MediaHighlight[];
}

function StatusBadge({ status }: { status: string }) {
  let style: string;
  if (status === "Published") {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
  } else if (status.includes("Scheduled") || status.includes("TBC")) {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
  } else {
    style = "bg-accent-primary/15 text-accent-primary border-accent-primary/30";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
        style
      )}
    >
      {status}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {type}
    </span>
  );
}

function formatDateAbbrev(dateStr: string | null): string {
  if (!dateStr) return "Date TBC";
  const d = new Date(dateStr + "T00:00:00");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const year = String(d.getFullYear()).slice(2);
  return `${months[d.getMonth()]} ${year}`;
}

export function MediaHighlightCards({ highlights }: MediaHighlightCardsProps) {
  const [selected, setSelected] = useState<MediaHighlight | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleClick(highlight: MediaHighlight) {
    setSelected(highlight);
    setModalOpen(true);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
          Prominent Media Coverage
        </p>
        <span className="font-mono text-[12px] text-text-muted">
          {highlights.length} prominent mentions this month
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-[14px]">
        {highlights.map((highlight) => (
          <button
            key={highlight.id}
            type="button"
            onClick={() => handleClick(highlight)}
            className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
          >
            {/* Outlet */}
            <p className="font-serif text-base text-text-bright font-semibold">
              {highlight.outlet}
            </p>

            {/* Badges */}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <TypeBadge type={highlight.type} />
              <StatusBadge status={highlight.status} />
            </div>

            {/* Title */}
            <p className="mt-2 font-sans text-sm text-text-secondary line-clamp-2">
              {highlight.title}
            </p>

            {/* Date + Reach */}
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="font-mono text-[12px] text-text-muted">
                {formatDateAbbrev(highlight.date)}
              </span>
              <span className="font-mono text-[12px] text-text-muted truncate max-w-[60%] text-right">
                {highlight.reach}
              </span>
            </div>

            {/* Coverage link */}
            {highlight.coverageUrl && (
              <p className="mt-2 font-mono text-[12px] text-accent-primary">
                View coverage →
              </p>
            )}
          </button>
        ))}
      </div>

      <MediaModal
        highlight={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
