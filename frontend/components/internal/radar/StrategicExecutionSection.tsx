"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import data from "@/lib/data/internal/strategic-accountability.json";
import { StatusSummaryBar } from "@/components/internal/strategic-accountability/StatusSummaryBar";
import { STATUS_COLORS } from "@/components/internal/strategic-accountability/StatusBadge";
import type { Directive, DirectiveStatus } from "@/lib/types/internal-intelligence";

const directives = data.directives as Directive[];

const EXCEPTION_STATUSES: DirectiveStatus[] = ["Overdue", "Blocked"];

export function StrategicExecutionSection() {
  const [isOpen, setIsOpen] = useState(false);

  // Count directives by status
  const counts: Partial<Record<DirectiveStatus, number>> = {};
  for (const d of directives) {
    counts[d.status] = (counts[d.status] ?? 0) + 1;
  }

  const summaryParts: string[] = [];
  const ORDER: DirectiveStatus[] = [
    "Completed",
    "In progress",
    "On track",
    "Overdue",
    "Blocked",
    "Not started",
  ];
  for (const status of ORDER) {
    const count = counts[status];
    if (count) {
      summaryParts.push(`${count} ${status.toLowerCase()}`);
    }
  }
  const summaryText = `${directives.length} directives: ${summaryParts.join(", ")}`;

  // Exception directives (overdue + blocked)
  const exceptions = directives.filter((d) =>
    EXCEPTION_STATUSES.includes(d.status)
  );

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <section className="space-y-6">
        {/* Section header — clickable */}
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center gap-3 cursor-pointer group"
          >
            <div className="h-5 w-1 rounded-full bg-sig-high" />
            <span
              className={cn(
                "text-text-muted text-xs shrink-0 transition-transform duration-300 inline-block",
                isOpen && "rotate-90"
              )}
            >
              &#x25B8;
            </span>
            <h2 className="font-sans text-[16px] font-semibold uppercase tracking-[0.08em] text-text-primary">
              Execution Health
            </h2>
            <div className="h-px flex-1 bg-border-primary" />
          </button>
        </CollapsibleTrigger>

        {/* Content — collapsible */}
        <CollapsibleContent className="overflow-hidden">
          <div className="rounded-sm border border-border-primary bg-bg-secondary/30 px-5 py-5 space-y-5">
            {/* One-line summary */}
            <p className="font-sans text-sm leading-relaxed text-text-secondary">
              {summaryText}
            </p>

            {/* Status bar */}
            <StatusSummaryBar directives={directives} />

            {/* Exception rows — overdue and blocked only */}
            {exceptions.length > 0 && (
              <div className="space-y-2">
                {exceptions.map((d) => {
                  const latestUpdate =
                    d.updateHistory[d.updateHistory.length - 1]?.note ?? "";
                  const borderColor = STATUS_COLORS[d.status];
                  // Extract short owner name (first + last)
                  const ownerShort = d.owner.split(",")[0].trim();

                  return (
                    <div
                      key={d.id}
                      className="border-l-2 pl-4 py-2 bg-bg-tertiary/40 rounded-r-sm"
                      style={{ borderLeftColor: borderColor }}
                    >
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <span className="font-sans text-sm font-semibold text-text-primary">
                          {d.title}
                        </span>
                        <span className="font-mono text-[13px] text-text-muted">
                          {ownerShort}
                        </span>
                      </div>
                      <p className="font-sans text-[14px] leading-relaxed text-text-secondary mt-0.5">
                        {latestUpdate}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}

          </div>
        </CollapsibleContent>
      </section>
    </Collapsible>
  );
}
