import { MetricCard } from "@/components/internal/shared/MetricCard";
import { SectionHeader } from "@/components/internal/shared/SectionHeader";
import { Tier1ByVenueChart } from "./Tier1ByVenueChart";
import { PublicationsByDivision } from "./PublicationsByDivision";
import { PublicationTrend } from "./PublicationTrend";
import { FlagshipPublicationCards } from "./FlagshipPublicationCards";
import type {
  EvidenceMetric,
  Tier1VenueCount,
  DivisionPublications,
  MonthlyPublicationTrend,
  FlagshipPublication,
} from "@/lib/types/internal-intelligence";

interface PublicationsSectionProps {
  metrics: EvidenceMetric[];
  tier1ByVenue: Tier1VenueCount[];
  tier1Definition: string;
  byDivision: DivisionPublications[];
  monthlyTrend: MonthlyPublicationTrend[];
  flagshipPublications: FlagshipPublication[];
}

export function PublicationsSection({
  metrics,
  tier1ByVenue,
  tier1Definition,
  byDivision,
  monthlyTrend,
  flagshipPublications,
}: PublicationsSectionProps) {
  return (
    <div className="space-y-6">
      {/* Headline metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {metrics.map((metric) => (
          <MetricCard key={metric.id} metric={metric} />
        ))}
      </div>

      {/* Hero: Quarterly trend */}
      <PublicationTrend data={monthlyTrend} />

      {/* Supporting detail */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] gap-4 items-start">
        <Tier1ByVenueChart data={tier1ByVenue} tier1Definition={tier1Definition} />
        <PublicationsByDivision data={byDivision} />
      </div>

      {/* Notable publications */}
      <div>
        <SectionHeader title="Notable Publications This Month" />
        <FlagshipPublicationCards publications={flagshipPublications} />
      </div>
    </div>
  );
}
