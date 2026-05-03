"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import type { FacultyAchievement } from "@/lib/types/internal-intelligence";

interface FacultyAchievementsProps {
  achievements: FacultyAchievement[];
}

const CATEGORY_STYLES: Record<FacultyAchievement["category"], string> = {
  Award: "bg-accent-primary/15 text-accent-primary border-accent-primary/30",
  Fellowship: "bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/30",
  Keynote: "bg-sig-high/15 text-sig-high border-sig-high/30",
  "Academy Membership":
    "bg-accent-success/15 text-accent-success border-accent-success/30",
  "Named Position":
    "bg-[#A78BFA]/15 text-[#A78BFA] border-[#A78BFA]/30",
};

function formatDate(dateStr: string): string {
  const [year, month] = dateStr.split("-");
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${months[parseInt(month, 10) - 1]} ${year}`;
}

export function FacultyAchievements({
  achievements,
}: FacultyAchievementsProps) {
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());

  function toggleId(id: string) {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div className="grid grid-cols-1 gap-[14px] md:grid-cols-2 xl:grid-cols-3 items-start">
      {achievements.map((ach) => {
        const isOpen = openIds.has(ach.id);

        return (
          <Collapsible
            key={ach.id}
            open={isOpen}
            onOpenChange={() => toggleId(ach.id)}
          >
            <div className="rounded-sm border border-border-primary bg-bg-secondary">
              <CollapsibleTrigger asChild>
                <button
                  type="button"
                  className="flex h-[108px] w-full items-start gap-3 px-7 py-[22px] text-left cursor-pointer"
                >
                  <span
                    className={cn(
                      "mt-1 text-text-muted text-xs shrink-0 transition-transform duration-300 inline-block",
                      isOpen && "rotate-90"
                    )}
                  >
                    &#x25B8;
                  </span>
                  <div className="flex flex-1 flex-col min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-serif text-sm font-semibold text-text-bright">
                        {ach.facultyName}
                      </span>
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium shrink-0",
                          CATEGORY_STYLES[ach.category]
                        )}
                      >
                        {ach.category}
                      </span>
                    </div>
                    <p className="truncate font-sans text-sm leading-snug text-text-primary">
                      {ach.title}
                    </p>
                    <div className="mt-3 grid grid-cols-[minmax(0,1fr)_auto_auto] items-start gap-x-2">
                      <span className="truncate font-mono text-[13px] leading-snug text-text-muted">
                        {ach.division}
                      </span>
                      <span className="font-mono text-[13px] text-text-muted">
                        ·
                      </span>
                      <span className="font-mono text-[13px] leading-snug text-text-muted">
                        {formatDate(ach.date)}
                      </span>
                    </div>
                  </div>
                </button>
              </CollapsibleTrigger>

              <CollapsibleContent className="overflow-hidden">
                <div className="px-5 pb-4 pl-12 space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                        Faculty Member
                      </p>
                      <p className="mt-1 font-sans text-sm text-text-primary">
                        {ach.facultyName}
                      </p>
                    </div>
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                        Division
                      </p>
                      <p className="mt-1 font-sans text-sm text-text-primary">
                        {ach.division}
                      </p>
                    </div>
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                        Achievement
                      </p>
                      <p className="mt-1 font-sans text-sm text-text-primary">
                        {ach.title}
                      </p>
                    </div>
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                        Date
                      </p>
                      <p className="mt-1 font-sans text-sm text-text-primary">
                        {formatDate(ach.date)}
                      </p>
                    </div>
                  </div>

                  <p className="font-sans text-sm leading-relaxed text-text-secondary">
                    {ach.description}
                  </p>
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Awarding Body / Event
                    </p>
                    <p className="mt-1 font-sans text-sm text-text-primary">
                      {ach.awardingBody}
                    </p>
                  </div>
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
}
