"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { UpcomingResearchEvent } from "@/lib/types/internal-intelligence";
import { EventModal } from "./EventModal";

interface UpcomingResearchEventsSectionProps {
  events: UpcomingResearchEvent[];
}

function formatDateRange(start: string, end: string): string {
  const s = new Date(start + "T00:00:00");
  const e = new Date(end + "T00:00:00");

  const sMonth = s.toLocaleDateString("en-US", { month: "short" });
  const eMonth = e.toLocaleDateString("en-US", { month: "short" });
  const sDay = s.getDate();
  const eDay = e.getDate();
  const year = s.getFullYear();

  // Single day
  if (start === end) {
    return `${sMonth} ${sDay}, ${year}`;
  }

  // Same month
  if (sMonth === eMonth) {
    return `${sMonth} ${sDay}–${eDay}, ${year}`;
  }

  // Cross month
  return `${sMonth} ${sDay} – ${eMonth} ${eDay}, ${year}`;
}

function RegistrationBadge({ status }: { status: string }) {
  let style: string;
  let label: string;

  if (status === "open") {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
    label = "Open";
  } else if (status === "invite_only") {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
    label = "Invite Only";
  } else {
    style = "bg-bg-tertiary text-text-muted border-border-primary";
    label = "Closed";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
        style
      )}
    >
      {label}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {type}
    </span>
  );
}

export function UpcomingResearchEventsSection({
  events,
}: UpcomingResearchEventsSectionProps) {
  const [selectedEvent, setSelectedEvent] = useState<UpcomingResearchEvent | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="space-y-4">
      <p className="font-mono text-[13px] text-text-muted">
        {events.length} upcoming
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-[14px]">
        {events.map((event) => (
          <button
            key={event.id}
            type="button"
            onClick={() => {
              setSelectedEvent(event);
              setModalOpen(true);
            }}
            className="rounded-sm border border-border-primary bg-bg-secondary px-7 py-[22px] text-left transition-colors hover:border-text-muted hover:bg-bg-tertiary/50 cursor-pointer"
          >
            <p className="font-serif text-base text-text-bright leading-snug line-clamp-2">
              {event.name}
            </p>

            <p className="font-mono text-[14px] text-text-secondary mt-2">
              {formatDateRange(event.dateStart, event.dateEnd)}
            </p>

            <div className="flex items-center gap-2 mt-2">
              <TypeBadge type={event.type} />
              <RegistrationBadge status={event.registrationStatus} />
            </div>

            <p className="font-sans text-[14px] text-text-muted mt-2">
              {event.location}
            </p>

            {event.chair && (
              <p className="font-mono text-[12px] text-text-muted mt-1">
                Chaired by {event.chair}
              </p>
            )}
          </button>
        ))}
      </div>

      <EventModal
        event={selectedEvent}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
