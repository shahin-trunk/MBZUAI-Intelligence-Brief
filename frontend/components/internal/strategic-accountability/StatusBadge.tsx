import { cn } from "@/lib/utils";
import type { DirectiveStatus } from "@/lib/types/internal-intelligence";

interface StatusBadgeProps {
  status: DirectiveStatus;
  size?: "sm" | "md";
}

const STATUS_STYLES: Record<DirectiveStatus, string> = {
  Completed: "bg-accent-success/15 text-accent-success border-accent-success/30",
  "In progress": "bg-accent-primary/15 text-accent-primary border-accent-primary/30",
  "On track": "bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/30",
  Overdue: "bg-accent-warning/15 text-accent-warning border-accent-warning/30",
  Blocked: "bg-accent-danger/15 text-accent-danger border-accent-danger/30",
  "Not started": "bg-bg-tertiary text-text-muted border-border-primary",
};

export const STATUS_COLORS: Record<DirectiveStatus, string> = {
  Completed: "#22C55E",
  "In progress": "#3B82F6",
  "On track": "#06B6D4",
  Overdue: "#EAB308",
  Blocked: "#EF4444",
  "Not started": "var(--text-muted)",
};

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border font-mono font-medium",
        STATUS_STYLES[status],
        size === "sm"
          ? "px-2 py-0.5 text-[12px]"
          : "px-2.5 py-0.5 text-[13px]"
      )}
    >
      {status}
    </span>
  );
}
