import type { DelegationRegionalBreakdown } from "@/lib/types/internal-intelligence";

interface DelegationOverviewProps {
  ytdCount: number;
  regionalBreakdown?: DelegationRegionalBreakdown[];
}

export function DelegationOverview({
  ytdCount,
  regionalBreakdown,
}: DelegationOverviewProps) {
  return (
    <div className="space-y-6">
      {/* YTD count */}
      <p className="font-mono text-[13px] text-text-muted">
        {ytdCount} international delegations hosted year-to-date
      </p>

      {/* Regional Breakdown */}
      {regionalBreakdown && regionalBreakdown.length > 0 && (
        <div className="bg-bg-tertiary rounded-sm border border-border-primary overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border-primary">
                <th className="px-4 py-2 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium">
                  Region
                </th>
                <th className="px-4 py-2 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium text-right">
                  Delegations
                </th>
                <th className="px-4 py-2 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted font-medium text-right">
                  MOUs Signed
                </th>
              </tr>
            </thead>
            <tbody>
              {regionalBreakdown.map((r) => (
                <tr key={r.region} className="border-b border-border-primary last:border-b-0">
                  <td className="px-4 py-2 font-mono text-[14px] text-text-secondary">
                    {r.region}
                  </td>
                  <td className="px-4 py-2 font-mono text-[14px] text-text-bright font-medium text-right">
                    {r.count}
                  </td>
                  <td className="px-4 py-2 font-mono text-[14px] text-text-bright font-medium text-right">
                    {r.mousSigned}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
