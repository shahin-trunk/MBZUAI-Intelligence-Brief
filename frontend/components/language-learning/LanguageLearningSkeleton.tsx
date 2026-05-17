"use client";

export default function LanguageLearningSkeleton() {
  return (
    <div className="min-h-[100dvh] flex flex-col bg-bg-primary" aria-label="Loading learning content" aria-busy="true">
      {/* Top progress bar skeleton */}
      <div className="fixed top-0 left-0 right-0 z-50">
        <div className="h-[3px] bg-rule/20">
          <div className="h-full bg-accent-primary/30 w-1/3 animate-pulse" />
        </div>
      </div>

      {/* Header skeleton */}
      <div className="pt-8 px-6 sm:px-10 lg:px-0 max-w-[620px] mx-auto w-full">
        <div className="flex items-center justify-between mb-4">
          <div className="h-8 w-24 bg-rule/20 rounded animate-pulse" />
          <div className="h-8 w-16 bg-rule/20 rounded-full animate-pulse" />
        </div>
        <div className="h-6 w-48 bg-rule/20 rounded animate-pulse mb-2" />
        <div className="h-4 w-32 bg-rule/10 rounded animate-pulse" />
      </div>

      {/* Navigation dots skeleton */}
      <div className="flex justify-center py-4">
        <div className="flex items-center gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-3 w-3 rounded-full bg-rule/20 animate-pulse"
              style={{ animationDelay: `${i * 100}ms` }}
            />
          ))}
        </div>
      </div>

      {/* Content skeleton */}
      <div className="flex-1 flex flex-col items-center justify-start px-6 sm:px-10 lg:px-0 py-6 max-w-[560px] mx-auto w-full">
        {/* Context badge skeleton */}
        <div className="mb-6 flex flex-col items-center gap-2">
          <div className="h-6 w-32 bg-rule/20 rounded-full animate-pulse" />
          <div className="h-4 w-48 bg-rule/10 rounded animate-pulse" />
        </div>

        {/* Main phrase skeleton */}
        <div className="w-full mb-8">
          <div className="h-12 w-full bg-rule/20 rounded-lg animate-pulse mb-4" />
          <div className="h-12 w-3/4 bg-rule/20 rounded-lg animate-pulse" />
        </div>

        {/* Translation skeleton */}
        <div className="flex items-center gap-3 mb-4">
          <div className="h-px w-8 bg-rule/40" />
          <div className="h-4 w-24 bg-rule/20 rounded animate-pulse" />
          <div className="h-px w-8 bg-rule/40" />
        </div>

        {/* Pronunciation skeleton */}
        <div className="h-10 w-48 bg-rule/20 rounded-lg animate-pulse mb-4" />

        {/* Grammar button skeleton */}
        <div className="h-10 w-56 bg-rule/20 rounded-full animate-pulse" />
      </div>
    </div>
  );
}
