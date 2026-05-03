"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { UpcomingResearchEvent } from "@/lib/types/internal-intelligence";

interface EventModalProps {
  event: UpcomingResearchEvent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatDateRange(start: string, end: string): string {
  const s = new Date(start + "T00:00:00");
  const e = new Date(end + "T00:00:00");

  const sMonth = s.toLocaleDateString("en-US", { month: "long" });
  const eMonth = e.toLocaleDateString("en-US", { month: "long" });
  const sDay = s.getDate();
  const eDay = e.getDate();
  const year = s.getFullYear();

  if (start === end) return `${sMonth} ${sDay}, ${year}`;
  if (sMonth === eMonth) return `${sMonth} ${sDay}–${eDay}, ${year}`;
  return `${sMonth} ${sDay} – ${eMonth} ${eDay}, ${year}`;
}

function RegistrationBadge({ status }: { status: string }) {
  let style: string;
  let label: string;

  if (status === "open") {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
    label = "Registration Open";
  } else if (status === "invite_only") {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
    label = "Invite Only";
  } else {
    style = "bg-bg-tertiary text-text-muted border-border-primary";
    label = "Registration Closed";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        style
      )}
    >
      {label}
    </span>
  );
}

export function EventModal({ event, open, onOpenChange }: EventModalProps) {
  if (!event) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {event.name}
          </DialogTitle>
          <DialogDescription className="text-text-secondary text-sm">
            {event.type}
          </DialogDescription>
        </DialogHeader>

        {/* Date + Registration */}
        <div className="flex items-center gap-3 mt-2">
          <span className="font-mono text-sm font-medium text-text-primary">
            {formatDateRange(event.dateStart, event.dateEnd)}
          </span>
          <RegistrationBadge status={event.registrationStatus} />
        </div>

        {/* Location */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Location
          </h3>
          <p className="font-sans text-sm text-text-primary">{event.location}</p>
        </div>

        {/* Description */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Description
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {event.description}
          </p>
        </div>

        {/* Chair */}
        {event.chair && (
          <div className="mt-4">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
              Chair
            </h3>
            <p className="font-sans text-sm text-text-primary">{event.chair}</p>
          </div>
        )}

        {/* Speakers */}
        {event.speakers && event.speakers.length > 0 && (
          <div className="mt-4">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
              Confirmed Speakers
            </h3>
            <ul className="list-disc list-inside space-y-1">
              {event.speakers.map((speaker) => (
                <li key={speaker} className="font-sans text-sm text-text-primary">
                  {speaker}
                </li>
              ))}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
