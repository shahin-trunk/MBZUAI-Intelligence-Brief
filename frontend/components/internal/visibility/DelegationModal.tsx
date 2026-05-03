"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { HostedDelegation } from "@/lib/types/internal-intelligence";

interface DelegationModalProps {
  delegation: HostedDelegation | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DelegationModal({
  delegation,
  open,
  onOpenChange,
}: DelegationModalProps) {
  if (!delegation) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {delegation.delegation}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-3 mt-1">
              <span className="font-mono text-[13px] text-text-muted">
                {delegation.date}
              </span>
              <span className="font-mono text-[13px] text-text-muted">
                {delegation.size} delegates
              </span>
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Purpose */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Purpose
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
            {delegation.purpose}
          </p>
        </div>

        {/* Outcome */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Outcome
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
            {delegation.outcome}
          </p>
        </div>

        {/* Significance */}
        <div className="mt-5 border-l-2 border-l-sig-high bg-sig-high/5 px-4 py-3 rounded-sm">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-1">
            Why This Matters
          </p>
          <p className="font-sans text-sm text-text-secondary leading-relaxed">
            {delegation.significance}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
