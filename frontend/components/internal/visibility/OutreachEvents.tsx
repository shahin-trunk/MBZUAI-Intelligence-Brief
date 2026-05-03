import type { OutreachEvent } from "@/lib/types/internal-intelligence";

interface OutreachEventsProps {
  events: OutreachEvent[];
}

function OutreachTypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {type}
    </span>
  );
}

export function OutreachEvents({ events }: OutreachEventsProps) {
  return (
    <div className="space-y-3">
      {events.map((event) => (
        <div
          key={event.id}
          className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px]"
        >
          {/* Name + Badge */}
          <div className="flex items-start justify-between gap-3">
            <p className="font-serif text-sm text-text-bright leading-snug">
              {event.name}
            </p>
            <OutreachTypeBadge type={event.type} />
          </div>

          {/* Date + Reach */}
          <div className="mt-2 flex items-center gap-4">
            <span className="font-mono text-[12px] text-text-muted">
              {event.date}
            </span>
            <span className="font-mono text-[12px] text-text-muted">
              Reach: {event.reach}
            </span>
          </div>

          {/* Description */}
          <p className="mt-2 font-sans text-[14px] text-text-secondary leading-relaxed">
            {event.description}
          </p>

          {/* Significance */}
          <p className="mt-2 font-sans text-[14px] text-text-muted italic leading-[1.6]">
            {event.significance}
          </p>
        </div>
      ))}
    </div>
  );
}
