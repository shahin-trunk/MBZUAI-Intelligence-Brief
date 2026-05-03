"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { MediaHighlight } from "@/lib/types/internal-intelligence";

interface MediaModalProps {
  highlight: MediaHighlight | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function StatusBadge({ status }: { status: string }) {
  let style: string;
  if (status === "Published") {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
  } else if (status.includes("Scheduled") || status.includes("TBC")) {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
  } else {
    // Completed — awaiting, Interview completed — pending
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

export function MediaModal({ highlight, open, onOpenChange }: MediaModalProps) {
  if (!highlight) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {highlight.outlet}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-2 mt-1">
              <TypeBadge type={highlight.type} />
              <StatusBadge status={highlight.status} />
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Title */}
        <div className="mt-4">
          <p className="font-serif text-base text-text-bright">{highlight.title}</p>
        </div>

        {/* Date */}
        <div className="mt-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Date
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary">
            {highlight.date || "TBC"}
          </p>
        </div>

        {/* Description */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Description
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
            {highlight.description}
          </p>
        </div>

        {/* Reach */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Reach
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary">
            {highlight.reach}
          </p>
        </div>

        {/* Spokespeople */}
        {highlight.mbzuaiSpokespeople.length > 0 && (
          <div className="mt-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              MBZUAI Spokespeople
            </p>
            <ul className="mt-1 space-y-0.5">
              {highlight.mbzuaiSpokespeople.map((person) => (
                <li
                  key={person}
                  className="font-sans text-sm text-text-secondary"
                >
                  {person}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Coverage Link */}
        {highlight.coverageUrl && (
          <div className="mt-4">
            <a
              href={highlight.coverageUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 font-mono text-[14px] text-accent-primary hover:underline"
            >
              View published coverage →
            </a>
          </div>
        )}

        {/* Significance */}
        <div className="mt-5 border-l-2 border-l-sig-high bg-sig-high/5 px-4 py-3 rounded-sm">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-1">
            Why This Matters
          </p>
          <p className="font-sans text-sm text-text-secondary leading-relaxed">
            {highlight.significance}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
