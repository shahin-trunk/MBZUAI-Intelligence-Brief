"use client";

import type { NotableAttendee } from "@/lib/types/internal-intelligence";

interface NotableAttendeeCardsProps {
  attendees: NotableAttendee[];
}

export function NotableAttendeeCards({ attendees }: NotableAttendeeCardsProps) {
  return (
    <div className="space-y-3">
      <p className="font-mono text-[13px] text-text-muted">
        {attendees.length} notable attendee{attendees.length !== 1 ? "s" : ""}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-[14px]">
        {attendees.map((attendee) => (
          <div
            key={attendee.id}
            className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px]"
          >
            {/* Name */}
            <p className="font-serif text-sm text-text-bright leading-snug">
              {attendee.name}
            </p>

            {/* Title */}
            <p className="mt-1 font-sans text-[14px] text-text-secondary">
              {attendee.title}
            </p>

            {/* Program badge */}
            <div className="mt-2">
              <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
                {attendee.program}
              </span>
            </div>

            {/* Significance */}
            <p className="mt-3 font-sans text-[14px] text-text-muted leading-[1.6]">
              {attendee.significance}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
