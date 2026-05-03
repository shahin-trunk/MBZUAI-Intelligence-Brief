"use client";

import { ChevronDown, Moon, Sun } from "lucide-react";
import { formatBriefDate } from "@/lib/utils";

interface BriefHeaderProps {
  briefDate: string;
  itemCount: number;
  sourcesConsulted: number;
  flagCount: number;
  executiveSummary?: string;
  onDateTap: () => void;
  onFlagBadgeTap: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
}

export default function BriefHeader({
  briefDate,
  itemCount,
  sourcesConsulted,
  flagCount,
  executiveSummary,
  onDateTap,
  onFlagBadgeTap,
  theme,
  onToggleTheme,
}: BriefHeaderProps) {
  const year = new Date(briefDate + "T00:00:00").getFullYear();

  return (
    <div>
      {/* Top row: date line + flag badge */}
      <div className="flex items-start justify-between">
        <button
          onClick={onDateTap}
          className="flex min-h-[44px] items-center gap-1.5 font-mono text-[12px] tracking-[0.04em] text-text-muted"
        >
          {formatBriefDate(briefDate)}, {year}
          <ChevronDown className="h-3 w-3 shrink-0 text-accent" strokeWidth={2.5} aria-hidden />
        </button>
        <div className="flex items-center gap-2">
          {onToggleTheme && (
            <button
              onClick={onToggleTheme}
              className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-[2px] text-text-muted transition-colors hover:text-text-primary"
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? (
                <Sun className="h-4 w-4" strokeWidth={2} aria-hidden />
              ) : (
                <Moon className="h-4 w-4" strokeWidth={2} aria-hidden />
              )}
            </button>
          )}
          {flagCount > 0 && (
            <button
              onClick={onFlagBadgeTap}
              className="flex items-center gap-1 rounded-[2px] bg-accent/10 px-2 py-1"
            >
              <span className="text-xs text-accent">⚑</span>
              <span className="font-mono text-[10px] font-medium text-accent">
                {flagCount}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Title */}
      <h1 className="mt-1.5 font-display text-[28px] font-normal leading-[1.15] tracking-[-0.01em] text-text-primary">
        President&apos;s Daily Brief
      </h1>

      {/* Stats */}
      <p className="mt-2 font-mono text-[12px] text-text-muted">
        {itemCount} items
        {sourcesConsulted > 0 && (
          <>
            <span className="opacity-50"> · </span>
            {sourcesConsulted} sources
          </>
        )}
        <span className="opacity-50"> · </span>
        08:00 GST
      </p>

      {/* Executive summary */}
      {executiveSummary && (
        <p className="mt-4 font-body text-[15px] leading-[1.6] text-text-secondary">
          {executiveSummary}
        </p>
      )}
    </div>
  );
}
