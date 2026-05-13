import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { createServiceClient } from "@/lib/supabase/server";
import { transformBrief } from "@/lib/transforms/brief";
import type { Brief, BriefItem, RawPipelineBrief } from "@/lib/types/brief";
import LanguageLearningView from "@/components/language-learning/LanguageLearningView";

export const dynamic = "force-dynamic";

interface LearnPageProps {
  params: Promise<{ date: string; itemId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({
  params,
}: LearnPageProps): Promise<Metadata> {
  const { date } = await params;
  return {
    title: `Language Learning — ${date}`,
  };
}

export default async function LearnPage({ params, searchParams }: LearnPageProps) {
  const { date, itemId } = await params;
  const sp = await searchParams;
  const slideIndex = typeof sp?.slideIndex === "string"
    ? parseInt(sp.slideIndex, 10)
    : 0;

  const supabase = createServiceClient();

  const { data, error } = await supabase
    .from("briefs")
    .select("raw_json, brief_date")
    .eq("brief_date", date)
    .single();

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-primary px-6">
        <div className="mx-auto max-w-md text-center">
          <h1 className="font-display text-2xl text-text-primary">
            Brief Not Available
          </h1>
          <p className="mt-3 text-text-secondary">
            The briefing for {date} could not be found.
          </p>
          <a
            href={`/brief/${date}`}
            className="mt-6 inline-block rounded-full border border-rule bg-bg-surface px-5 py-2.5 font-ui text-sm text-accent-primary hover:bg-bg-surface-2 transition-colors"
          >
            Go to briefing
          </a>
        </div>
      </div>
    );
  }

  const rawJson = data.raw_json as RawPipelineBrief;
  const brief = transformBrief(rawJson, {});

  const item = brief.items.find((i: BriefItem) => i.id === itemId);

  if (!item) {
    redirect(`/brief/${date}`);
  }

  if (!item.learning_fr && !item.learning_ar) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-primary px-6">
        <div className="mx-auto max-w-md text-center">
          <h1 className="font-display text-2xl text-text-primary">
            Learning Content Not Available
          </h1>
          <p className="mt-3 text-text-secondary">
            This slide doesn&apos;t have language learning content yet.
            Content is generated as part of the daily briefing pipeline.
          </p>
          <a
            href={`/brief/${date}?slideIndex=${slideIndex}`}
            className="mt-6 inline-block rounded-full border border-rule bg-bg-surface px-5 py-2.5 font-ui text-sm text-accent-primary hover:bg-bg-surface-2 transition-colors"
          >
            Back to briefing
          </a>
        </div>
      </div>
    );
  }

  return (
    <LanguageLearningView
      item={item}
      briefDate={date}
      slideIndex={slideIndex}
    />
  );
}
