import type { RecentStrategicVisit } from "@/lib/types/internal-intelligence";

interface RecentStrategicVisitsProps {
  visits: RecentStrategicVisit[];
}

function FollowUpBadge({ status }: { status: string }) {
  const style =
    status === "Active"
      ? "bg-accent-success/15 text-accent-success border-accent-success/30"
      : status === "Exploratory"
        ? "bg-sig-high/10 text-sig-high border-sig-high/30"
        : "bg-bg-tertiary text-text-muted border-border-primary";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium ${style}`}
    >
      {status}
    </span>
  );
}

export function RecentStrategicVisits({ visits }: RecentStrategicVisitsProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-border-primary">
            <th className="pb-2 pr-4 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
              Institution
            </th>
            <th className="pb-2 pr-4 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
              Date
            </th>
            <th className="pb-2 pr-4 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
              Key Visitor
            </th>
            <th className="pb-2 pr-4 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
              MBZUAI Host
            </th>
            <th className="pb-2 pr-4 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
              Purpose
            </th>
            <th className="pb-2 pr-4 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
              Outcome
            </th>
            <th className="pb-2 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
              Follow-up
            </th>
          </tr>
        </thead>
        <tbody>
          {visits.map((visit) => (
            <tr
              key={visit.id}
              className="border-b border-border-primary/50 last:border-0"
            >
              <td className="py-3 pr-4 font-serif text-[14px] text-text-bright">
                {visit.institution}
              </td>
              <td className="py-3 pr-4 font-mono text-[12px] text-text-muted whitespace-nowrap">
                {visit.date}
              </td>
              <td className="py-3 pr-4 font-sans text-[14px] text-text-secondary">
                {visit.keyVisitor}
              </td>
              <td className="py-3 pr-4 font-sans text-[14px] text-text-secondary">
                {visit.mbzuaiHost}
              </td>
              <td className="py-3 pr-4 font-sans text-[13px] text-text-secondary">
                {visit.purpose}
              </td>
              <td className="py-3 pr-4 font-sans text-[13px] text-text-secondary">
                {visit.outcome}
              </td>
              <td className="py-3">
                <FollowUpBadge status={visit.followUpStatus} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
