import { MetricCard } from "@/components/internal/shared/MetricCard";
import type { EvidenceMetric } from "@/lib/types/internal-intelligence";

interface OutreachMetricsProps {
  metrics: EvidenceMetric[];
}

export function OutreachMetrics({ metrics }: OutreachMetricsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-[14px]">
      {metrics.map((metric) => (
        <MetricCard key={metric.id} metric={metric} />
      ))}
    </div>
  );
}
