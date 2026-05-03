"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { ProgramDevelopment } from "@/lib/types/internal-intelligence";
import { ProgramDevelopmentModal } from "./ProgramDevelopmentModal";

interface ProgramDevelopmentCardsProps {
  developments: ProgramDevelopment[];
}

function ScopeBadge({ scope }: { scope: ProgramDevelopment["scope"] }) {
  const styles: Record<ProgramDevelopment["scope"], string> = {
    Graduate: "bg-sig-high/10 text-sig-high/80 border-sig-high/20",
    Undergraduate: "bg-accent-primary/10 text-accent-primary/80 border-accent-primary/20",
    "University-wide": "bg-text-muted/10 text-text-muted border-border-primary",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
        styles[scope]
      )}
    >
      {scope}
    </span>
  );
}

function StatusBadge({ status }: { status: ProgramDevelopment["status"] }) {
  const styles: Record<ProgramDevelopment["status"], string> = {
    Active: "bg-accent-primary/10 text-accent-primary/70 border-accent-primary/20",
    "In design": "bg-text-muted/10 text-text-muted border-border-primary",
    Completed: "bg-accent-success/15 text-accent-success border-accent-success/30",
    "Under review": "bg-amber-500/10 text-amber-400 border-amber-500/20",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
        styles[status]
      )}
    >
      {status}
    </span>
  );
}

export function ProgramDevelopmentCards({ developments }: ProgramDevelopmentCardsProps) {
  const [selectedDevelopment, setSelectedDevelopment] =
    useState<ProgramDevelopment | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleCardClick(development: ProgramDevelopment) {
    setSelectedDevelopment(development);
    setModalOpen(true);
  }

  return (
    <>
      {/* Count subtitle */}
      <p className="font-mono text-[14px] leading-[1.6] text-text-muted mb-4">
        {developments.length} program initiative{developments.length !== 1 ? "s" : ""}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
        {developments.map((dev) => (
          <button
            key={dev.id}
            type="button"
            onClick={() => handleCardClick(dev)}
            className="bg-bg-tertiary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-secondary hover:border-border-primary cursor-pointer"
          >
            {/* Initiative title — prominent */}
            <p className="font-sans text-sm font-medium text-text-bright leading-snug">
              {dev.title}
            </p>

            {/* Scope + Status badges */}
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <ScopeBadge scope={dev.scope} />
              <StatusBadge status={dev.status} />
            </div>

            {/* Brief description */}
            <p className="mt-2 font-sans text-[14px] text-text-muted leading-relaxed line-clamp-2">
              {dev.briefDescription}
            </p>

            {/* Owner */}
            <p className="mt-2 font-mono text-[12px] text-text-muted truncate">
              {dev.owner}
            </p>
          </button>
        ))}
      </div>

      <ProgramDevelopmentModal
        development={selectedDevelopment}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
