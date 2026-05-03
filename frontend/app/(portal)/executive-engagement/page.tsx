import type { Metadata } from "next";
import { createServiceClient } from "@/lib/supabase/server";
import { EngagementPageClient } from "@/components/internal/executive-engagement/EngagementPageClient";
import type { Engagement } from "@/lib/types/executive-engagement";

export const metadata: Metadata = {
  title: "Executive Engagement — Intelligence Dashboard",
  description: "Upcoming presidential meetings and engagement dossiers",
};

export const dynamic = "force-dynamic";

export default async function ExecutiveEngagementPage() {
  const supabase = createServiceClient();

  // Fetch future engagements (use Dubai/GST = UTC+4)
  const now = new Date();
  const gstMs = now.getTime() + 4 * 60 * 60 * 1000;
  const todayGST = new Date(gstMs).toISOString().split("T")[0];

  const { data: engagements, error: engErr } = await supabase
    .from("engagements")
    .select("*")
    .gte("date", todayGST)
    .order("date", { ascending: true })
    .order("time", { ascending: true });

  if (engErr) {
    console.error("[executive-engagement] fetch error:", engErr);
  }

  return (
    <EngagementPageClient
      engagements={(engagements ?? []) as Engagement[]}
    />
  );
}
