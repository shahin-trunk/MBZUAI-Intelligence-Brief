"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { ProgramDevelopment } from "@/lib/types/internal-intelligence";

interface ProgramDevelopmentModalProps {
  development: ProgramDevelopment | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function ScopeBadge({ scope }: { scope: ProgramDevelopment["scope"] }) {
  const styles: Record<ProgramDevelopment["scope"], string> = {
    Graduate: "bg-sig-high/10 text-sig-high/80 border-sig-high/20",
    Undergraduate: "bg-accent-primary/10 text-accent-primary/80 border-accent-primary/20",
    "University-wide": "bg-text-muted/10 text-text-muted border-border-primary",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        styles[scope]
      )}
    >
      {scope}
    </span>
  );
}

function StatusBadge({ status }: { status: ProgramDevelopment["status"] }) {
  const styles: Record<ProgramDevelopment["status"], string> = {
    Active: "bg-accent-primary/10 text-accent-primary/70 border-accent-primary/20",
    "In design": "bg-text-muted/10 text-text-muted border-border-primary",
    Completed: "bg-accent-success/15 text-accent-success border-accent-success/30",
    "Under review": "bg-amber-500/10 text-amber-400 border-amber-500/20",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        styles[status]
      )}
    >
      {status}
    </span>
  );
}

export function ProgramDevelopmentModal({
  development,
  open,
  onOpenChange,
}: ProgramDevelopmentModalProps) {
  if (!development) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-[28px] text-text-bright">
            {development.title}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-2 mt-1">
              <ScopeBadge scope={development.scope} />
              <StatusBadge status={development.status} />
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Owner */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Owner
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {development.owner}
          </p>
        </div>

        {/* Full description */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Description
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {development.fullDescription}
          </p>
        </div>

        {/* Current progress */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Current Progress
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {development.currentProgress}
          </p>
        </div>

        {/* Timeline */}
        {development.targetDate && (
          <div className="mt-4">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
              Timeline
            </h3>
            <p className="font-sans text-sm text-text-primary">
              {development.targetDate}
            </p>
          </div>
        )}

        {/* SMT Source */}
        <div className="mt-4 pt-3 border-t border-border-primary">
          <p className="font-mono text-[13px] text-text-muted">
            Source: {development.source}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
