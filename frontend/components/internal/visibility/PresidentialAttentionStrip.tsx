import type { PresidentialAttentionIndicator } from "@/lib/types/internal-intelligence";

interface PresidentialAttentionStripProps {
  indicators: PresidentialAttentionIndicator[];
}

export function PresidentialAttentionStrip({ indicators }: PresidentialAttentionStripProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-[14px]">
      {indicators.map((ind) => (
        <div
          key={ind.label}
          className="bg-bg-tertiary rounded-sm border border-border-primary px-4 py-3"
        >
          <p className="font-mono text-xl font-bold text-text-bright">
            {ind.value}
          </p>
          <p className="mt-1 font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
            {ind.label}
          </p>
        </div>
      ))}
    </div>
  );
}
