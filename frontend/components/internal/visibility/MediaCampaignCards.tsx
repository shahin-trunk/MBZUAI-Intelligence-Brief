"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { MediaCampaign } from "@/lib/types/internal-intelligence";
import { MediaCampaignModal } from "./MediaCampaignModal";

interface MediaCampaignCardsProps {
  campaigns: MediaCampaign[];
}

function StatusBadge({ status }: { status: MediaCampaign["status"] }) {
  const styles: Record<MediaCampaign["status"], string> = {
    Active: "bg-accent-primary/10 text-accent-primary/70 border-accent-primary/20",
    "In planning": "bg-text-muted/10 text-text-muted border-border-primary",
    Completed: "bg-accent-success/15 text-accent-success border-accent-success/30",
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

function ProgressBar({ status }: { status: MediaCampaign["status"] }) {
  const config: Record<MediaCampaign["status"], { width: string; color: string; label: string }> = {
    Active: { width: "100%", color: "bg-accent-success", label: "Active" },
    "In planning": { width: "30%", color: "bg-text-muted/50", label: "Planning" },
    Completed: { width: "100%", color: "bg-accent-success", label: "Complete" },
  };
  const { width, color, label } = config[status];

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-[11px] text-text-muted uppercase tracking-wider">{label}</span>
        {status === "Completed" && (
          <svg className="h-3 w-3 text-accent-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        )}
      </div>
      <div className="h-1 w-full rounded-full bg-border-primary">
        <div className={cn("h-1 rounded-full", color)} style={{ width }} />
      </div>
    </div>
  );
}

export function MediaCampaignCards({ campaigns }: MediaCampaignCardsProps) {
  const [selectedCampaign, setSelectedCampaign] =
    useState<MediaCampaign | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleCardClick(campaign: MediaCampaign) {
    setSelectedCampaign(campaign);
    setModalOpen(true);
  }

  return (
    <>
      {/* Count subtitle */}
      <p className="font-mono text-[14px] leading-[1.6] text-text-muted mb-4">
        {campaigns.length} active campaign{campaigns.length !== 1 ? "s" : ""}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
        {campaigns.map((campaign) => (
          <button
            key={campaign.id}
            type="button"
            onClick={() => handleCardClick(campaign)}
            className="bg-bg-tertiary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-secondary hover:border-border-primary cursor-pointer"
          >
            {/* Campaign name — prominent */}
            <p className="font-sans text-sm font-medium text-text-bright leading-snug">
              {campaign.name}
            </p>

            {/* Status badge */}
            <div className="mt-2">
              <StatusBadge status={campaign.status} />
            </div>

            {/* Brief description */}
            <p className="mt-2 font-sans text-[14px] text-text-muted leading-relaxed line-clamp-2">
              {campaign.briefDescription}
            </p>

            {/* Timeline */}
            <p className="mt-2 font-mono text-[12px] text-text-muted truncate">
              {campaign.timeline}
            </p>

            {/* Owner */}
            <p className="mt-1 font-mono text-[12px] text-text-muted truncate">
              {campaign.owner}
            </p>

            {/* Progress */}
            <ProgressBar status={campaign.status} />
          </button>
        ))}
      </div>

      <MediaCampaignModal
        campaign={selectedCampaign}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
