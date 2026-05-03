"use client";

import { useState } from "react";
import { DelegationModal } from "./DelegationModal";
import type {
  HostedDelegation,
  UpcomingDelegation,
  DelegationRegionalBreakdown,
} from "@/lib/types/internal-intelligence";

interface DelegationCardsProps {
  ytdCount: number;
  hostedThisMonth: HostedDelegation[];
  upcoming: UpcomingDelegation[];
  regionalBreakdown?: DelegationRegionalBreakdown[];
}

export function DelegationCards({
  ytdCount,
  hostedThisMonth,
  upcoming,
  regionalBreakdown,
}: DelegationCardsProps) {
  const [selected, setSelected] = useState<HostedDelegation | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleClick(delegation: HostedDelegation) {
    setSelected(delegation);
    setModalOpen(true);
  }

  return (
    <div className="space-y-6">
      {/* YTD count */}
      <p className="font-mono text-[13px] text-text-muted">
        {ytdCount} international delegations hosted year-to-date
      </p>

      {/* Regional Breakdown */}
      {regionalBreakdown && regionalBreakdown.length > 0 && (
        <div className="bg-bg-tertiary rounded-sm border border-border-primary overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border-primary">
                <th className="px-4 py-2 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium">
                  Region
                </th>
                <th className="px-4 py-2 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium text-right">
                  Delegations
                </th>
                <th className="px-4 py-2 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium text-right">
                  MOUs Signed
                </th>
              </tr>
            </thead>
            <tbody>
              {regionalBreakdown.map((r) => (
                <tr key={r.region} className="border-b border-border-primary last:border-b-0">
                  <td className="px-4 py-2 font-mono text-[14px] text-text-secondary">
                    {r.region}
                  </td>
                  <td className="px-4 py-2 font-mono text-[14px] text-text-bright font-medium text-right">
                    {r.count}
                  </td>
                  <td className="px-4 py-2 font-mono text-[14px] text-text-bright font-medium text-right">
                    {r.mousSigned}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Hosted this month */}
      <div className="space-y-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
          Hosted This Month
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-[14px]">
          {hostedThisMonth.map((delegation) => (
            <button
              key={delegation.id}
              type="button"
              onClick={() => handleClick(delegation)}
              className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
            >
              {/* Name */}
              <p className="font-serif text-sm text-text-bright leading-snug">
                {delegation.delegation}
              </p>

              {/* Lead Delegate */}
              {delegation.leadDelegate && (
                <p className="mt-1 font-sans text-[14px] text-text-secondary">
                  {delegation.leadDelegate}
                </p>
              )}

              {/* Date */}
              <div className="mt-2 flex items-center gap-3">
                <span className="font-mono text-[12px] text-text-muted">
                  {delegation.date}
                </span>
              </div>

              {/* Purpose (truncated) */}
              <p className="mt-2 font-sans text-[14px] text-text-muted line-clamp-2">
                {delegation.purpose}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Upcoming */}
      {upcoming.length > 0 && (
        <div className="space-y-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Upcoming
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
            {upcoming.map((delegation) => (
              <div
                key={delegation.id}
                className="bg-bg-secondary rounded-sm border border-border-primary/60 px-7 py-[22px]"
              >
                {/* Name */}
                <p className="font-serif text-sm text-text-bright leading-snug">
                  {delegation.delegation}
                </p>

                {/* Lead Delegate */}
                {delegation.leadDelegate && (
                  <p className="mt-1 font-sans text-[14px] text-text-secondary">
                    {delegation.leadDelegate}
                  </p>
                )}

                {/* Date */}
                <div className="mt-2 flex items-center gap-3">
                  <span className="font-mono text-[12px] text-text-muted">
                    {delegation.plannedDate}
                  </span>
                </div>

                {/* Purpose */}
                <p className="mt-2 font-sans text-[14px] text-text-secondary">
                  {delegation.purpose}
                </p>

                {/* Significance */}
                <p className="mt-2 font-sans text-[14px] text-text-muted italic leading-[1.6]">
                  {delegation.significance}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <DelegationModal
        delegation={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
