"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import type {
  StrategicDelegation,
  DelegationPriority,
  DelegationStatus,
  DelegationCategory,
} from "@/lib/types/internal-intelligence";

interface StrategicDelegationCardsProps {
  delegations: StrategicDelegation[];
}

const PRIORITY_STYLES: Record<DelegationPriority, string> = {
  critical: "bg-accent-warning/15 text-accent-warning border-accent-warning/30",
  high: "bg-accent-primary/15 text-accent-primary border-accent-primary/30",
  standard: "bg-bg-tertiary text-text-muted border-border-primary",
};

const STATUS_STYLES: Record<DelegationStatus, string> = {
  confirmed: "bg-accent-success/15 text-accent-success border-accent-success/30",
  tentative: "bg-accent-warning/15 text-accent-warning border-accent-warning/30",
  in_planning: "bg-bg-tertiary text-text-muted border-border-primary",
};

const STATUS_LABELS: Record<DelegationStatus, string> = {
  confirmed: "Confirmed",
  tentative: "Tentative",
  in_planning: "In planning",
};

const CATEGORY_LABELS: Record<DelegationCategory, string> = {
  government: "Government",
  academic: "Academic",
  industry: "Industry",
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function StrategicDelegationCards({ delegations }: StrategicDelegationCardsProps) {
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
      {delegations.map((del) => {
        const isOpen = openIds.has(del.id);
        const isCritical = del.priority === "critical";

        return (
          <Collapsible
            key={del.id}
            open={isOpen}
            onOpenChange={() => toggleId(del.id)}
          >
            <div
              className={cn(
                "rounded-sm border border-border-primary bg-bg-secondary",
                isCritical && "border-l-2 border-l-sig-high"
              )}
            >
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
                    {/* Institution name + badges */}
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-serif text-sm font-semibold text-text-bright">
                        {del.institution}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
                            PRIORITY_STYLES[del.priority]
                          )}
                        >
                          {del.priority}
                        </span>
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
                            STATUS_STYLES[del.status]
                          )}
                        >
                          {STATUS_LABELS[del.status]}
                        </span>
                      </div>
                    </div>

                    {/* Lead visitor */}
                    {del.keyVisitors.length > 0 && (
                      <p className="font-sans text-[14px] text-text-secondary">
                        {del.keyVisitors[0].name} — {del.keyVisitors[0].title}
                      </p>
                    )}

                    {/* Date + category + size */}
                    <div className="mt-2 flex items-center gap-3 flex-wrap">
                      <span className="font-mono text-[12px] text-text-muted">
                        {formatDate(del.plannedDate)}
                      </span>
                      <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
                        {CATEGORY_LABELS[del.category]}
                      </span>
                      <span className="font-mono text-[12px] text-text-muted">
                        {del.size} visitors
                      </span>
                    </div>
                  </div>
                </button>
              </CollapsibleTrigger>

              <CollapsibleContent className="overflow-hidden">
                <div className="px-5 pb-4 pl-12 space-y-4">
                  {/* Strategic Context */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Strategic Context
                    </p>
                    <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
                      {del.strategicContext}
                    </p>
                  </div>

                  {/* Purpose */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Purpose
                    </p>
                    <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
                      {del.purpose}
                    </p>
                  </div>

                  {/* Key Visitors */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-2">
                      Key Visitors
                    </p>
                    <div className="space-y-1.5">
                      {del.keyVisitors.map((visitor) => (
                        <div key={visitor.name} className="flex items-start gap-2">
                          <span className="font-mono text-[14px] text-text-muted shrink-0 w-4 text-center">
                            •
                          </span>
                          <div>
                            <span className="font-sans text-[14px] text-text-bright">
                              {visitor.name}
                            </span>
                            <span className="font-sans text-[14px] text-text-muted ml-1">
                              — {visitor.title}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Previous Visits */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-2">
                      Previous Visits
                    </p>
                    {del.previousVisits.length === 0 ? (
                      <p className="font-sans text-[14px] text-text-muted italic">
                        First engagement — no previous visits on record.
                      </p>
                    ) : (
                      <div className="space-y-1.5">
                        {del.previousVisits.map((visit) => (
                          <div key={visit.date} className="flex items-start gap-2">
                            <span className="font-mono text-[12px] text-text-muted shrink-0 mt-0.5 w-20">
                              {formatDate(visit.date)}
                            </span>
                            <span className="font-sans text-[14px] text-text-secondary leading-snug">
                              {visit.outcome}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* MOU Status */}
                  {del.mouStatus && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                        MOU Status
                      </p>
                      <p className="mt-1 font-sans text-sm text-text-primary font-medium">
                        {del.mouStatus}
                      </p>
                    </div>
                  )}

                  {/* Owner */}
                  <div>
                    <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                      Owner
                    </p>
                    <p className="mt-1 font-mono text-[14px] text-text-secondary">
                      {del.owner}
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
