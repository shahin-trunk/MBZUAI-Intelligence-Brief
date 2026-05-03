const SUBSECTIONS = [
  "Headline",
  "Current State",
  "What Changed",
  "What's Notable",
  "What's Ahead",
] as const;

export function AssessmentSection() {
  return (
    <div>
      {/* Section header — matches BriefSection horizontal-rule pattern */}
      <div className="flex items-center gap-3 mb-4">
        <div className="h-px w-4 bg-border-accent" />
        <h2 className="font-sans text-[16px] font-semibold uppercase tracking-[0.08em] text-text-primary shrink-0">
          Assessment
        </h2>
        <div className="h-px flex-1 bg-border-primary" />
      </div>

      <div className="space-y-4">
        {SUBSECTIONS.map((label) => (
          <div key={label} className="rounded-sm bg-bg-secondary px-7 py-[22px]">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
              {label}
            </h3>
            <p className="font-sans text-sm text-text-muted italic">
              Assessment content will appear here once lens data is available.
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
