"use client";

interface ProgramHighlight {
  entity: string;
  topic: string;
  notableAttendee: string;
}

interface ProgramHighlightsProps {
  practical: ProgramHighlight[];
  theory: ProgramHighlight[];
}

function HighlightList({ items }: { items: ProgramHighlight[] }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div
          key={`${item.entity}-${item.topic}`}
          className="bg-bg-secondary rounded-sm border border-border-primary px-4 py-3"
        >
          <p className="font-sans text-sm text-text-bright font-medium">
            {item.entity}
          </p>
          <p className="mt-1 font-sans text-[14px] text-text-secondary">
            {item.topic}
          </p>
          <p className="mt-1 font-mono text-[12px] text-text-muted">
            {item.notableAttendee}
          </p>
        </div>
      ))}
    </div>
  );
}

export function ProgramHighlights({ practical, theory }: ProgramHighlightsProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
          Practical Applications
        </p>
        <HighlightList items={practical} />
      </div>
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
          Theory & Foundations
        </p>
        <HighlightList items={theory} />
      </div>
    </div>
  );
}
