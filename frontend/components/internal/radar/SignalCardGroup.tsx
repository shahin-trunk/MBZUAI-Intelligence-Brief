"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import type { RadarSignalCard, RadarCategory } from "@/lib/types/internal-intelligence";
import { SignalCard } from "./SignalCard";

interface SignalCardGroupProps {
  category: RadarCategory;
  cards: RadarSignalCard[];
}

const CATEGORY_CONFIG: Record<
  RadarCategory,
  { label: string; accent: string }
> = {
  attention: {
    label: "Attention Needed",
    accent: "border-l-accent-warning",
  },
  wins: {
    label: "Wins & Highlights",
    accent: "border-l-accent-success",
  },
};

export function SignalCardGroup({ category, cards }: SignalCardGroupProps) {
  const [isOpen, setIsOpen] = useState(false);
  const config = CATEGORY_CONFIG[category];

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <section className="space-y-4">
        {/* Section header — clickable */}
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center gap-3 cursor-pointer group"
          >
            <div className={`h-5 w-1 rounded-full ${config.accent}`} />
            <span
              className={cn(
                "text-text-muted text-xs shrink-0 transition-transform duration-300 inline-block",
                isOpen && "rotate-90"
              )}
            >
              &#x25B8;
            </span>
            <h2 className="font-sans text-[16px] font-semibold uppercase tracking-[0.08em] text-text-primary">
              {config.label}
            </h2>
            <span className="font-mono text-[13px] text-text-muted">
              {cards.length} {cards.length === 1 ? "item" : "items"}
            </span>
            <div className="h-px flex-1 bg-border-primary" />
          </button>
        </CollapsibleTrigger>

        {/* Card grid — collapsible */}
        <CollapsibleContent className="overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-[14px]">
            {cards.map((card) => (
              <SignalCard key={card.id} card={card} />
            ))}
          </div>
        </CollapsibleContent>
      </section>
    </Collapsible>
  );
}
