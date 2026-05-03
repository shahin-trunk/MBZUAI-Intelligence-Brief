import type { Directive, DirectiveStatus } from "@/lib/types/internal-intelligence";
import { STATUS_COLORS } from "./StatusBadge";

interface StatusSummaryBarProps {
  directives: Directive[];
}

const STATUS_ORDER: DirectiveStatus[] = [
  "Completed",
  "In progress",
  "On track",
  "Overdue",
  "Blocked",
  "Not started",
];

export function StatusSummaryBar({ directives }: StatusSummaryBarProps) {
  const counts = STATUS_ORDER.map((status) => ({
    status,
    count: directives.filter((d) => d.status === status).length,
  }));

  return (
    <div className="flex flex-wrap items-center gap-2">
      {counts.map(({ status, count }) => (
        <div
          key={status}
          className="flex items-center gap-1.5 rounded-sm border border-border-primary bg-bg-tertiary px-3 py-1.5"
        >
          <div
            className="h-2 w-2 rounded-full shrink-0"
            style={{ backgroundColor: STATUS_COLORS[status] }}
          />
          <span className="font-mono text-[14px] text-text-bright font-bold">
            {count}
          </span>
          <span className="font-mono text-[13px] text-text-muted">
            {status}
          </span>
        </div>
      ))}
    </div>
  );
}
