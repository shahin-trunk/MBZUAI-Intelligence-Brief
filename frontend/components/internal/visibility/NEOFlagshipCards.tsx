"use client";

import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import type { NEOFlagshipProject } from "@/lib/types/internal-intelligence";

interface NEOFlagshipCardsProps {
  projects: NEOFlagshipProject[];
}

function StatusBadge({ status }: { status: string }) {
  const style =
    status === "Active"
      ? "bg-accent-success/15 text-accent-success border-accent-success/30"
      : status === "Scheduled"
        ? "bg-sig-high/10 text-sig-high border-sig-high/30"
        : "bg-bg-tertiary text-text-muted border-border-primary";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium ${style}`}
    >
      {status}
    </span>
  );
}

export function NEOFlagshipCards({ projects }: NEOFlagshipCardsProps) {
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
      {projects.map((project) => {
        const isOpen = openIds.has(project.id);

        return (
          <Collapsible.Root
            key={project.id}
            open={isOpen}
            onOpenChange={() => toggle(project.id)}
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
                      <p className="font-serif text-sm text-text-bright leading-snug">
                        {project.title}
                      </p>
                      <StatusBadge status={project.status} />
                    </div>

                    {/* Significance (line-clamp-1) */}
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed line-clamp-1">
                      {project.significance}
                    </p>

                    {/* Next milestone */}
                    <p className="font-mono text-[12px] text-text-muted">
                      {project.nextMilestone}
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
                  {/* Objective */}
                  {project.objective && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Objective
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {project.objective}
                      </p>
                    </div>
                  )}

                  {/* Strategic value */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                      Strategic Value
                    </p>
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                      {project.strategicValue}
                    </p>
                  </div>

                  {/* Recent progress */}
                  {project.recentProgress && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Recent Progress
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {project.recentProgress}
                      </p>
                    </div>
                  )}

                  {/* Key components */}
                  {project.keyComponents && project.keyComponents.length > 0 && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Key Components
                      </p>
                      <ul className="list-disc list-inside space-y-0.5">
                        {project.keyComponents.map((c) => (
                          <li
                            key={c}
                            className="font-sans text-[14px] text-text-secondary"
                          >
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Owner */}
                  {project.owner && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Owner
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {project.owner}
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
