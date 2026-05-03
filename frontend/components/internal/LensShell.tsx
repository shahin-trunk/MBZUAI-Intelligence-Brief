import { getLensConfigOrThrow } from "@/lib/config/lenses";
import type { LensSlug } from "@/lib/types/internal-intelligence";
import { AssessmentSection } from "@/components/internal/AssessmentSection";
import { EvidenceSection } from "@/components/internal/EvidenceSection";
import { DrilldownSection } from "@/components/internal/DrilldownSection";
import { FacultyExcellenceLens } from "@/components/internal/faculty-excellence";
import { StudentPipelineLens } from "@/components/internal/student-pipeline";
import { StudentExperienceLens } from "@/components/internal/student-experience";
import { ResearchImpactLens } from "@/components/internal/research-impact";
import { VisibilityLens } from "@/components/internal/visibility";
import { StudentOutcomesLens } from "@/components/internal/student-outcomes";

interface LensShellProps {
  lensSlug: LensSlug;
}

export function LensShell({ lensSlug }: LensShellProps) {
  const config = getLensConfigOrThrow(lensSlug);

  // Lens-specific rendering
  if (lensSlug === "faculty-excellence") {
    return <FacultyExcellenceLens />;
  }

  if (lensSlug === "student-pipeline") {
    return <StudentPipelineLens />;
  }

  if (lensSlug === "student-experience") {
    return <StudentExperienceLens />;
  }

  if (lensSlug === "research-impact") {
    return <ResearchImpactLens />;
  }

  if (lensSlug === "student-outcomes") {
    return <StudentOutcomesLens />;
  }

  if (lensSlug === "visibility") {
    return <VisibilityLens />;
  }

  // Generic shell for other lenses (placeholder)
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-serif text-[28px] text-text-bright">{config.name}</h1>
      </div>

      {/* 1. Assessment */}
      <AssessmentSection />

      {/* 2. Supporting Evidence */}
      <EvidenceSection />

      {/* 3. Drilldown (conditional — only for lenses that need it) */}
      {config.hasDetailDrilldown && (
        <DrilldownSection lensName={config.name} />
      )}
    </div>
  );
}
