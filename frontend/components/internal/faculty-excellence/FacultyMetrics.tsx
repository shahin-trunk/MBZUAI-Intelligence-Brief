import { MetricCard } from "@/components/internal/shared/MetricCard";
import type { EvidenceMetric } from "@/lib/types/internal-intelligence";

interface FacultyMetricsProps {
  metrics: EvidenceMetric[];
}

export function FacultyMetrics({ metrics }: FacultyMetricsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-[14px]">
      {metrics.map((metric) => (
        <MetricCard key={metric.id} metric={metric} />
      ))}
    </div>
  );
}
