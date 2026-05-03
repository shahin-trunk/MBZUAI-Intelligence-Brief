import type { Metadata } from "next";
import Link from "next/link";
import BriefViewRouter from "@/components/presidential-brief/BriefViewRouter";
import { createServiceClient } from "@/lib/supabase/server";
import { transformBrief } from "@/lib/transforms/brief";
import type { Brief, RawPipelineBrief } from "@/lib/types/brief";

// ISR: revalidate every hour
export const revalidate = 3600;

interface BriefPageProps {
  params: Promise<{ date: string }>;
}

export async function generateMetadata({
  params,
}: BriefPageProps): Promise<Metadata> {
  const { date } = await params;

  const displayDate =
    date === "today"
      ? "Today"
      : new Date(date + "T00:00:00").toLocaleDateString("en-US", {
          year: "numeric",
          month: "long",
          day: "numeric",
        });

  return {
    title: `Brief ${displayDate} — Intelligence Dashboard`,
    description: `Intelligence brief for ${displayDate}`,
  };
}

export async function generateStaticParams() {
  return [{ date: "today" }];
}

async function fetchBrief(date: string) {
  const supabase = createServiceClient();

  if (date === "today") {
    const { data, error } = await supabase
      .from("briefs")
      .select(
        "raw_json, brief_date, audio_url, audio_script, audio_url_fr, audio_script_fr, audio_status, generated_at, item_count, sources_consulted, items_reviewed, pipeline_cost_usd, executive_summary"
      )
      .order("brief_date", { ascending: false })
      .limit(1)
      .single();

    if (error || !data) {
      return null;
    }

    return data;
  }

  const { data, error } = await supabase
    .from("briefs")
    .select(
      "raw_json, brief_date, audio_url, audio_script, audio_url_fr, audio_script_fr, audio_status, generated_at, item_count, sources_consulted, items_reviewed, pipeline_cost_usd, executive_summary"
    )
    .eq("brief_date", date)
    .single();

  if (error || !data) {
    return null;
  }

  return data;
}

async function fetchBriefForDate(date: string): Promise<Brief | null> {
  const data = await fetchBrief(date);

  if (!data) {
    return null;
  }

  const rawJson = data.raw_json as RawPipelineBrief;
  const brief = transformBrief(rawJson, {
    generated_at: data.generated_at,
    item_count: data.item_count,
    sources_consulted: data.sources_consulted,
    items_reviewed: data.items_reviewed,
    pipeline_cost_usd: data.pipeline_cost_usd,
    executive_summary: data.executive_summary,
  });

  brief.audio_url = data.audio_url ?? undefined;
  brief.audio_script = data.audio_script ?? undefined;
  brief.audio_url_fr = data.audio_url_fr ?? undefined;
  brief.audio_script_fr = data.audio_script_fr ?? undefined;

  return brief;
}

async function fetchAdjacentDates(
  currentDate: string
): Promise<{ prevDate: string | null; nextDate: string | null }> {
  const supabase = createServiceClient();

  const [prevResult, nextResult] = await Promise.all([
    supabase
      .from("briefs")
      .select("brief_date")
      .lt("brief_date", currentDate)
      .order("brief_date", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("briefs")
      .select("brief_date")
      .gt("brief_date", currentDate)
      .order("brief_date", { ascending: true })
      .limit(1)
      .maybeSingle(),
  ]);

  return {
    prevDate: prevResult.data?.brief_date ?? null,
    nextDate: nextResult.data?.brief_date ?? null,
  };
}

async function fetchAvailableDates(limit: number = 90): Promise<string[]> {
  const supabase = createServiceClient();
  const { data, error } = await supabase
    .from("briefs")
    .select("brief_date")
    .order("brief_date", { ascending: false })
    .limit(limit);

  if (error || !data) {
    return [];
  }

  return data.map((row) => row.brief_date);
}

export default async function BriefPage({ params }: BriefPageProps) {
  const { date } = await params;
  const data = await fetchBrief(date);

  if (!data) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center">
        <div className="mx-auto max-w-md text-center">
          <h1 className="font-serif text-2xl text-text-primary">
            No Brief Available
          </h1>
          <p className="mt-3 text-text-secondary">
            {date === "today"
              ? "No briefs have been generated yet. Check back later."
              : `No brief was found for ${date}. It may not have been generated.`}
          </p>
          <Link
            href="/brief/today"
            className="mt-6 inline-block text-sm text-accent-primary hover:underline"
          >
            Go to latest brief
          </Link>
        </div>
      </div>
    );
  }

  const brief = await fetchBriefForDate(data.brief_date);
  const { prevDate, nextDate } = await fetchAdjacentDates(data.brief_date);
  const availableDates = await fetchAvailableDates();

  if (!brief) {
    return null;
  }

  return (
    <BriefViewRouter
      brief={brief}
      prevDate={prevDate}
      nextDate={nextDate}
      availableDates={availableDates}
    />
  );
}
