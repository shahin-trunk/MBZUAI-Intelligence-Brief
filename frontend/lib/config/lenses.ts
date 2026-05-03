import type { LensConfig, LensSlug } from "@/lib/types/internal-intelligence";

export const LENS_CONFIG: LensConfig[] = [
  {
    slug: "faculty-excellence",
    name: "Faculty Excellence",
    question: "Are we building a world-class faculty?",
    narrativeOwners: ["VP Faculty Excellence", "Division Deans"],
    hasDetailDrilldown: true,
  },
  {
    slug: "research-impact",
    name: "Research Impact",
    question: "Is our research making a difference?",
    narrativeOwners: ["Director of Research Admin", "Division Deans"],
    hasDetailDrilldown: false,
  },
  {
    slug: "student-pipeline",
    name: "Student Pipeline",
    question: "Are we attracting the right students?",
    narrativeOwners: ["VP Graduate Education", "Dean of UG Division"],
    hasDetailDrilldown: false,
  },
  {
    slug: "student-experience",
    name: "Student Experience",
    question: "Is the model working once students arrive?",
    narrativeOwners: ["Dean of UG Division", "Career Services Director"],
    hasDetailDrilldown: false,
  },
  {
    slug: "student-outcomes",
    name: "Student Outcomes",
    question: "",
    narrativeOwners: ["Career Services Director"],
    hasDetailDrilldown: true,
  },
  {
    slug: "visibility",
    name: "Visibility & Influence",
    question: "Are we recognized as a global AI leader?",
    narrativeOwners: ["VP MarComms", "VP NEO", "MD The Academy"],
    hasDetailDrilldown: false,
  },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

export function getLensConfig(slug: LensSlug): LensConfig | undefined {
  return LENS_CONFIG.find((l) => l.slug === slug);
}

export function getLensConfigOrThrow(slug: string): LensConfig {
  const config = LENS_CONFIG.find((l) => l.slug === slug);
  if (!config) {
    throw new Error(`Unknown lens slug: ${slug}`);
  }
  return config;
}

export function isValidLensSlug(slug: string): slug is LensSlug {
  return LENS_CONFIG.some((l) => l.slug === slug);
}

export function getCurrentMonth(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

/** Generate a list of the last N months in YYYY-MM format, most recent first. */
export function getRecentMonths(count: number = 6): string[] {
  const months: string[] = [];
  const now = new Date();
  for (let i = 0; i < count; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    months.push(`${year}-${month}`);
  }
  return months;
}

// ─── SMT Lens Tag Helpers ────────────────────────────────────────────────────

const TAG_DISPLAY_NAMES: Record<string, string> = {
  "faculty-excellence": "Faculty Excellence",
  "research-impact": "Research Impact",
  "student-pipeline": "Student Pipeline",
  "student-experience": "Student Experience",
  "student-outcomes": "Student Outcomes",
  visibility: "Visibility & Influence",
  operations: "Operations",
};

export function getTagDisplayName(tag: string): string {
  return TAG_DISPLAY_NAMES[tag] ?? tag;
}

export function getTagHref(tag: string): string {
  return `/${tag}`;
}

/** Format a YYYY-MM string for display, e.g. "March 2026". */
export function formatMonthDisplay(monthStr: string): string {
  const [year, month] = monthStr.split("-");
  const date = new Date(parseInt(year), parseInt(month) - 1, 1);
  return date.toLocaleDateString("en-US", { year: "numeric", month: "long" });
}
