"use client";

import type { BriefItem } from "@/lib/types/brief";
import { renderAnalysisBlock, renderMarkdown } from "@/lib/rendering/markdown";
import { ExhibitRenderer } from "./ExhibitRenderer";

interface CardExpandedProps {
  item: BriefItem;
  onClose: () => void;
  onResearch?: () => void;
}

export function CardExpanded({ item, onClose, onResearch }: CardExpandedProps) {
  // v2: use analysis. v1 fallback: combine context + implication
  const analysisText = item.analysis
    ?? [item.context, item.implication].filter(Boolean).join(" ");

  const bullets = item.key_bullets?.length
    ? item.key_bullets
    : item.main_bullet
      ? [item.main_bullet]
      : [];

  return (
    <div className="fixed inset-0 z-[80] bg-surface-primary overflow-y-auto">
      <div className="max-w-lg mx-auto px-6 py-8 min-h-screen">
        {/* Close button */}
        <button
          onClick={onClose}
          className="fixed top-4 right-4 z-[90] w-10 h-10 rounded-full bg-surface-secondary border border-border-secondary flex items-center justify-center text-text-muted hover:text-text-primary"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>

        {/* Headline */}
        <h1
          className="text-2xl leading-tight font-semibold text-text-primary mb-6 pr-12"
          style={{ fontFamily: "var(--font-heading, 'Playfair Display', serif)" }}
        >
          {item.headline}
        </h1>

        {/* Key bullets */}
        <div className="space-y-2 mb-6">
          {bullets.map((bullet, i) => (
            <div key={i} className="flex gap-2.5 items-start">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-primary shrink-0 mt-1.5" />
              <p className="text-sm text-text-muted leading-relaxed">
                {renderMarkdown(bullet)}
              </p>
            </div>
          ))}
        </div>

        {/* Analysis — paragraph (legacy) or bulleted list (v4+) */}
        {analysisText && (
          <div className="mb-6 text-sm leading-relaxed text-text-primary">
            {renderAnalysisBlock(analysisText)}
          </div>
        )}

        {/* Exhibits */}
        {item.exhibits?.map((ex, i) => (
          <ExhibitRenderer key={i} exhibit={ex} />
        ))}

        {/* Source link */}
        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-accent-primary hover:underline mt-6"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M5 1H2a1 1 0 00-1 1v8a1 1 0 001 1h8a1 1 0 001-1V7M7 1h4v4M11 1L5.5 6.5" />
            </svg>
            {item.source_name}
          </a>
        )}

        {/* Research request */}
        {onResearch && (
          <button
            onClick={onResearch}
            className="mt-6 w-full py-2.5 rounded-lg border border-border-secondary text-sm text-text-muted hover:text-text-primary hover:border-accent-primary/30 transition-colors"
          >
            Request Research
          </button>
        )}
      </div>
    </div>
  );
}
