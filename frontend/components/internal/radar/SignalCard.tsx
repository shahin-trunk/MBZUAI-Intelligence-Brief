import Link from "next/link";
import type { RadarSignalCard as RadarSignalCardType } from "@/lib/types/internal-intelligence";
import { MeetingContextTags } from "./MeetingContextTags";

interface SignalCardProps {
  card: RadarSignalCardType;
}

const SEVERITY_COLORS: Record<string, string> = {
  high: "bg-accent-danger",
  medium: "bg-accent-warning",
};

export function SignalCard({ card }: SignalCardProps) {
  const formattedDate = new Date(card.date + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
  const lensHref = `/${card.sourceLens}`;

  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary px-7 py-[22px] space-y-3">
      {/* Top row: severity dot + NEW badge + date */}
      <div className="flex items-center gap-2">
        {card.severity && (
          <div
            className={`h-2 w-2 rounded-full shrink-0 ${SEVERITY_COLORS[card.severity]}`}
          />
        )}
        {card.isNew && (
          <span className="inline-flex items-center rounded-full bg-accent-primary/20 text-accent-primary border border-accent-primary/40 px-1.5 py-0 font-mono text-[11px] font-bold uppercase tracking-wider">
            New
          </span>
        )}
        <span className="ml-auto font-mono text-[12px] text-text-muted">
          {formattedDate}
        </span>
      </div>

      {/* Title */}
      <h3 className="font-sans text-[16px] font-semibold text-text-bright leading-[1.45]">
        {card.title}
      </h3>

      {/* Summary */}
      <p className="font-sans text-sm text-text-secondary leading-relaxed">
        {card.summary}
      </p>

      {/* Meeting context tags (wins only) */}
      {card.tags && card.tags.length > 0 && (
        <MeetingContextTags tags={card.tags} />
      )}

      {/* Footer: source lens badge + link */}
      <div className="flex items-center justify-between pt-1 border-t border-border-primary">
        <Link
          href={lensHref}
          className="font-mono text-[12px] text-text-muted bg-bg-tertiary border border-border-primary rounded-sm px-2 py-0.5 hover:text-text-primary hover:border-border-accent transition-colors"
        >
          {card.sourceLensName}
        </Link>
        <Link
          href={lensHref}
          className="font-mono text-[13px] text-accent-primary hover:text-accent-primary/80 transition-colors"
        >
          View in {card.sourceLensName} &rarr;
        </Link>
      </div>
    </div>
  );
}
