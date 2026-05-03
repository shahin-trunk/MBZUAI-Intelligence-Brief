"use client";

import { DirectiveCard } from "./DirectiveCard";
import { STATUS_COLORS } from "./StatusBadge";
import type { Directive, DirectiveStatus } from "@/lib/types/internal-intelligence";

interface DirectiveCardGroupProps {
  status: DirectiveStatus;
  directives: Directive[];
  onCardClick: (directive: Directive) => void;
}

export function DirectiveCardGroup({
  status,
  directives,
  onCardClick,
}: DirectiveCardGroupProps) {
  if (directives.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* Group header */}
      <div className="flex items-center gap-2">
        <div
          className="h-2.5 w-2.5 rounded-full shrink-0"
          style={{ backgroundColor: STATUS_COLORS[status] }}
        />
        <h3 className="font-mono text-[14px] uppercase tracking-[0.08em] text-text-secondary font-medium">
          {status}
        </h3>
        <span className="font-mono text-[13px] text-text-muted">
          — {directives.length} {directives.length === 1 ? "directive" : "directives"}
        </span>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {directives.map((directive) => (
          <DirectiveCard
            key={directive.id}
            directive={directive}
            onClick={onCardClick}
          />
        ))}
      </div>
    </div>
  );
}
