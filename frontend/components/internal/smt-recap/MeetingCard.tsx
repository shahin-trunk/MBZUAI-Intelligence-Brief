"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { DecisionsAndActions } from "./DecisionsAndActions";
import type { SmtMeeting } from "@/lib/types/internal-intelligence";

interface MeetingCardProps {
  meeting: SmtMeeting;
  isOpen: boolean;
  onToggle: () => void;
}

function formatMeetingDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function MeetingCard({ meeting, isOpen, onToggle }: MeetingCardProps) {
  const [showAttendees, setShowAttendees] = useState(false);

  const typeLabel = meeting.number
    ? `${meeting.type} ${meeting.number}`
    : meeting.type;

  return (
    <Collapsible open={isOpen} onOpenChange={onToggle}>
      <div className="rounded-sm border border-border-primary bg-bg-secondary">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-start gap-3 text-left cursor-pointer px-7 py-[22px]"
          >
            <span
              className={cn(
                "mt-1.5 text-text-muted text-xs shrink-0 transition-transform duration-300 inline-block",
                isOpen && "rotate-90"
              )}
            >
              &#x25B8;
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-3 mb-1">
                <span className="font-serif text-sm font-semibold text-text-bright">
                  {typeLabel}
                </span>
                <span className="font-mono text-[13px] text-text-muted shrink-0">
                  {formatMeetingDate(meeting.date)}
                </span>
              </div>
              <p className="font-sans text-sm leading-snug text-text-secondary">
                {meeting.summary}
              </p>
              <p className="font-mono text-[13px] text-text-muted mt-1.5">
                Chair: {meeting.chair}
              </p>
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent className="overflow-hidden">
          <div className="px-5 pb-5 pl-12 space-y-5">
            {/* Attendees toggle */}
            <div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowAttendees((prev) => !prev);
                }}
                className="font-mono text-[13px] text-accent-primary hover:text-accent-primary/80 cursor-pointer"
              >
                {showAttendees
                  ? "Hide attendees"
                  : `Show attendees (${meeting.attendees.length})`}
              </button>
              {showAttendees && (
                <div className="mt-2">
                  <p className="font-sans text-[14px] leading-relaxed text-text-muted">
                    {meeting.attendees.join("; ")}
                  </p>
                  {meeting.apologies.length > 0 && (
                    <p className="font-sans text-[14px] text-text-muted mt-1.5">
                      <span className="font-mono text-[13px] text-text-muted">
                        Apologies:
                      </span>{" "}
                      {meeting.apologies.join("; ")}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Key Decisions & Action Items — side by side */}
            <DecisionsAndActions
              decisions={meeting.keyDecisions}
              actionItems={meeting.actionItems}
            />

            {/* Meeting metadata */}
            <p className="font-mono text-[13px] text-text-muted">
              {meeting.time} · {meeting.location}
            </p>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
