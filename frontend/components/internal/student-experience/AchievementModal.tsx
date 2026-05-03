"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { StudentAchievement } from "@/lib/types/internal-intelligence";

interface AchievementModalProps {
  achievement: StudentAchievement | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function CategoryBadge({ category }: { category: StudentAchievement["category"] }) {
  const styles: Record<StudentAchievement["category"], string> = {
    Competition: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    Publication: "bg-green-500/15 text-green-400 border-green-500/30",
    Fellowship: "bg-sig-high/15 text-sig-high border-sig-high/30",
    Research: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        styles[category]
      )}
    >
      {category}
    </span>
  );
}

function ProgramBadge({ program }: { program: "UG" | "MSc" | "PhD" }) {
  const styles: Record<string, string> = {
    UG: "bg-accent-primary/15 text-accent-primary border-accent-primary/30",
    MSc: "bg-sig-high/15 text-sig-high border-sig-high/30",
    PhD: "bg-accent-success/15 text-accent-success border-accent-success/30",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
        styles[program]
      )}
    >
      {program}
    </span>
  );
}

export function AchievementModal({
  achievement,
  open,
  onOpenChange,
}: AchievementModalProps) {
  if (!achievement) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-[28px] text-text-bright">
            {achievement.studentName}
          </DialogTitle>
          <DialogDescription className="text-text-secondary text-sm">
            {achievement.nationality}
          </DialogDescription>
        </DialogHeader>

        {/* Badges */}
        <div className="flex items-center gap-2 mt-1">
          <ProgramBadge program={achievement.program} />
          <CategoryBadge category={achievement.category} />
        </div>

        {/* Achievement headline */}
        <div className="mt-4">
          <h3 className="font-serif text-lg text-text-bright leading-snug">
            {achievement.achievementHeadline}
          </h3>
          <p className="font-mono text-[13px] text-text-muted mt-1">
            {new Date(achievement.date + "T00:00:00").toLocaleDateString("en-US", {
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
            {achievement.description}
          </p>
        </div>

        {/* Associated publication */}
        {achievement.associatedPublication && (
          <div className="mt-4">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
              Publication
            </h3>
            <p className="font-sans text-sm text-text-primary italic">
              {achievement.associatedPublication}
            </p>
          </div>
        )}

        {/* Associated award */}
        {achievement.associatedAward && (
          <div className="mt-4">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
              Award
            </h3>
            <p className="font-sans text-sm text-text-primary">
              {achievement.associatedAward}
            </p>
          </div>
        )}

        {/* Faculty advisor */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Faculty Advisor
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {achievement.facultyAdvisor}
          </p>
        </div>

      </DialogContent>
    </Dialog>
  );
}
