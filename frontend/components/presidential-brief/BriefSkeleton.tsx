export function BriefSkeleton() {
  return (
    <div className="mx-auto max-w-lg animate-pulse px-5 py-6">
      {/* Header skeleton */}
      <div className="relative">
        {/* App title */}
        <div className="h-2.5 w-40 rounded bg-bg-surface-2" />
        {/* Date */}
        <div className="mt-2.5 h-6 w-56 rounded bg-bg-surface-2" />
        {/* Subtext */}
        <div className="mt-1.5 h-2.5 w-44 rounded bg-bg-surface-2" />
      </div>

      {/* Audio player skeleton */}
      <div className="mt-5 h-16 w-full rounded-[4px] bg-bg-surface-2" />

      {/* Section skeletons */}
      {[0, 1, 2].map((sectionIdx) => (
        <div key={sectionIdx} className="mt-7">
          {/* Section label */}
          <div className="mb-3 h-2.5 w-28 rounded bg-bg-surface-2" />

          {/* Items */}
          {[0, 1, sectionIdx === 0 ? 2 : -1].filter((n) => n >= 0).map((itemIdx) => (
            <div key={itemIdx} className="border-b border-border-divider py-3.5">
              {/* Headline line 1 */}
              <div
                className="h-3.5 rounded bg-bg-surface-2"
                style={{ width: itemIdx === 0 ? "90%" : itemIdx === 1 ? "75%" : "82%" }}
              />
              {/* Headline line 2 (some items) */}
              {itemIdx === 0 && (
                <div className="mt-1.5 h-3.5 w-3/5 rounded bg-bg-surface-2" />
              )}
              {/* Metadata line */}
              <div className="mt-1.5 h-2.5 w-32 rounded bg-bg-surface-2 opacity-60" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
