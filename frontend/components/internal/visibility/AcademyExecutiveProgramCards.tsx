"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import type { AcademyExecutiveProgram } from "@/lib/types/internal-intelligence";

interface AcademyExecutiveProgramCardsProps {
  programs: AcademyExecutiveProgram[];
}

export function AcademyExecutiveProgramCards({ programs }: AcademyExecutiveProgramCardsProps) {
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
      {programs.map((program) => {
        const isOpen = openIds.has(program.id);

        return (
          <Collapsible
            key={program.id}
            open={isOpen}
            onOpenChange={() => toggleId(program.id)}
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
                        {program.title}
                      </span>
                      {program.satisfactionRating && (
                        <span className="font-mono text-[14px] font-bold text-sig-high shrink-0">
                          {program.satisfactionRating}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
                        {program.client}
                      </span>
                      <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
                        {program.cohort}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center gap-3">
                      <span className="font-mono text-[12px] text-text-muted">
                        {program.dates}
                      </span>
                      {program.participants > 0 && (
                        <>
                          <span className="font-mono text-[12px] text-text-muted">·</span>
                          <span className="font-mono text-[12px] text-text-muted">
                            {program.participants} participants
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </button>
              </CollapsibleTrigger>

              <CollapsibleContent className="overflow-hidden">
                <div className="px-5 pb-4 pl-12 space-y-4">
                  {/* Strategic Value */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Strategic Value
                    </p>
                    <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
                      {program.strategicValue}
                    </p>
                  </div>

                  {/* Key Outcome */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Key Outcome
                    </p>
                    <p className="mt-1 font-sans text-sm text-text-primary leading-relaxed">
                      {program.keyOutcome}
                    </p>
                  </div>

                  {/* Pipeline Note */}
                  {program.pipelineNote && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                        Pipeline
                      </p>
                      <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
                        &#x25B6; {program.pipelineNote}
                      </p>
                    </div>
                  )}
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
}
