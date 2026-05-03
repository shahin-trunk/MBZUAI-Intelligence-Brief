"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { FlagshipPublication } from "@/lib/types/internal-intelligence";
import { PublicationModal } from "./PublicationModal";

interface FlagshipPublicationCardsProps {
  publications: FlagshipPublication[];
}

function TierBadge({ tier }: { tier: string }) {
  const styles: Record<string, string> = {
    "Tier 1": "bg-sig-high/15 text-sig-high border-sig-high/30",
    "Tier 2": "bg-accent-primary/15 text-accent-primary border-accent-primary/30",
    "Tier 3": "bg-bg-tertiary text-text-muted border-border-primary",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
        styles[tier] || styles["Tier 3"]
      )}
    >
      {tier}
    </span>
  );
}

export function FlagshipPublicationCards({ publications }: FlagshipPublicationCardsProps) {
  const [selected, setSelected] = useState<FlagshipPublication | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleClick(pub: FlagshipPublication) {
    setSelected(pub);
    setModalOpen(true);
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {publications.map((pub) => (
          <button
            key={pub.id}
            type="button"
            onClick={() => handleClick(pub)}
            className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
          >
            {/* Title */}
            <p className="font-serif text-base text-text-bright leading-snug line-clamp-2">
              {pub.title}
            </p>

            {/* Venue + Tier */}
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <span className="font-mono text-[13px] text-text-secondary">
                {pub.venue}
              </span>
              <TierBadge tier={pub.tier} />
            </div>

            {/* Authors */}
            <p className="mt-2 font-sans text-[14px] text-text-muted truncate">
              {pub.authors[0]}{pub.authors.length > 1 ? ` et al. (${pub.authors.length})` : ""}
            </p>

            {/* Division + Date */}
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="font-mono text-[12px] text-text-muted">
                {pub.division}
              </span>
              <span className="font-mono text-[12px] text-text-muted">
                {new Date(pub.date + "T00:00:00").toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })}
              </span>
            </div>
          </button>
        ))}
      </div>

      <PublicationModal
        publication={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
