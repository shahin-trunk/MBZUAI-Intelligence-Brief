import { cn } from "@/lib/utils";
import type { SmtDecision, SmtActionItem } from "@/lib/types/internal-intelligence";

interface DecisionsAndActionsProps {
  decisions: SmtDecision[];
  actionItems: SmtActionItem[];
}

function isOverdue(deadline: string | null): boolean {
  if (!deadline) return false;
  const now = new Date();
  if (/^\d{4}-\d{2}-\d{2}$/.test(deadline)) {
    return new Date(deadline) < now;
  }
  const monthNames: Record<string, number> = {
    January: 0, February: 1, March: 2, April: 3, May: 4, June: 5,
    July: 6, August: 7, September: 8, October: 9, November: 10, December: 11,
  };
  const parts = deadline.split(" ");
  if (parts.length === 2 && monthNames[parts[0]] !== undefined) {
    const year = parseInt(parts[1], 10);
    const month = monthNames[parts[0]];
    const endOfMonth = new Date(year, month + 1, 0);
    return endOfMonth < now;
  }
  return false;
}

function formatDeadline(deadline: string | null): string {
  if (!deadline) return "No deadline";
  return deadline;
}

export function DecisionsAndActions({
  decisions,
  actionItems,
}: DecisionsAndActionsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* ── Left column — Key Decisions ──────────────────────────────── */}
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
          Key Decisions
        </p>
        <div className="border-l-2 border-l-sig-high rounded-sm border border-border-primary bg-bg-secondary overflow-hidden">
          {decisions.map((decision, i) => (
            <div
              key={i}
              className={cn(
                "flex gap-3 px-4 py-3",
                i > 0 && "border-t border-border-primary"
              )}
            >
              <span className="font-mono text-[13px] text-sig-high shrink-0 mt-0.5 font-semibold">
                {i + 1}.
              </span>
              <p className="font-sans text-sm leading-relaxed text-text-primary">
                {decision.text}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right column — Action Items ──────────────────────────────── */}
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
          Action Items
        </p>
        <div className="space-y-[10px]">
          {actionItems.map((item, i) => {
            const overdue = isOverdue(item.deadline);

            return (
              <div
                key={i}
                className={cn(
                  "bg-bg-tertiary rounded-sm px-4 py-3 border-l-2",
                  overdue
                    ? "border-l-accent-warning"
                    : item.deadline
                      ? "border-l-accent-primary"
                      : "border-l-border-accent"
                )}
              >
                <p className="font-sans text-sm leading-snug text-text-primary">
                  {item.action}
                </p>
                <div className="flex items-center justify-between gap-3 mt-2">
                  <span className="inline-flex items-center bg-bg-secondary rounded-full px-2 py-0.5 font-mono text-[12px] text-text-muted border border-border-primary">
                    {item.owner}
                  </span>
                  <span
                    className={cn(
                      "font-mono text-[12px] shrink-0",
                      overdue
                        ? "text-accent-warning font-medium"
                        : item.deadline
                          ? "text-text-secondary"
                          : "text-text-muted"
                    )}
                  >
                    {formatDeadline(item.deadline)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
