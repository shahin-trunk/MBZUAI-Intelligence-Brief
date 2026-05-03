"use client";

import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import type { UpcomingDelegation } from "@/lib/types/internal-intelligence";

interface UpcomingDelegationCardsProps {
  delegations: UpcomingDelegation[];
}

function PresidentTag({ needed }: { needed: boolean | "optional" }) {
  if (needed === true) {
    return (
      <span className="inline-flex items-center rounded-full border border-sig-high/30 bg-sig-high/10 px-2 py-0.5 font-mono text-[12px] font-medium text-sig-high">
        President needed
      </span>
    );
  }
  if (needed === "optional") {
    return (
      <span className="inline-flex items-center rounded-full border border-sig-high/20 bg-sig-high/5 px-2 py-0.5 font-mono text-[12px] font-medium text-sig-high/70">
        President optional
      </span>
    );
  }
  return null;
}

function StatusBadge({ status }: { status: string }) {
  const style =
    status === "Confirmed"
      ? "bg-accent-success/15 text-accent-success border-accent-success/30"
      : status === "Scheduled"
        ? "bg-accent-info/15 text-accent-info border-accent-info/30"
        : status === "Active"
          ? "bg-accent-success/15 text-accent-success border-accent-success/30"
          : "bg-bg-tertiary text-text-muted border-border-primary";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium ${style}`}
    >
      {status}
    </span>
  );
}

export function UpcomingDelegationCards({ delegations }: UpcomingDelegationCardsProps) {
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
      {delegations.map((del) => {
        const isOpen = openIds.has(del.id);
        const goldBorder = del.presidentNeeded === true;

        return (
          <Collapsible.Root
            key={del.id}
            open={isOpen}
            onOpenChange={() => toggle(del.id)}
          >
            <div
              className={`bg-bg-secondary rounded-sm border border-border-primary ${goldBorder ? "border-l-2 border-l-sig-high" : ""}`}
            >
              {/* Collapsed header */}
              <Collapsible.Trigger asChild>
                <button
                  type="button"
                  className="flex w-full cursor-pointer items-start justify-between px-7 py-[22px] text-left"
                >
                  <div className="min-w-0 flex-1 space-y-2">
                    {/* Institution + visitor */}
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-serif text-sm font-semibold text-text-bright">
                        {del.institution}
                      </p>
                      <StatusBadge status={del.status} />
                      <PresidentTag needed={del.presidentNeeded} />
                    </div>

                    {/* Visitor + title + date */}
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="font-sans text-[14px] text-text-secondary">
                        {del.keyVisitor}
                        {del.visitorTitle ? ` — ${del.visitorTitle}` : ""}
                      </span>
                      <span className="font-mono text-[12px] text-text-muted">
                        {del.visitDate}
                      </span>
                    </div>

                    {/* Strategic purpose */}
                    <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                      {del.strategicPurpose}
                    </p>

                    {/* MBZUAI lead */}
                    <p className="font-mono text-[12px] text-text-muted">
                      MBZUAI Lead: {del.mbzuaiLead}
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
                  {/* Visiting members */}
                  {del.visitingMembers && del.visitingMembers.length > 0 && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Visiting Delegation
                      </p>
                      <ul className="space-y-1">
                        {del.visitingMembers.map((v) => (
                          <li
                            key={v.name}
                            className="font-sans text-[14px] text-text-secondary"
                          >
                            <span className="font-semibold text-text-bright">{v.name}</span>
                            {" — "}
                            {v.title}
                            {v.organization && (
                              <span className="text-text-muted">, {v.organization}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Internal attendees */}
                  {del.internalAttendees && del.internalAttendees.length > 0 && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        MBZUAI Attendees
                      </p>
                      <ul className="space-y-1">
                        {del.internalAttendees.map((a) => (
                          <li
                            key={a.name}
                            className="font-sans text-[14px] text-text-secondary"
                          >
                            <span className="font-semibold text-text-bright">{a.name}</span>
                            {" — "}
                            {a.title}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Expected outcome */}
                  {del.expectedOutcome && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Expected Outcome
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        {del.expectedOutcome}
                      </p>
                    </div>
                  )}

                  {/* Previous engagement */}
                  {del.previousEngagementDate && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Previous Engagement
                      </p>
                      <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                        <span className="font-mono text-[12px] text-text-muted">
                          {del.previousEngagementDate}
                        </span>
                        {del.previousEngagementOutcome
                          ? ` — ${del.previousEngagementOutcome}`
                          : ""}
                      </p>
                    </div>
                  )}

                  {/* Next step */}
                  {del.nextStep && (
                    <div>
                      <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted mb-1">
                        Next Step
                      </p>
                      <p className="font-sans text-[14px] text-sig-high font-medium leading-relaxed">
                        {del.nextStep}
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
