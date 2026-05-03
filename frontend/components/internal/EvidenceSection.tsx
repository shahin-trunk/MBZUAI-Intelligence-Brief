export function EvidenceSection() {
  return (
    <div>
      {/* Section header — matches BriefSection horizontal-rule pattern */}
      <div className="flex items-center gap-3 mb-4">
        <div className="h-px w-4 bg-border-accent" />
        <h2 className="font-sans text-[16px] font-semibold uppercase tracking-[0.08em] text-text-primary shrink-0">
          Supporting Evidence
        </h2>
        <div className="h-px flex-1 bg-border-primary" />
      </div>

      <div className="rounded-sm border border-border-primary bg-bg-secondary px-5 py-6">
        <p className="font-sans text-sm text-text-muted italic">
          Data visualizations and metrics will appear here.
        </p>
      </div>
    </div>
  );
}
