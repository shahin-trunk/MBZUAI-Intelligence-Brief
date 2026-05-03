"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { EventDelivered } from "@/lib/types/internal-intelligence";

interface EventModalProps {
  event: EventDelivered | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function EventTypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {type}
    </span>
  );
}

export function EventModal({ event, open, onOpenChange }: EventModalProps) {
  if (!event) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl text-text-bright leading-snug">
            {event.name}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="flex items-center gap-2 mt-1">
              <EventTypeBadge type={event.type} />
              <span className="font-mono text-[13px] text-text-muted">
                {event.date}
              </span>
            </div>
          </DialogDescription>
        </DialogHeader>

        {/* Location */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Location
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary">
            {event.location}
          </p>
        </div>

        {/* Description */}
        <div className="mt-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Description
          </p>
          <p className="mt-1 font-sans text-sm text-text-secondary leading-relaxed">
            {event.description}
          </p>
        </div>

        {/* Attendance */}
        {event.attendees.total !== null && (
          <div className="mt-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Attendance
            </p>
            <div className="mt-1 flex items-center gap-4">
              <span className="font-mono text-sm text-text-bright font-bold">
                {event.attendees.total} total
              </span>
              {event.attendees.inPerson !== null && (
                <span className="font-mono text-[13px] text-text-muted">
                  {event.attendees.inPerson} in-person
                </span>
              )}
              {event.attendees.online !== null && event.attendees.online > 0 && (
                <span className="font-mono text-[13px] text-text-muted">
                  {event.attendees.online} online
                </span>
              )}
            </div>
          </div>
        )}

        {/* Notable Attendees */}
        {event.notableAttendees.length > 0 && (
          <div className="mt-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Notable Attendees
            </p>
            <ul className="mt-1 space-y-0.5">
              {event.notableAttendees.map((attendee) => (
                <li
                  key={attendee}
                  className="font-sans text-sm text-text-secondary"
                >
                  {attendee}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Media Generated */}
        {event.mediaGenerated && (
          <div className="mt-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Media Generated
            </p>
            <p className="mt-1 font-sans text-sm text-text-secondary">
              {event.mediaGenerated}
            </p>
          </div>
        )}

        {/* Significance */}
        <div className="mt-5 border-l-2 border-l-sig-high bg-sig-high/5 px-4 py-3 rounded-sm">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-1">
            Why This Matters
          </p>
          <p className="font-sans text-sm text-text-secondary leading-relaxed">
            {event.significance}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
