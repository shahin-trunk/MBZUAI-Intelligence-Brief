"use client";

import { useState } from "react";
import data from "@/lib/data/internal/smt-recap.json";
import { MeetingCard } from "./MeetingCard";
import type { SmtMeeting } from "@/lib/types/internal-intelligence";

const meetings = data.meetings as SmtMeeting[];

export function SmtRecapPage() {
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());

  function toggleId(id: string) {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div className="space-y-6">
      {/* Meeting count */}
      <p className="font-sans text-sm text-text-secondary">
        {meetings.length} meeting{meetings.length !== 1 ? "s" : ""} this period
      </p>

      {/* Meeting cards */}
      <div className="space-y-3">
        {meetings.map((meeting) => (
          <MeetingCard
            key={meeting.id}
            meeting={meeting}
            isOpen={openIds.has(meeting.id)}
            onToggle={() => toggleId(meeting.id)}
          />
        ))}
      </div>
    </div>
  );
}
