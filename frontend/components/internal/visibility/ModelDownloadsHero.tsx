"use client";

import type { EvidenceMetric } from "@/lib/types/internal-intelligence";

interface ResearchImpact {
  totalCitations: number;
  topPaperCitations: number;
  userTypes: string[];
  topRegions: string[];
  target2026: string;
}

interface ModelDownloadsHeroProps {
  metrics: EvidenceMetric[];
  modelComparison?: string;
  researchImpact?: ResearchImpact;
}

function formatHeroValue(value: number | string, format?: string): string {
  if (format === "text" || typeof value === "string") return String(value);
  return Number(value).toLocaleString("en-US");
}

export function ModelDownloadsHero({ metrics, modelComparison, researchImpact }: ModelDownloadsHeroProps) {
  return (
    <div className="space-y-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
        Institute of Foundation Models
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-[14px]">
        {metrics.map((metric) => (
          <div
            key={metric.id}
            className="bg-bg-tertiary rounded-sm border border-border-primary px-5 py-5"
          >
            {/* Label */}
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              {metric.label}
            </p>

            {/* Big number */}
            <p className="mt-2 font-mono text-3xl font-bold text-text-bright leading-none">
              {formatHeroValue(metric.value, metric.format)}
            </p>

            {/* Trend */}
            {metric.trendLabel && (
              <p className="mt-2 font-mono text-[14px] text-accent-success">
                {metric.trendLabel}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Model Comparison Callout */}
      {modelComparison && (
        <div className="bg-sig-high/10 border border-sig-high/30 rounded-sm px-4 py-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-1">
            Model Comparison
          </p>
          <p className="font-sans text-sm text-text-secondary leading-relaxed">
            {modelComparison}
          </p>
        </div>
      )}

      {/* Research Impact */}
      {researchImpact && (
        <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4 space-y-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
            Research Impact
          </p>

          <div className="grid grid-cols-2 gap-[14px]">
            <div>
              <p className="font-mono text-[12px] text-text-muted uppercase">Total Citations</p>
              <p className="font-mono text-xl font-bold text-text-bright">{researchImpact.totalCitations.toLocaleString()}</p>
            </div>
            <div>
              <p className="font-mono text-[12px] text-text-muted uppercase">Top Paper Citations</p>
              <p className="font-mono text-xl font-bold text-text-bright">{researchImpact.topPaperCitations.toLocaleString()}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-[14px]">
            <div>
              <p className="font-mono text-[12px] text-text-muted uppercase mb-1">User Types</p>
              <div className="space-y-0.5">
                {researchImpact.userTypes.map((t) => (
                  <p key={t} className="font-mono text-[13px] text-text-secondary">{t}</p>
                ))}
              </div>
            </div>
            <div>
              <p className="font-mono text-[12px] text-text-muted uppercase mb-1">Top Regions</p>
              <div className="space-y-0.5">
                {researchImpact.topRegions.map((r) => (
                  <p key={r} className="font-mono text-[13px] text-text-secondary">{r}</p>
                ))}
              </div>
            </div>
          </div>

          <div className="border-t border-border-primary pt-3">
            <p className="font-mono text-[12px] text-text-muted uppercase mb-1">2026 Target</p>
            <p className="font-mono text-[14px] text-text-secondary">{researchImpact.target2026}</p>
          </div>
        </div>
      )}
    </div>
  );
}
