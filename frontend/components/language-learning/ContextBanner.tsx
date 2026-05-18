"use client";

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
    <div className="px-5 py-2">
      <div className="flex items-center gap-2.5">
        <div className="h-6 w-0.5 rounded-full bg-indigo-500/30" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-ui text-[10px] font-medium uppercase tracking-[0.15em] text-gray-500">
              From this briefing
            </span>
            {category && (
              <>
                <span className="text-gray-600/50">/</span>
                <span className="font-ui text-[10px] text-gray-500">
                  {category}
                </span>
              </>
            )}
          </div>
          <p className="font-body text-[12px] leading-snug text-gray-400 line-clamp-1 mt-0.5">
            {headline}
          </p>
        </div>
      </div>
    </div>
  );
}
