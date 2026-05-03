import type { Metadata } from "next";
import Link from "next/link";
import { createServiceClient } from "@/lib/supabase/server";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Daily Briefs — Intelligence Dashboard",
  description: "Intelligence briefs",
};

interface BriefEntry {
  brief_date: string;
  item_count: number;
  generated_at: string;
  top_headlines: string[];
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatTime(isoStr: string): string {
  if (!isoStr) return "";
  const date = new Date(isoStr);
  return (
    date.toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Dubai",
    }) + " GST"
  );
}

export default async function BriefListingPage() {
  const supabase = createServiceClient();

  const { data, error } = await supabase
    .from("briefs")
    .select("brief_date, raw_json")
    .order("brief_date", { ascending: false })
    .limit(20);

  if (error) {
    console.error("Failed to fetch briefs:", error);
  }

  const entries: BriefEntry[] = (data ?? []).map((row) => {
    const raw = row.raw_json as Record<string, unknown> | null;
    const metadata = (raw?.brief_metadata ?? {}) as Record<string, unknown>;
    const items = (raw?.items ?? []) as Array<Record<string, unknown>>;

    const topHeadlines = items
      .filter((item) => !item.is_placeholder)
      .sort((a, b) => ((a.rank as number) ?? 999) - ((b.rank as number) ?? 999))
      .slice(0, 3)
      .map((item) => (item.headline as string) ?? "Untitled");

    return {
      brief_date: row.brief_date as string,
      item_count: (metadata.total_items as number) ?? 0,
      generated_at: (metadata.generated_at as string) ?? "",
      top_headlines: topHeadlines,
    };
  });

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-serif text-2xl text-text-bright">Daily Briefs</h1>
      <p className="mt-1 font-mono text-xs text-text-muted">
        {entries.length} recent brief{entries.length !== 1 ? "s" : ""}
      </p>

      {entries.length === 0 ? (
        <div className="mt-8 rounded-sm border border-border-primary bg-bg-secondary p-8 text-center">
          <p className="text-text-secondary text-sm">
            No briefs available yet.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-3">
          {entries.map((entry) => (
            <Link
              key={entry.brief_date}
              href={`/brief/${entry.brief_date}`}
              className="block rounded-sm border border-border-primary bg-bg-secondary p-4 transition-colors hover:bg-bg-tertiary"
            >
              <div className="flex items-baseline justify-between">
                <span className="font-serif text-sm text-text-bright">
                  {formatDate(entry.brief_date)}
                </span>
                <span className="font-mono text-[10px] text-text-muted">
                  {entry.item_count} items
                  {entry.generated_at
                    ? ` \u00B7 ${formatTime(entry.generated_at)}`
                    : ""}
                </span>
              </div>

              {entry.top_headlines.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {entry.top_headlines.map((headline, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 font-serif text-xs text-text-secondary"
                    >
                      <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-text-muted/40" />
                      <span className="line-clamp-1">{headline}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Link>
          ))}
        </div>
      )}

      <div className="mt-8">
        <Link
          href="/history"
          className="font-mono text-[12px] text-accent-primary hover:text-accent-primary/80 transition-colors"
        >
          View full archive &rarr;
        </Link>
      </div>
    </div>
  );
}
