"use client";

import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import type { AcademyDifferentiatorV2 } from "@/lib/types/internal-intelligence";

interface AcademyDifferentiatorCardsProps {
  differentiators: AcademyDifferentiatorV2[];
}

export function AcademyDifferentiatorCards({ differentiators }: AcademyDifferentiatorCardsProps) {
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
      {differentiators.map((diff) => {
        const isOpen = openIds.has(diff.id);

        return (
          <Collapsible.Root
            key={diff.id}
            open={isOpen}
            onOpenChange={() => toggle(diff.id)}
          >
            <div className="bg-bg-secondary rounded-sm border border-border-primary border-l-2 border-l-sig-high">
              {/* Collapsed header */}
              <Collapsible.Trigger asChild>
                <button
                  type="button"
                  className="flex w-full cursor-pointer items-start justify-between px-7 py-[22px] text-left"
                >
                  <div className="min-w-0 flex-1 space-y-2">
                    {/* Title */}
                    <p className="font-serif text-base text-text-bright leading-snug">
                      {diff.title}
                    </p>

                    {/* Significance */}
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                      {diff.significance}
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
                  {/* Why it matters */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                      Why It Matters
                    </p>
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                      {diff.whyItMatters}
                    </p>
                  </div>

                  {/* Current signal */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                      Current Signal
                    </p>
                    <p className="font-mono text-[13px] text-text-muted">
                      {diff.currentSignal}
                    </p>
                  </div>

                  {/* Strategic value */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                      Strategic Value
                    </p>
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                      {diff.strategicValue}
                    </p>
                  </div>

                  {/* Program shape */}
                  {diff.programShape && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Program Shape
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {diff.programShape}
                      </p>
                    </div>
                  )}

                  {/* Next milestone */}
                  {diff.nextMilestone && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Next Milestone
                      </p>
                      <p className="font-sans text-[14px] text-sig-high font-medium leading-relaxed">
                        {diff.nextMilestone}
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
