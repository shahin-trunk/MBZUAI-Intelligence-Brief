"use client";

import { ArrowUpRight, Eye } from "lucide-react";

interface ContextBannerProps {
  headline: string;
  briefDate: string;
  slideIndex: number;
  category?: string;
  onViewSlide?: () => void;
}

export default function ContextBanner({
  headline,
  briefDate,
  slideIndex,
  category,
  onViewSlide,
}: ContextBannerProps) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-bg-surface to-bg-surface/50 border border-rule/30 px-4 py-3">
      {/* Subtle background pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,_hsl(var(--accent-primary)),_transparent_70%)]" />
      </div>

      <div className="relative flex items-start gap-3">
        {/* Icon */}
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-primary/10">
          <Eye className="h-4 w-4 text-accent-primary/70" />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {/* Breadcrumb */}
          <div className="flex items-center gap-1.5 mb-1">
            <span className="font-ui text-[10px] font-medium uppercase tracking-wider text-text-muted">
              From briefing
            </span>
            {category && (
              <>
                <span className="text-text-muted/40">•</span>
                <span className="font-ui text-[10px] font-medium text-accent-primary/70">
                  {category}
                </span>
              </>
            )}
          </div>

          {/* Headline */}
          <p className="font-body text-[12px] sm:text-[13px] leading-snug text-text-secondary line-clamp-2 mb-1.5">
            {headline}
          </p>

          {/* Action link */}
          {onViewSlide ? (
            <button
              onClick={onViewSlide}
              className="inline-flex items-center gap-1 font-ui text-[11px] font-medium text-accent-primary/80 hover:text-accent-primary transition-colors group"
            >
              <span>View original slide</span>
              <ArrowUpRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </button>
          ) : (
            <a
              href={`/brief/${briefDate}?slideIndex=${slideIndex}`}
              className="inline-flex items-center gap-1 font-ui text-[11px] font-medium text-accent-primary/80 hover:text-accent-primary transition-colors group"
            >
              <span>View original slide</span>
              <ArrowUpRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
