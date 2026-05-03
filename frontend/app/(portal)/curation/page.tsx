import { createServiceClient } from "@/lib/supabase/server";
import { CurationWorkspace } from "@/components/curation/CurationWorkspace";
import {
  getCurationClient,
  getLatestAccessiblePendingBrief,
  loadCurationItems,
} from "@/lib/api/curation-helpers";
import { transformBrief } from "@/lib/transforms/brief";
import type { RawPipelineBrief, BriefItem } from "@/lib/types/brief";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function CurationPage() {
  let supabase = createServiceClient();
  let userId: string | null = null;

  try {
    const auth = await getCurationClient();
    supabase = auth.supabase;
    userId = auth.user.id;
  } catch {
    redirect("/");
  }

  // Phase 5 fix: check today's published state FIRST. If today's brief has
  // already been published, prefer showing the "today is done" state over
  // falling back to an older pending brief. Admins who genuinely need to
  // work on a past date navigate via /curation/history instead.
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Dubai" });
  let todayPublished = false;
  let publishedBriefDate: string | null = null;
  let publishedItems: BriefItem[] = [];

  const { data: publishedToday } = await supabase
    .from("pending_briefs")
    .select("id")
    .eq("status", "published")
    .eq("brief_date", today)
    .limit(1)
    .maybeSingle();
  todayPublished = !!publishedToday;

  if (todayPublished) {
    const { data: briefRow } = await supabase
      .from("briefs")
      .select("raw_json, brief_date")
      .eq("brief_date", today)
      .maybeSingle();

    if (briefRow?.raw_json) {
      const transformed = transformBrief(briefRow.raw_json as RawPipelineBrief);
      publishedBriefDate = briefRow.brief_date;
      publishedItems = transformed.items;
    }
  }

  // Only look up an older pending brief if today's isn't already published.
  const brief =
    !todayPublished && userId
      ? await getLatestAccessiblePendingBrief(supabase, userId)
      : null;

  let items: unknown[] = [];

  if (brief) {
    items = await loadCurationItems(supabase, brief.id);
  }

  return (
    <div className="p-6">
      <CurationWorkspace
        initialBrief={brief as never}
        initialItems={items as never[]}
        todayPublished={todayPublished}
        publishedBriefDate={publishedBriefDate}
        publishedItems={publishedItems}
      />
    </div>
  );
}
