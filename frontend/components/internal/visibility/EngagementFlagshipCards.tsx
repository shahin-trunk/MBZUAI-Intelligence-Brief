"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import type { EngagementFlagshipProject } from "@/lib/types/internal-intelligence";

interface EngagementFlagshipCardsProps {
  projects: EngagementFlagshipProject[];
}

const STATUS_STYLES: Record<string, string> = {
  "Active": "bg-accent-primary/15 text-accent-primary border-accent-primary/30",
  "In planning": "bg-bg-tertiary text-text-muted border-border-primary",
  "Completed": "bg-accent-success/15 text-accent-success border-accent-success/30",
};

const STEP_ICON: Record<string, { symbol: string; color: string }> = {
  completed: { symbol: "\u2713", color: "text-accent-success" },
  in_progress: { symbol: "\u25CF", color: "text-sig-high" },
  pending: { symbol: "\u25CB", color: "text-text-muted" },
};

export function EngagementFlagshipCards({ projects }: EngagementFlagshipCardsProps) {
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
    <div className="grid grid-cols-1 gap-[14px]">
      {projects.map((project) => {
        const isOpen = openIds.has(project.id);
        const completedCount = project.steps.filter((s) => s.status === "completed").length;
        const badgeStyle = STATUS_STYLES[project.status] ?? STATUS_STYLES["In planning"];

        return (
          <Collapsible
            key={project.id}
            open={isOpen}
            onOpenChange={() => toggleId(project.id)}
          >
            <div className="rounded-sm border border-border-primary bg-bg-secondary">
              <CollapsibleTrigger asChild>
                <button
                  type="button"
                  className="flex w-full items-start gap-3 px-7 py-[22px] text-left cursor-pointer"
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
                        {project.title}
                      </span>
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium shrink-0",
                          badgeStyle
                        )}
                      >
                        {project.status}
                      </span>
                    </div>
                    <p className="font-sans text-[14px] text-text-secondary line-clamp-1">
                      {project.objective}
                    </p>
                    <div className="mt-2 flex items-center gap-3">
                      <span className="font-mono text-[12px] text-text-muted">
                        Due {project.finalDeadline}
                      </span>
                      {project.owner && (
                        <>
                          <span className="font-mono text-[12px] text-text-muted">·</span>
                          <span className="font-mono text-[12px] text-text-muted">
                            {project.owner}
                          </span>
                        </>
                      )}
                      <span className="font-mono text-[12px] text-text-muted ml-auto">
                        {completedCount}/{project.steps.length} steps
                      </span>
                    </div>
                  </div>
                </button>
              </CollapsibleTrigger>

              <CollapsibleContent className="overflow-hidden">
                <div className="px-5 pb-4 pl-12 space-y-4">
                  {/* Full objective */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Objective
                    </p>
                    <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
                      {project.objective}
                    </p>
                  </div>

                  {/* Deadline */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Final Deadline
                    </p>
                    <p className="mt-1 font-sans text-sm text-text-primary">
                      {project.finalDeadline}
                    </p>
                  </div>

                  {/* Progress checklist */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-2">
                      Progress
                    </p>
                    <div className="space-y-1.5">
                      {project.steps.map((step) => {
                        const icon = STEP_ICON[step.status] ?? STEP_ICON.pending;
                        return (
                          <div
                            key={step.label}
                            className="flex items-start gap-2"
                          >
                            <span className={cn("font-mono text-[14px] shrink-0 w-4 text-center", icon.color)}>
                              {icon.symbol}
                            </span>
                            <span
                              className={cn(
                                "font-sans text-[14px] leading-snug",
                                step.status === "completed"
                                  ? "text-text-muted line-through"
                                  : "text-text-primary"
                              )}
                            >
                              {step.label}
                            </span>
                            {step.deadline && step.status !== "completed" && (
                              <span className="font-mono text-[12px] text-text-muted ml-auto shrink-0">
                                {step.deadline}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
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
