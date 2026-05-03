"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { FlagshipGrant } from "@/lib/types/internal-intelligence";

interface GrantModalProps {
  grant: FlagshipGrant | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GrantModal({
  grant,
  open,
  onOpenChange,
}: GrantModalProps) {
  if (!grant) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {grant.title}
          </DialogTitle>
          <DialogDescription className="text-text-secondary text-sm">
            {grant.funder}
          </DialogDescription>
        </DialogHeader>

        {/* Amount + Duration */}
        <div className="flex items-center gap-4 mt-2">
          <span className="font-mono text-lg font-bold text-sig-high">
            {grant.amount}
          </span>
          <span className="font-mono text-[13px] text-text-muted">
            {grant.duration}
          </span>
        </div>

        {/* PI & Co-PIs */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Principal Investigator
          </h3>
          <p className="font-sans text-sm text-text-primary">{grant.pi}</p>
          {grant.coPIs.length > 0 && (
            <p className="font-sans text-sm text-text-secondary mt-1">
              Co-PIs: {grant.coPIs.join(", ")}
            </p>
          )}
        </div>

        {/* Division */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Division
          </h3>
          <p className="font-sans text-sm text-text-primary">{grant.division}</p>
        </div>

        {/* Start date */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Start Date
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {new Date(grant.startDate).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>

        {/* Description */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Description
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {grant.description}
          </p>
        </div>

      </DialogContent>
    </Dialog>
  );
}
