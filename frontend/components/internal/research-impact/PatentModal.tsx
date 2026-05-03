"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { FlagshipPatent } from "@/lib/types/internal-intelligence";

interface PatentModalProps {
  patent: FlagshipPatent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function StatusBadge({ status }: { status: string }) {
  let style: string;
  if (status.includes("under examination")) {
    style = "bg-accent-primary/15 text-accent-primary border-accent-primary/30";
  } else if (status.includes("pending review")) {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
  } else if (status.includes("Granted")) {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
  } else {
    style = "bg-bg-tertiary text-text-muted border-border-primary";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        style
      )}
    >
      {status}
    </span>
  );
}

export function PatentModal({
  patent,
  open,
  onOpenChange,
}: PatentModalProps) {
  if (!patent) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {patent.title}
          </DialogTitle>
          <DialogDescription className="text-text-secondary text-sm">
            {patent.division}
          </DialogDescription>
        </DialogHeader>

        {/* Status + Date */}
        <div className="flex items-center gap-3 mt-1">
          <StatusBadge status={patent.status} />
          <span className="font-mono text-[13px] text-text-muted">
            Filed{" "}
            {new Date(patent.filingDate).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </span>
        </div>

        {/* Inventors */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Inventors
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {patent.inventors.join(", ")}
          </p>
        </div>

        {/* Description */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Description
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {patent.description}
          </p>
        </div>

        {/* Significance callout */}
        <div className="mt-4 border-l-2 border-l-sig-high bg-sig-high/5 px-4 py-3 rounded-sm">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-2">
            Why This Matters
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary italic">
            {patent.significance}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
