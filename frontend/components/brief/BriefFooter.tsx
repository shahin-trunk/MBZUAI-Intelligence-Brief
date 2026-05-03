import type { Brief } from "@/lib/types/brief";

interface BriefFooterProps {
  brief: Brief;
}

/**
 * Format an ISO timestamp to GST (UTC+4) date-time string.
 */
function formatGeneratedAt(iso: string): string {
  const date = new Date(iso);
  return (
    date.toLocaleString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Dubai",
    }) + " GST"
  );
}

export default function BriefFooter({ brief }: BriefFooterProps) {
  return (
    <footer className="mt-16">
      {/* Double horizontal rules */}
      <div className="space-y-1">
        <div className="h-px bg-border-accent" />
        <div className="h-px bg-border-primary" />
      </div>

      <div className="pt-8 pb-12 text-center space-y-4">
        {/* END OF BRIEF */}
        <p className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
          End of Brief
        </p>

        {/* Attribution */}
        <div className="space-y-1">
          <p className="font-sans text-[14px] text-text-muted">
            Prepared by the MBZUAI Intelligence Office
          </p>
          <p className="font-sans text-[14px] text-text-secondary">
            Mohamed bin Zayed University of Artificial Intelligence
          </p>
        </div>

        {/* Stats line */}
        <p className="font-mono text-[14px] text-text-muted">
          Generated {formatGeneratedAt(brief.generated_at)}
        </p>

        <p className="font-mono text-[13px] text-text-muted">
          {brief.item_count} items selected
          {brief.items_reviewed > 0 &&
            ` from ${brief.items_reviewed} reviewed`}
          {brief.sources_consulted > 0 &&
            ` across ${brief.sources_consulted} sources`}
        </p>

        {/* Diamond ornament */}
        <div className="flex justify-center pt-2">
          <span className="text-text-muted/40 text-sm">&#x25C6;</span>
        </div>
      </div>
    </footer>
  );
}
