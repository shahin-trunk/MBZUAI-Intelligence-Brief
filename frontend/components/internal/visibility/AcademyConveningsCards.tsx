"use client";

import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import type { AcademyConveningV2 } from "@/lib/types/internal-intelligence";

interface AcademyConveningsCardsProps {
  convenings: AcademyConveningV2[];
}

export function AcademyConveningsCards({ convenings }: AcademyConveningsCardsProps) {
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
      {convenings.map((convening) => {
        const isOpen = openIds.has(convening.id);

        return (
          <Collapsible.Root
            key={convening.id}
            open={isOpen}
            onOpenChange={() => toggle(convening.id)}
          >
            <div className="bg-bg-secondary rounded-sm border border-border-primary">
              {/* Collapsed header */}
              <Collapsible.Trigger asChild>
                <button
                  type="button"
                  className="flex w-full cursor-pointer items-start justify-between px-7 py-[22px] text-left"
                >
                  <div className="min-w-0 flex-1 space-y-2">
                    {/* Title */}
                    <p className="font-serif text-sm text-text-bright leading-snug">
                      {convening.title}
                    </p>

                    {/* Date or Format */}
                    {(convening.date || convening.format) && (
                      <p className="font-mono text-[12px] text-text-muted">
                        {convening.date ?? convening.format}
                      </p>
                    )}

                    {/* Why it matters (short significance) */}
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed line-clamp-1">
                      {convening.whyItMatters}
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
                  {/* Reached / Audience */}
                  {(convening.reached || convening.audience) && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        {convening.reached ? "Reached" : "Audience"}
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {convening.reached ?? convening.audience}
                      </p>
                    </div>
                  )}

                  {/* Notable participants */}
                  {convening.notableParticipants && convening.notableParticipants.length > 0 && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Notable Participants
                      </p>
                      <p className="font-serif text-[14px] text-text-secondary italic">
                        {convening.notableParticipants.join(", ")}
                      </p>
                    </div>
                  )}

                  {/* Notable example */}
                  {convening.notableExample && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Notable Example
                      </p>
                      <p className="font-serif text-[14px] text-text-secondary italic">
                        {convening.notableExample}
                      </p>
                    </div>
                  )}

                  {/* Strategic value */}
                  {convening.strategicValue && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Strategic Value
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {convening.strategicValue}
                      </p>
                    </div>
                  )}

                  {/* Outcome */}
                  {convening.outcome && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Outcome
                      </p>
                      <p className="font-sans text-[14px] text-sig-high font-medium leading-relaxed">
                        {convening.outcome}
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
