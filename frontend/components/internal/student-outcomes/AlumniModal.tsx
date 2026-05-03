"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { AlumniHighlight } from "@/lib/types/internal-intelligence";

interface AlumniModalProps {
  alumni: AlumniHighlight | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AlumniModal({ alumni, open, onOpenChange }: AlumniModalProps) {
  if (!alumni) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-[28px] text-text-bright">
            {alumni.name}
          </DialogTitle>
          <DialogDescription className="text-text-secondary text-sm">
            {alumni.program}, Class of {alumni.graduationYear} — {alumni.nationality}
          </DialogDescription>
        </DialogHeader>

        {/* Current role */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Current Role
          </h3>
          <p className="font-serif text-lg text-text-bright leading-snug">
            {alumni.currentRole}
          </p>
          <p className="font-sans text-sm text-text-secondary mt-1">
            {alumni.organization}
          </p>
        </div>

        {/* Career path */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Career Path
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {alumni.careerPath}
          </p>
        </div>

        {/* Achievement */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Achievement
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {alumni.achievement}
          </p>
        </div>

        {/* MBZUAI connection */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            MBZUAI Connection
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {alumni.mbzuaiConnection}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
