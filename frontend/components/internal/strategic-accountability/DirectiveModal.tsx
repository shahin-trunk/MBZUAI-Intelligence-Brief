"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import type { Directive } from "@/lib/types/internal-intelligence";

interface DirectiveModalProps {
  directive: Directive | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function PriorityDot({ priority }: { priority: Directive["priority"] }) {
  const colorClass =
    priority === "critical"
      ? "bg-accent-danger"
      : priority === "high"
        ? "bg-accent-warning"
        : "bg-text-muted";

  return (
    <span
      className={cn("inline-block h-2.5 w-2.5 rounded-full shrink-0", colorClass)}
      title={`${priority} priority`}
    />
  );
}

function SourceBadge({ sourceType }: { sourceType: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {sourceType}
    </span>
  );
}

export function DirectiveModal({
  directive,
  open,
  onOpenChange,
}: DirectiveModalProps) {
  if (!directive) return null;

  const isOverdue = directive.status === "Overdue";

  // Reverse chronological for the timeline
  const timeline = [...directive.updateHistory].reverse();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug flex items-start gap-2">
            <PriorityDot priority={directive.priority} />
            <span>{directive.title}</span>
          </DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-2 mt-1">
              <StatusBadge status={directive.status} size="md" />
              <SourceBadge sourceType={directive.sourceType} />
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Description */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Description
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
            {directive.description}
          </p>
        </div>

        {/* Source */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Source
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary">
            {directive.source}
          </p>
        </div>

        {/* Owner */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Owner
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary">
            {directive.owner}
          </p>
        </div>

        {/* Deadline */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Deadline
          </p>
          <div className="mt-1 flex items-center gap-2">
            <span className="font-sans text-sm text-text-secondary">
              {directive.deadline || "No deadline set"}
            </span>
            {isOverdue && (
              <span className="font-mono text-[13px] font-bold text-accent-danger">
                OVERDUE
              </span>
            )}
          </div>
        </div>

        {/* Current Status */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Current Status
          </p>
          <div className="mt-1 flex items-center gap-2">
            <StatusBadge status={directive.status} size="md" />
            <span className="font-mono text-[13px] text-text-muted">
              as of {directive.statusDate}
            </span>
          </div>
        </div>

        {/* Update History Timeline */}
        <div className="mt-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-4">
            Update History
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
      </DialogContent>
    </Dialog>
  );
}
