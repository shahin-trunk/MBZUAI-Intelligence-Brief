"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { EnrichedPartnership } from "@/lib/types/internal-intelligence";

interface PartnershipModalProps {
  partner: EnrichedPartnership | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function StatusBadge({ status }: { status: string }) {
  let style: string;
  if (status === "Active") {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
  } else if (status.includes("dormant")) {
    style = "bg-bg-tertiary text-text-muted border-border-primary";
  } else {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
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

export function PartnershipModal({
  partner,
  open,
  onOpenChange,
}: PartnershipModalProps) {
  if (!partner) return null;

  const timeline = partner.activityHistory;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {partner.name}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-2 mt-1">
              <TypeBadge type={partner.type} />
              <StatusBadge status={partner.status} />
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Focus Area */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Focus Area
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
            {partner.focusArea}
          </p>
        </div>

        {/* Last Activity */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Last Activity
          </p>
          <p className="mt-1 font-mono text-sm text-text-secondary">
            {partner.lastActivityDate}
          </p>
        </div>

        {/* Key Contacts */}
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              MBZUAI Contacts
            </p>
            <p className="mt-1 font-sans text-sm text-text-primary">
              {partner.keyContactsMBZUAI}
            </p>
          </div>
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Partner Contacts
            </p>
            <p className="mt-1 font-sans text-sm text-text-primary">
              {partner.keyContactsPartner}
            </p>
          </div>
        </div>

        {/* Activity Timeline */}
        <div className="mt-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
            Activity History
          </p>

          <div className="relative pl-6">
            {/* Vertical line */}
            <div className="absolute left-[7px] top-1.5 bottom-1.5 w-px bg-border-primary" />

            <div className="space-y-4">
              {timeline.map((entry, index) => {
                const isLatest = index === 0;
                return (
                  <div key={entry.date + index} className="relative">
                    {/* Dot on the timeline */}
                    <div
                      className={cn(
                        "absolute -left-6 top-1 h-3 w-3 rounded-full border-2",
                        isLatest
                          ? "bg-accent-primary border-accent-primary/50"
                          : "bg-bg-tertiary border-border-primary"
                      )}
                    />

                    {/* Date */}
                    <p
                      className={cn(
                        "font-mono text-[13px]",
                        isLatest
                          ? "text-accent-primary font-medium"
                          : "text-text-muted"
                      )}
                    >
                      {entry.date}
                    </p>

                    {/* Note */}
                    <p
                      className={cn(
                        "mt-0.5 font-sans text-sm leading-relaxed",
                        isLatest ? "text-text-secondary" : "text-text-muted"
                      )}
                    >
                      {entry.note}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Upcoming */}
        {partner.upcoming && (
          <div className="mt-6">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
              Upcoming
            </p>
            <div className="border-l-2 border-l-accent-primary bg-accent-primary/5 px-4 py-3 rounded-sm">
              <p className="font-sans text-sm text-text-secondary leading-relaxed">
                {partner.upcoming}
              </p>
            </div>
          </div>
        )}

        {/* Notes */}
        {partner.notes && (
          <div className="mt-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Notes
            </p>
            <p className="mt-1 font-sans text-sm text-text-muted leading-relaxed italic">
              {partner.notes}
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
