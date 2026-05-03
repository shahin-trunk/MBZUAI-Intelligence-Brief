"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { FlagshipPublication } from "@/lib/types/internal-intelligence";

interface PublicationModalProps {
  publication: FlagshipPublication | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function TierBadge({ tier }: { tier: string }) {
  const styles: Record<string, string> = {
    "Tier 1": "bg-sig-high/15 text-sig-high border-sig-high/30",
    "Tier 2": "bg-accent-primary/15 text-accent-primary border-accent-primary/30",
    "Tier 3": "bg-bg-tertiary text-text-muted border-border-primary",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        styles[tier] || styles["Tier 3"]
      )}
    >
      {tier}
    </span>
  );
}

export function PublicationModal({
  publication,
  open,
  onOpenChange,
}: PublicationModalProps) {
  if (!publication) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {publication.title}
          </DialogTitle>
          <DialogDescription className="text-text-secondary text-sm">
            {publication.venue}
          </DialogDescription>
        </DialogHeader>

        {/* Tier + Date */}
        <div className="flex items-center gap-3 mt-1">
          <TierBadge tier={publication.tier} />
          <span className="font-mono text-[13px] text-text-muted">
            {new Date(publication.date + "T00:00:00").toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </span>
        </div>

        {/* Authors */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Authors
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {publication.authors.join(", ")}
          </p>
        </div>

        {/* Division */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Division
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {publication.division}
          </p>
        </div>

        {/* Abstract */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Abstract
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {publication.abstract}
          </p>
        </div>

        {/* Impact factor */}
        {publication.impactFactor != null && (
          <div className="mt-4">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
              Impact Factor
            </h3>
            <p className="font-mono text-lg font-bold text-text-bright">
              {publication.impactFactor}
            </p>
          </div>
        )}

        {/* Significance callout */}
        <div className="mt-4 border-l-2 border-l-sig-high bg-sig-high/5 px-4 py-3 rounded-sm">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-2">
            Why This Matters
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary italic">
            {publication.significance}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
