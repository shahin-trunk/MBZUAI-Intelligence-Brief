"use client";

import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import type { AcademyFlagshipProgram } from "@/lib/types/internal-intelligence";

interface AcademyFlagshipProgramCardsProps {
  programs: AcademyFlagshipProgram[];
}

function StatusBadge({ status }: { status: string }) {
  const isActive =
    status.toLowerCase().includes("active") ||
    status.toLowerCase().includes("ongoing");
  const isCompleted = status.toLowerCase().includes("completed");

  const style = isActive
    ? "bg-accent-success/15 text-accent-success border-accent-success/30"
    : isCompleted
      ? "bg-accent-info/15 text-accent-info border-accent-info/30"
      : "bg-bg-tertiary text-text-muted border-border-primary";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium ${style}`}
    >
      {status}
    </span>
  );
}

export function AcademyFlagshipProgramCards({ programs }: AcademyFlagshipProgramCardsProps) {
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());

  function toggle(id: string) {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-3">
      {programs.map((program) => {
        const isOpen = openIds.has(program.id);

        return (
          <Collapsible.Root
            key={program.id}
            open={isOpen}
            onOpenChange={() => toggle(program.id)}
          >
            <div className="bg-bg-secondary rounded-sm border border-border-primary">
              {/* Collapsed header */}
              <Collapsible.Trigger asChild>
                <button
                  type="button"
                  className="flex w-full cursor-pointer items-start justify-between px-7 py-[22px] text-left"
                >
                  <div className="min-w-0 flex-1 space-y-2">
                    {/* Title + status */}
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-serif text-sm font-semibold text-text-bright">
                        {program.title}
                      </p>
                      <StatusBadge status={program.status} />
                    </div>

                    {/* Audience */}
                    <p className="font-sans text-[14px] text-text-secondary">
                      {program.audience}
                    </p>

                    {/* Current period signal */}
                    <p className="font-sans text-[14px] text-text-primary font-medium">
                      {program.currentPeriodSignal}
                    </p>
                  </div>

                  {/* Chevron */}
                  <span className="ml-3 mt-1 shrink-0 text-text-muted transition-transform">
                    {isOpen ? "▾" : "▸"}
                  </span>
                </button>
              </Collapsible.Trigger>

              {/* Expanded detail */}
              <Collapsible.Content>
                <div className="border-t border-border-primary px-7 py-[22px] space-y-3">
                  {/* Represented entities */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                      Represented Entities
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {program.representedEntities.map((entity) => (
                        <span
                          key={entity}
                          className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted"
                        >
                          {entity}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Strategic value */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                      Strategic Value
                    </p>
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                      {program.strategicValue}
                    </p>
                  </div>

                  {/* Recent progress */}
                  {program.recentProgress && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Recent Progress
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {program.recentProgress}
                      </p>
                    </div>
                  )}

                  {/* Why it matters to MBZUAI */}
                  {program.whyItMattersToMBZUAI && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Why It Matters to MBZUAI
                      </p>
                      <p className="font-sans text-[14px] text-sig-high font-medium leading-relaxed">
                        {program.whyItMattersToMBZUAI}
                      </p>
                    </div>
                  )}

                  {/* Next milestone */}
                  {program.nextMilestone && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Next Milestone
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {program.nextMilestone}
                      </p>
                    </div>
                  )}
                </div>
              </Collapsible.Content>
            </div>
          </Collapsible.Root>
        );
      })}
    </div>
  );
}
