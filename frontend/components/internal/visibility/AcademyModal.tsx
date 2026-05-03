"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { AcademyProgram } from "@/lib/types/internal-intelligence";

interface AcademyModalProps {
  program: AcademyProgram | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function ProgramTypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {type}
    </span>
  );
}

export function AcademyModal({ program, open, onOpenChange }: AcademyModalProps) {
  if (!program) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {program.programName}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-2 mt-1">
              <span className="font-mono text-[14px] text-text-secondary font-medium">
                {program.client}
              </span>
              <ProgramTypeBadge type={program.type} />
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Dates + Participants */}
        <div className="mt-4 flex items-center gap-6">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Dates
            </p>
            <p className="mt-1 font-sans text-sm text-text-secondary">
              {program.dates}
            </p>
          </div>
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Participants
            </p>
            <p className="mt-1 font-mono text-sm text-text-bright font-bold">
              {program.participants}
            </p>
          </div>
        </div>

        {/* Description */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Description
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
            {program.description}
          </p>
        </div>

        {/* Significance */}
        <div className="mt-5 border-l-2 border-l-sig-high bg-sig-high/5 px-4 py-3 rounded-sm">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-1">
            Why This Matters
          </p>
          <p className="font-sans text-sm text-text-secondary leading-relaxed">
            {program.significance}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
