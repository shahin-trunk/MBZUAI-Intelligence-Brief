import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import type { Directive } from "@/lib/types/internal-intelligence";

interface DirectiveCardProps {
  directive: Directive;
  onClick: (directive: Directive) => void;
}

function PriorityDot({ priority }: { priority: Directive["priority"] }) {
  const colorClass =
    priority === "critical"
      ? "bg-accent-danger"
      : priority === "high"
        ? "bg-accent-warning"
        : "bg-text-muted";

  return (
    <span
      className={cn("inline-block h-2 w-2 rounded-full shrink-0", colorClass)}
      title={`${priority} priority`}
    />
  );
}

function SourceBadge({ sourceType }: { sourceType: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {sourceType}
    </span>
  );
}

export function DirectiveCard({ directive, onClick }: DirectiveCardProps) {
  const isOverdue = directive.status === "Overdue";
  const isBlocked = directive.status === "Blocked";
  const latestUpdate =
    directive.updateHistory[directive.updateHistory.length - 1];

  return (
    <button
      type="button"
      onClick={() => onClick(directive)}
      className={cn(
        "bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer w-full",
        isOverdue && "border-l-2 border-l-accent-warning",
        isBlocked && "border-l-2 border-l-accent-danger"
      )}
    >
      {/* Title + Priority */}
      <div className="flex items-start gap-2">
        <PriorityDot priority={directive.priority} />
        <p className="font-serif text-sm text-text-bright leading-snug flex-1">
          {directive.title}
        </p>
      </div>

      {/* Description (truncated) */}
      <p className="mt-1.5 font-sans text-[14px] text-text-muted line-clamp-2 pl-4">
        {directive.description}
      </p>

      {/* Source + Status */}
      <div className="mt-2.5 flex items-center gap-2 pl-4 flex-wrap">
        <SourceBadge sourceType={directive.sourceType} />
        <StatusBadge status={directive.status} />
      </div>

      {/* Owner */}
      <p className="mt-2 font-mono text-[12px] text-text-muted pl-4">
        {directive.owner}
      </p>

      {/* Deadline */}
      <div className="mt-1 flex items-center gap-2 pl-4">
        <span className="font-mono text-[12px] text-text-muted">
          {directive.deadline
            ? `Deadline: ${directive.deadline}`
            : "No deadline set"}
        </span>
        {isOverdue && (
          <span className="font-mono text-[12px] font-bold text-accent-danger">
            OVERDUE
          </span>
        )}
      </div>

      {/* Latest update */}
      {latestUpdate && (
        <div className="mt-2 border-t border-border-primary/50 pt-2 pl-4">
          <p className="font-mono text-[12px] text-text-muted">
            {latestUpdate.date}
          </p>
          <p className="font-sans text-[13px] text-text-secondary line-clamp-1">
            {latestUpdate.note}
          </p>
        </div>
      )}
    </button>
  );
}
