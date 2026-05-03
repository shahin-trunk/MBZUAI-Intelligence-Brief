import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { LensShell } from "@/components/internal/LensShell";
import { getLensConfig, isValidLensSlug } from "@/lib/config/lenses";

interface LensPageProps {
  params: Promise<{ lens: string }>;
}

export async function generateMetadata({
  params,
}: LensPageProps): Promise<Metadata> {
  const { lens } = await params;

  if (!isValidLensSlug(lens)) {
    return { title: "Not Found — Intelligence Dashboard" };
  }

  const config = getLensConfig(lens);
  return {
    title: `${config?.name ?? lens} — Intelligence Dashboard`,
    description: config?.question,
  };
}

export default async function LensPage({ params }: LensPageProps) {
  const { lens } = await params;

  // Strategic Accountability no longer has a dedicated lens view.
  if (lens === "institutional-health") {
    redirect("/brief/today");
  }

  // Student sections are no longer exposed as standalone portal views.
  if (
    lens === "student-pipeline" ||
    lens === "student-experience" ||
    lens === "student-outcomes"
  ) {
    notFound();
  }

  if (!isValidLensSlug(lens)) {
    notFound();
  }

  return <LensShell lensSlug={lens} />;
}
