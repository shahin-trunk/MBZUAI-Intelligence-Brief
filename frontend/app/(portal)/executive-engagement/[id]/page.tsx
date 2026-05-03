import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { createServiceClient } from "@/lib/supabase/server";
import { resolveEngagementMaterials } from "@/lib/server/engagement-materials";
import { EngagementDetailClient } from "@/components/internal/executive-engagement/EngagementDetailClient";
import type {
  Engagement,
  EngagementFollowup,
} from "@/lib/types/executive-engagement";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { id } = await params;
  const supabase = createServiceClient();

  const { data } = await supabase
    .from("engagements")
    .select("visitor_name")
    .eq("id", id)
    .single();

  const name = data?.visitor_name ?? "Engagement";

  return {
    title: `${name} — Executive Engagement`,
    description: `Engagement dossier for ${name}`,
  };
}

export default async function EngagementDetailPage({ params }: PageProps) {
  const { id } = await params;
  const supabase = createServiceClient();

  // Fetch the engagement
  const { data: engagement, error } = await supabase
    .from("engagements")
    .select("*")
    .eq("id", id)
    .single();

  if (error || !engagement) {
    notFound();
  }

  const hydratedEngagement: Engagement = {
    ...(engagement as Engagement),
    materials: await resolveEngagementMaterials(
      supabase,
      (engagement as Engagement).materials
    ),
  };

  // Fetch followups
  const { data: followupData } = await supabase
    .from("engagement_followups")
    .select("*")
    .eq("engagement_id", id)
    .order("created_at", { ascending: false });

  const followups = (followupData ?? []) as EngagementFollowup[];

  // Fetch ordered list of future engagement IDs for prev/next nav
  const now = new Date();
  const gstMs = now.getTime() + 4 * 60 * 60 * 1000;
  const todayGST = new Date(gstMs).toISOString().split("T")[0];

  const { data: allEngagements } = await supabase
    .from("engagements")
    .select("id, visitor_name")
    .gte("date", todayGST)
    .order("date", { ascending: true })
    .order("time", { ascending: true });

  const orderedIds = (allEngagements ?? []).map((e) => e.id);
  const orderedNames = (allEngagements ?? []).map((e) => e.visitor_name);
  const currentIndex = orderedIds.indexOf(id);
  const prevId = currentIndex > 0 ? orderedIds[currentIndex - 1] : null;
  const nextId =
    currentIndex >= 0 && currentIndex < orderedIds.length - 1
      ? orderedIds[currentIndex + 1]
      : null;
  const prevName = currentIndex > 0 ? orderedNames[currentIndex - 1] : null;
  const nextName =
    currentIndex >= 0 && currentIndex < orderedIds.length - 1
      ? orderedNames[currentIndex + 1]
      : null;

  return (
    <EngagementDetailClient
      engagement={hydratedEngagement}
      followups={followups}
      prevId={prevId}
      nextId={nextId}
      prevName={prevName}
      nextName={nextName}
    />
  );
}
