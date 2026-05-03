import type { ReactNode } from "react";
import type { WhatsNextItem } from "@/lib/types/internal-intelligence";

interface AssessmentBlockProps {
  assessment: {
    headline: string;
    whereWeStand: string[];
    whatsNext: (string | WhatsNextItem)[];
  };
}

/** Parse **bold** markers into <strong> elements. */
function renderInlineBold(text: string): ReactNode {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  if (parts.length === 1) return text;
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-semibold text-text-bright">
        {part}
      </strong>
    ) : (
      part
    )
  );
}

/** Check if a whatsNext entry is a structured object. */
function isStructuredItem(item: string | WhatsNextItem): item is WhatsNextItem {
  return typeof item === "object" && "text" in item;
}

/** Parse inline "**Deadline: ... · Owner: ...**" from a legacy string. */
function parseInlineMetadata(text: string): { text: string; deadline?: string; owner?: string } {
  const metaMatch = text.match(/\*\*(?:Deadline:\s*([^·*]+?))?(?:\s*·\s*)?(?:Owner:\s*([^*]+?))?\*\*\s*$/);
  if (!metaMatch) return { text };
  const cleaned = text.slice(0, metaMatch.index).trim();
  const deadline = metaMatch[1]?.trim() || undefined;
  const owner = metaMatch[2]?.trim() || undefined;
  return { text: cleaned, deadline, owner };
}

function WhatsNextBullet({ item }: { item: string | WhatsNextItem }) {
  let text: string;
  let deadline: string | undefined;
  let owner: string | undefined;

  if (isStructuredItem(item)) {
    text = item.text;
    deadline = item.deadline;
    owner = item.owner;
  } else {
    const parsed = parseInlineMetadata(item);
    text = parsed.text;
    deadline = parsed.deadline;
    owner = parsed.owner;
  }

  const hasMetadata = deadline || owner;

  return (
    <li className="font-sans text-sm leading-[1.7] text-text-primary marker:text-text-muted">
      <span>{renderInlineBold(text)}</span>
      {hasMetadata && (
        <div className="mt-1 font-mono text-xs text-text-muted flex items-center gap-0">
          {deadline && (
            <span>
              <span className="text-text-muted">Deadline: </span>
              <span className="text-amber-400">{deadline}</span>
            </span>
          )}
          {deadline && owner && (
            <span className="mx-1.5 text-text-muted">·</span>
          )}
          {owner && (
            <span className="text-gray-400">{owner}</span>
          )}
        </div>
      )}
    </li>
  );
}

export function AssessmentBlock({ assessment }: AssessmentBlockProps) {
  return (
    <div className="space-y-5">
      {/* Headline */}
      <p className="font-serif text-base font-semibold leading-[1.6] text-sig-high">
        {assessment.headline}
      </p>

      {/* Body sections — card grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {/* Where We Stand */}
        <div className="rounded-sm border border-border-primary bg-bg-secondary px-7 py-[22px]">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Where We Stand
          </h3>
          <ul className="space-y-1.5 list-disc list-outside pl-4">
            {assessment.whereWeStand.map((bullet, i) => (
              <li
                key={i}
                className="font-sans text-sm leading-[1.7] text-text-primary marker:text-text-muted"
              >
                {renderInlineBold(bullet)}
              </li>
            ))}
          </ul>
        </div>

        {/* What's Next */}
        <div className="rounded-sm border border-border-primary bg-bg-secondary px-7 py-[22px]">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            What&rsquo;s Next
          </h3>
          <ul className="space-y-2.5 list-disc list-outside pl-4">
            {assessment.whatsNext.map((item, i) => (
              <WhatsNextBullet key={i} item={item} />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
