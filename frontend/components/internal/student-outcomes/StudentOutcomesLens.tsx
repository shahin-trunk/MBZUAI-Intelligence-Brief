"use client";

import { useState, useMemo } from "react";
import data from "@/lib/data/internal/student-outcomes.json";
import { getLensConfigOrThrow } from "@/lib/config/lenses";
import { LensPageHeader } from "@/components/internal/shared/LensPageHeader";
import { SectionHeader } from "@/components/internal/shared/SectionHeader";
import { AssessmentBlock } from "@/components/internal/shared/AssessmentBlock";
import { OutcomesToggle } from "./OutcomesToggle";
import { OutcomesFilters } from "./OutcomesFilters";
import { OutcomesMetrics } from "./OutcomesMetrics";
import { EmployerChart } from "./EmployerChart";
import { SectorChart } from "./SectorChart";
import { RegionChart } from "./RegionChart";
import { OutcomesHistorical } from "./OutcomesHistorical";
import { AlumniCards } from "./AlumniCards";
import { FurtherEducationCharts } from "./FurtherEducationCharts";
import { AlumniServiceSection } from "./AlumniServiceSection";
import type {
  EvidenceMetric,
  OutcomesHiringOrg,
  OutcomesCohort,
  OutcomesFilteredData,
  EmploymentSector,
  EmploymentRegion,
  AlumniHighlight,
  AlumniServiceActivity,
  AlumniServiceAward,
} from "@/lib/types/internal-intelligence";

// Cast JSON data
const baseMetrics = data.metrics as EvidenceMetric[];
const baseOrganizations = data.topHiringOrganizations as OutcomesHiringOrg[];
const sectorData = data.employmentBySector as EmploymentSector[];
const regionData = data.employmentByRegion as EmploymentRegion[];
const historicalCohorts = data.historicalCohorts as OutcomesCohort[];
const alumniData = data.alumni as AlumniHighlight[];
const filteredData = data.filtered as Record<string, OutcomesFilteredData>;
const furtherEdByProgram = (data as Record<string, unknown>).furtherEducationByProgram as { program: string; count: number }[];
const gradStudyDestinations = (data as Record<string, unknown>).topGradStudyDestinations as { institution: string; count: number }[];
const alumniServiceData = (data as Record<string, unknown>).alumniService as { activities: AlumniServiceActivity[]; awards: AlumniServiceAward[] };

type ProgramFilter = "all" | "msc" | "phd";
type NationalityFilter = "all" | "uae" | "international";

/** Map filter state to the JSON key in `data.filtered` */
function getFilterKey(
  program: ProgramFilter,
  nationality: NationalityFilter
): string | null {
  // If both have non-"all" values, prioritize nationality (more impactful for this audience)
  if (nationality === "uae") return "uaeNationalsOnly";
  if (nationality === "international") return "internationalOnly";
  if (program === "msc") return "mscOnly";
  if (program === "phd") return "phdOnly";
  return null; // all + all → use baseline
}

/** Build MetricCard-compatible array from filtered metrics */
function buildFilteredMetrics(fd: OutcomesFilteredData): EvidenceMetric[] {
  return [
    {
      id: "so-employment-rate",
      label: "Employment within 12 months",
      value: fd.metrics.employmentRate,
      format: "percentage",
      flagLevel: "normal",
    },
    {
      id: "so-total-graduates",
      label: "Total graduates (filtered)",
      value: fd.metrics.totalGraduates,
      format: "number",
      flagLevel: "normal",
    },
    {
      id: "so-uae-retention",
      label: "UAE retention rate",
      value: fd.metrics.uaeRetention,
      format: "percentage",
      flagLevel: "amber",
    },
    {
      id: "so-pct-ai-tech",
      label: "% in AI/tech roles",
      value: fd.metrics.pctAITech,
      format: "percentage",
      flagLevel: "amber",
    },
  ];
}

/** Build employer chart data from filtered employers (no uaeBased flag — all shown as blue) */
function buildFilteredEmployers(
  fd: OutcomesFilteredData
): OutcomesHiringOrg[] {
  const UAE_SET = new Set([
    "G42",
    "TII",
    "ADNOC",
    "Abu Dhabi Digital Authority",
    "Mubadala",
    "Ministry of AI",
  ]);
  return fd.topEmployers.map((e) => ({
    ...e,
    uaeBased: UAE_SET.has(e.organization),
  }));
}

export function StudentOutcomesLens() {
  const config = getLensConfigOrThrow("student-outcomes");
  const [mode, setMode] = useState<"current" | "historical">("current");
  const [programFilter, setProgramFilter] = useState<ProgramFilter>("all");
  const [nationalityFilter, setNationalityFilter] =
    useState<NationalityFilter>("all");

  const filterKey = getFilterKey(programFilter, nationalityFilter);

  const activeMetrics = useMemo(() => {
    if (!filterKey) return baseMetrics;
    const fd = filteredData[filterKey];
    if (!fd) return baseMetrics;
    return buildFilteredMetrics(fd);
  }, [filterKey]);

  const activeOrganizations = useMemo(() => {
    if (!filterKey) return baseOrganizations;
    const fd = filteredData[filterKey];
    if (!fd) return baseOrganizations;
    return buildFilteredEmployers(fd);
  }, [filterKey]);

  // Active filter label for combined filter note
  const showCombinedNote =
    programFilter !== "all" && nationalityFilter !== "all";

  return (
    <div className="space-y-10">
      {/* Page Header */}
      <LensPageHeader
        lensName={config.name}
        narrativeOwner={data.narrativeOwner}
        lastUpdated={data.lastUpdated}
        isAutoGeneratedOnly={data.isAutoGeneratedOnly}
      />

      {/* Assessment */}
      <div>
        <SectionHeader title="Assessment" />
        <AssessmentBlock assessment={data.assessment} />
      </div>

      {/* Supporting Evidence */}
      <div>
        <SectionHeader title="Supporting Evidence" />

        <OutcomesToggle mode={mode} onModeChange={setMode} />
        <OutcomesFilters
          programFilter={programFilter}
          nationalityFilter={nationalityFilter}
          onProgramFilterChange={setProgramFilter}
          onNationalityFilterChange={setNationalityFilter}
        />

        {/* Data note */}
        <p className="font-mono text-[14px] leading-[1.6] text-text-muted italic mb-6">
          {data.dataNote}
        </p>

        {/* Combined filter note */}
        {showCombinedNote && (
          <p className="font-mono text-[14px] leading-[1.6] text-accent-warning italic mb-4">
            Showing{" "}
            {nationalityFilter === "uae"
              ? "UAE Nationals"
              : "International"}{" "}
            filter. Combined filters coming soon.
          </p>
        )}

        {mode === "current" ? (
          <div className="space-y-6">
            <OutcomesMetrics metrics={activeMetrics} />
            <FurtherEducationCharts
              byProgram={furtherEdByProgram}
              destinations={gradStudyDestinations}
            />
            <EmployerChart organizations={activeOrganizations} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SectorChart data={sectorData} />
              <RegionChart data={regionData} />
            </div>
          </div>
        ) : (
          <OutcomesHistorical cohorts={historicalCohorts} />
        )}
      </div>

      {/* Alumni Highlights — always visible */}
      <div>
        <SectionHeader title="Alumni Highlights" />
        <AlumniCards alumni={alumniData} />
      </div>

      {/* Alumni Service & Engagement */}
      <div>
        <SectionHeader title="Alumni Service & Engagement" />
        <AlumniServiceSection
          activities={alumniServiceData.activities}
          awards={alumniServiceData.awards}
        />
      </div>
    </div>
  );
}
