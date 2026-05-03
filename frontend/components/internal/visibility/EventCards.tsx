"use client";

import { useState } from "react";
import { EventModal } from "./EventModal";
import type { EventDelivered } from "@/lib/types/internal-intelligence";

interface EventCardsProps {
  events: EventDelivered[];
}

function EventTypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {type}
    </span>
  );
}

export function EventCards({ events }: EventCardsProps) {
  const [selected, setSelected] = useState<EventDelivered | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleClick(event: EventDelivered) {
    setSelected(event);
    setModalOpen(true);
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {events.map((event) => (
          <button
            key={event.id}
            type="button"
            onClick={() => handleClick(event)}
            className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
          >
            {/* Name */}
            <p className="font-serif text-base text-text-bright leading-snug">
              {event.name}
            </p>

            {/* Type + Date */}
            <div className="mt-2 flex items-center gap-2">
              <EventTypeBadge type={event.type} />
              <span className="font-mono text-[12px] text-text-muted">
                {event.date}
              </span>
            </div>

            {/* Attendance */}
            {event.attendees.total !== null && (
              <p className="mt-2 font-mono text-[14px] text-text-secondary">
                {event.attendees.total} attendees
              </p>
            )}

            {/* Notable Attendees (truncated) */}
            {event.notableAttendees.length > 0 && (
              <p className="mt-2 font-sans text-[14px] text-text-muted line-clamp-2">
                {event.notableAttendees.slice(0, 3).join(" · ")}
                {event.notableAttendees.length > 3 && " …"}
              </p>
            )}

            {/* Media */}
            {event.mediaGenerated && (
              <p className="mt-1 font-mono text-[12px] text-accent-primary">
                {event.mediaGenerated}
              </p>
            )}
          </button>
        ))}
      </div>

      <EventModal
        event={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
