import Link from "next/link";
import type { Engagement } from "@/lib/types/executive-engagement";

interface Props {
  engagement: Engagement;
}

function formatDayNumber(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").getDate().toString();
}

function formatDayAbbrev(dateStr: string): string {
  return new Date(dateStr + "T00:00:00")
    .toLocaleDateString("en-US", { weekday: "short" })
    .toUpperCase();
}

export function CompactEngagementRow({ engagement }: Props) {
  return (
    <Link
      href={`/executive-engagement/${engagement.id}`}
      className="w-full flex items-center gap-4 rounded-[10px] border px-5 py-[14px] text-left transition-colors"
      style={{
        background: "var(--bg-secondary)",
        borderColor: "var(--border-primary)",
      }}
    >
      {/* Date block */}
      <div className="flex flex-col items-center justify-center shrink-0" style={{ minWidth: 36 }}>
        <span className="text-[14px] font-medium text-text-secondary leading-none">
          {formatDayNumber(engagement.date)}
        </span>
        <span className="text-[11px] text-text-dim mt-0.5">
          {formatDayAbbrev(engagement.date)}
        </span>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-medium text-text-bright truncate">
          {engagement.visitor_name}
        </p>
        <p className="text-[12px] text-text-dim truncate">
          {engagement.visitor_title}
          {engagement.visitor_organization &&
            ` · ${engagement.visitor_organization}`}
          {" · "}
          {engagement.format}
          {engagement.time && ` · ${engagement.time}`}
        </p>
      </div>

      {/* Chevron — always right-pointing (navigation) */}
      <svg
        width="14"
        height="14"
        viewBox="0 0 16 16"
        fill="none"
        stroke="var(--text-dim)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="shrink-0"
      >
        <path d="M6 4l4 4-4 4" />
      </svg>
    </Link>
  );
}
