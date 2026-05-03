import type { Brief } from "@/lib/types/brief";
import AudioPlayer from "@/components/brief/AudioPlayer";
import { AudioStatusBanner } from "@/components/brief/AudioStatusBanner";

interface BriefHeaderProps {
  brief: Brief;
  audioUrl?: string;
  audioScript?: string;
  audioUrlFr?: string;
  audioScriptFr?: string;
  audioStatus?: string;
}

/**
 * Format an ISO timestamp into GST (UTC+4) time, e.g. "08:59 GST".
 */
function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return (
    date.toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Dubai",
    }) + " GST"
  );
}

export default function BriefHeader({
  brief,
  audioUrl,
  audioScript,
  audioUrlFr,
  audioScriptFr,
  audioStatus,
}: BriefHeaderProps) {
  return (
    <header>
      {/* Title */}
      <h1 className="font-serif text-[28px] text-text-bright">
        President&apos;s Daily Brief
      </h1>

      {/* Stats row */}
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-mono text-[14px] text-text-muted">
          {brief.item_count} items
        </span>
        {brief.sources_consulted > 0 && (
          <>
            <span className="font-mono text-[14px] text-text-muted">
              &middot;
            </span>
            <span className="font-mono text-[14px] text-text-muted">
              {brief.sources_consulted} sources
            </span>
          </>
        )}
        <span className="font-mono text-[14px] text-text-muted">&middot;</span>
        <span className="font-mono text-[14px] text-text-muted">
          {formatTimestamp(brief.generated_at)}
        </span>
      </div>

      {/* Executive summary */}
      {brief.executive_summary && (
        <p className="mt-4 font-sans text-sm text-text-secondary leading-relaxed max-w-2xl">
          {brief.executive_summary}
        </p>
      )}

      {/* Audio: show status banner while generating, player when ready */}
      {!audioUrl && audioStatus && audioStatus !== "ready" && (
        <AudioStatusBanner
          initialStatus={audioStatus}
          briefDate={brief.brief_date}
        />
      )}
      {audioUrl && (
        <AudioPlayer
          audioUrl={audioUrl}
          audioScript={audioScript}
          audioUrlFr={audioUrlFr}
          audioScriptFr={audioScriptFr}
        />
      )}
    </header>
  );
}
