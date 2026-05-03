"use client";

import { MetricCard } from "@/components/internal/shared/MetricCard";
import type { EvidenceMetric } from "@/lib/types/internal-intelligence";

interface OutcomesMetricsProps {
  metrics: EvidenceMetric[];
}

export function OutcomesMetrics({ metrics }: OutcomesMetricsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-2 gap-[14px]">
      {metrics.map((metric) => (
        <MetricCard key={metric.id} metric={metric} />
      ))}
    </div>
  );
}
