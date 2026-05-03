"use client";

import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import type { SeniorLeaderEngaged } from "@/lib/types/internal-intelligence";

interface SeniorLeaderCardsProps {
  leaders: SeniorLeaderEngaged[];
}

export function SeniorLeaderCards({ leaders }: SeniorLeaderCardsProps) {
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
      {leaders.map((leader) => {
        const isOpen = openIds.has(leader.id);

        return (
          <Collapsible.Root
            key={leader.id}
            open={isOpen}
            onOpenChange={() => toggle(leader.id)}
          >
            <div className="bg-bg-secondary rounded-sm border border-border-primary">
              {/* Collapsed header */}
              <Collapsible.Trigger asChild>
                <button
                  type="button"
                  className="flex w-full cursor-pointer items-start justify-between px-7 py-[22px] text-left"
                >
                  <div className="min-w-0 flex-1 space-y-2">
                    {/* Name — visual anchor */}
                    <p className="font-serif text-sm font-semibold text-text-bright">
                      {leader.name}
                    </p>

                    {/* Title + Organization */}
                    <p className="font-sans text-[14px] text-text-secondary">
                      {leader.title}, {leader.organization}
                    </p>

                    {/* Program badge */}
                    <div>
                      <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
                        {leader.program}
                      </span>
                    </div>
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
                  {/* Period */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                      Period
                    </p>
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                      {leader.period}
                    </p>
                  </div>

                  {/* Why it matters */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                      Why It Matters
                    </p>
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                      {leader.whyItMatters}
                    </p>
                  </div>

                  {/* Engagement type */}
                  {leader.engagementType && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Engagement Type
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {leader.engagementType}
                      </p>
                    </div>
                  )}

                  {/* Strategic signal */}
                  {leader.strategicSignal && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Strategic Signal
                      </p>
                      <p className="font-sans text-[14px] text-sig-high font-medium leading-relaxed">
                        {leader.strategicSignal}
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
