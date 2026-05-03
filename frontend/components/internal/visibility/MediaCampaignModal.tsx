"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { MediaCampaign } from "@/lib/types/internal-intelligence";

interface MediaCampaignModalProps {
  campaign: MediaCampaign | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
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
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        styles[status]
      )}
    >
      {status}
    </span>
  );
}

export function MediaCampaignModal({
  campaign,
  open,
  onOpenChange,
}: MediaCampaignModalProps) {
  if (!campaign) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-[28px] text-text-bright">
            {campaign.name}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-2 mt-1">
              <StatusBadge status={campaign.status} />
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Owner */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Owner
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {campaign.owner}
          </p>
        </div>

        {/* Full description */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Description
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {campaign.fullDescription}
          </p>
        </div>

        {/* Timeline */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Timeline
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {campaign.timeline}
          </p>
        </div>

        {/* Channels */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Channels
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {campaign.channels}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
