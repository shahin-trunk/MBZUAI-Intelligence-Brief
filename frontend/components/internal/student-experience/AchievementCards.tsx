"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { StudentAchievement } from "@/lib/types/internal-intelligence";
import { AchievementModal } from "./AchievementModal";

interface AchievementCardsProps {
  achievements: StudentAchievement[];
}

const CATEGORY_LABELS: Record<StudentAchievement["category"], string> = {
  Fellowship: "Scholarships & Fellowships",
  Publication: "Publications & Paper Awards",
  Competition: "Competitions",
  Research: "Research Projects",
};

const CATEGORY_ORDER: StudentAchievement["category"][] = [
  "Fellowship",
  "Publication",
  "Competition",
  "Research",
];

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
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
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

export function AchievementCards({ achievements }: AchievementCardsProps) {
  const [selectedAchievement, setSelectedAchievement] =
    useState<StudentAchievement | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleCardClick(achievement: StudentAchievement) {
    setSelectedAchievement(achievement);
    setModalOpen(true);
  }

  // Group achievements by category
  const grouped = CATEGORY_ORDER.map((cat) => ({
    category: cat,
    label: CATEGORY_LABELS[cat],
    items: achievements.filter((a) => a.category === cat),
  })).filter((g) => g.items.length > 0);

  return (
    <>
      {/* Count subtitle */}
      <p className="font-mono text-[14px] leading-[1.6] text-text-muted mb-4">
        {achievements.length} notable achievement{achievements.length !== 1 ? "s" : ""} this month
      </p>

      <div className="space-y-6">
        {grouped.map((group) => (
          <div key={group.category}>
            {/* Category sub-header */}
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
              {group.label}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
              {group.items.map((achievement) => (
                <button
                  key={achievement.id}
                  type="button"
                  onClick={() => handleCardClick(achievement)}
                  className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
                >
                  {/* Achievement headline */}
                  <p className="font-serif text-base text-text-bright leading-snug">
                    {achievement.achievementHeadline}
                  </p>

                  {/* Student name + nationality */}
                  <p className="mt-2 font-sans text-sm text-text-secondary">
                    {achievement.studentName}
                    <span className="text-text-muted"> — {achievement.nationality}</span>
                  </p>

                  {/* Program + Category badges */}
                  <div className="mt-2 flex items-center gap-2 flex-wrap">
                    <ProgramBadge program={achievement.program} />
                    <CategoryBadge category={achievement.category} />
                  </div>

                  {/* Date + Faculty advisor */}
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <span className="font-mono text-[12px] text-text-muted">
                      {new Date(achievement.date + "T00:00:00").toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                    <span className="font-mono text-[12px] text-text-muted truncate">
                      {achievement.facultyAdvisor}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <AchievementModal
        achievement={selectedAchievement}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
