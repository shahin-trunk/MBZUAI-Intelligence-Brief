import type { Metadata } from "next";
import { createServiceClient } from "@/lib/supabase/server";
import { Header } from "@/components/layout/Header";
import { HistoryCalendar } from "@/components/history/HistoryCalendar";

export const metadata: Metadata = {
  title: "Brief Archive — Intelligence Dashboard",
  description: "Browse past intelligence briefs by date",
};

export const revalidate = 3600;

interface BriefDateEntry {
  brief_date: string;
  item_count: number;
  generated_at: string;
  top_headlines: string[];
}

export default async function HistoryPage() {
  const supabase = createServiceClient();

  const { data, error } = await supabase
    .from("briefs")
    .select("brief_date, raw_json")
    .order("brief_date", { ascending: false });

  if (error) {
    console.error("Failed to fetch briefs for history:", error);
  }

  const entries: BriefDateEntry[] = (data ?? []).map((row) => {
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
    <>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="font-serif text-2xl text-text-bright">Brief Archive</h1>
        <p className="mt-1 font-mono text-xs text-text-muted">
          {entries.length} brief{entries.length !== 1 ? "s" : ""} available
        </p>
        <div className="mt-6">
          <HistoryCalendar entries={entries} />
        </div>
      </main>
    </>
  );
}
