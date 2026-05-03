import Link from "next/link";
import { Bookmark, LayoutGrid, Clock } from "lucide-react";

interface BriefTopBarProps {
  prevDate?: string | null;
  nextDate?: string | null;
  briefDate: string;
  isAdmin: boolean;
}

function formatBriefDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatShortDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

export default function BriefTopBar({
  prevDate,
  briefDate,
  isAdmin,
}: BriefTopBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 mb-6 sm:flex-nowrap sm:justify-between">
      {/* Date — full width on mobile, centered */}
      <p className="order-first w-full text-center font-sans text-[14px] text-text-secondary mb-1 sm:order-none sm:w-auto sm:flex-1 sm:mb-0">
        {formatBriefDate(briefDate)}
      </p>

      {/* Left — previous brief link */}
      {prevDate ? (
        <Link
          href={`/brief/${prevDate}`}
          className="inline-flex items-center gap-1 font-mono text-[14px] text-text-muted border border-border-primary rounded-[4px] px-2 py-1 hover:text-text-secondary transition-colors"
        >
          <span>&#x2039;</span>
          <span>{formatShortDate(prevDate)}</span>
        </Link>
      ) : (
        <span className="w-16" />
      )}

      {/* Right — utility links (icons only on mobile) */}
      <nav className="flex items-center gap-3 ml-auto sm:gap-4">
        <Link
          href="/flagged"
          className="inline-flex items-center gap-1.5 font-sans text-[14px] text-text-muted hover:text-text-secondary transition-colors"
          title="Flagged"
        >
          <Bookmark className="h-4 w-4 sm:h-3 sm:w-3 opacity-50" />
          <span className="hidden sm:inline">Flagged</span>
        </Link>
        <Link
          href="/brief"
          className="inline-flex items-center gap-1.5 font-sans text-[14px] text-text-muted hover:text-text-secondary transition-colors"
          title="All Briefs"
        >
          <LayoutGrid className="h-4 w-4 sm:h-3 sm:w-3 opacity-50" />
          <span className="hidden sm:inline">All Briefs</span>
        </Link>
        {isAdmin && (
          <Link
            href="/admin"
            className="inline-flex items-center gap-1.5 font-sans text-[14px] text-text-muted hover:text-text-secondary transition-colors"
            title="Admin"
          >
            <Clock className="h-4 w-4 sm:h-3 sm:w-3 opacity-50" />
            <span className="hidden sm:inline">Admin</span>
          </Link>
        )}
      </nav>
    </div>
  );
}
