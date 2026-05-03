import type {
  Brief,
  BriefItem,
  BriefSection,
  RawPipelineBrief,
  RawPipelineItem,
  SectionName,
} from "@/lib/types/brief";
import { SECTION_ORDER } from "@/lib/types/brief";

interface BriefRowOverrides {
  generated_at?: string | null;
  item_count?: number | null;
  sources_consulted?: number | null;
  items_reviewed?: number | null;
  pipeline_cost_usd?: number | null;
  executive_summary?: string | null;
}

function isHttpUrl(url: string | null | undefined): url is string {
  return typeof url === "string" && /^https?:\/\//i.test(url.trim());
}

/**
 * Transform a raw pipeline JSON brief into the frontend Brief interface.
 *
 * Key operations:
 * 1. Maps brief_metadata → top-level Brief fields
 * 2. Filters out placeholder items
 * 3. Normalizes each item (renames fields, derives is_continuity)
 * 4. Preserves the published reading order for card UI
 * 5. Derives section groupings secondarily for compatibility views
 */
export function transformBrief(
  raw: RawPipelineBrief,
  overrides: BriefRowOverrides = {}
): Brief {
  const { brief_metadata, items } = raw;

  // Filter out placeholders
  const realItems = items.filter(
    (item) => !item.is_placeholder && item.depth !== "placeholder"
  );

  // Transform each item
  const transformedItems = realItems.map(transformItem);

  // Group by section in canonical order for compatibility views
  const sections = groupBySection(transformedItems);

  return {
    brief_date: brief_metadata.date,
    generated_at: overrides.generated_at ?? brief_metadata.generated_at,
    item_count: overrides.item_count ?? brief_metadata.total_items,
    sources_consulted: overrides.sources_consulted ?? 0,
    items_reviewed: overrides.items_reviewed ?? 0,
    pipeline_cost_usd: overrides.pipeline_cost_usd ?? 0,
    executive_summary: overrides.executive_summary ?? undefined,
    items: transformedItems,
    sections,
    metadata: {
      lead_story_id: brief_metadata.lead_story_id,
      section_counts: brief_metadata.section_counts,
    },
  };
}

/**
 * Transform a single raw pipeline item to the frontend BriefItem shape.
 */
function transformItem(raw: RawPipelineItem): BriefItem {
  const additionalSources = (raw.additional_sources ?? []).filter(
    (src) => src?.name && isHttpUrl(src.url)
  );

  return {
    id: raw.id,
    headline: raw.headline,
    main_bullet: raw.main_bullet,
    context: raw.context ?? undefined,
    implication: raw.implication ?? undefined,
    source_name: raw.source_name ?? "Unknown",
    source_url: isHttpUrl(raw.source_url) ? raw.source_url : undefined,
    source_origin:
      raw.source_origin === "newsletter" ? "newsletter" : "canonical",
    significance: normalizeSignificance(raw.significance_level),
    composite_score: raw.composite_score,
    topic_relevance: 0, // Not in final brief output
    news_significance: 0, // Not in final brief output
    is_continuity: raw.continuity !== null && raw.continuity !== undefined,
    continuity_days: raw.continuity ? 1 : undefined,
    section: raw.section,

    // Extended fields
    rank: raw.rank,
    depth: normalizeDepth(raw.depth),
    entities: raw.entities,
    additional_sources: additionalSources,
    source_domain: raw.source_domain ?? undefined,
    cluster: raw.cluster ?? undefined,
    is_model_release: raw.is_model_release ?? false,
    model_release_data: raw.model_release_data ?? undefined,

    // v2 card reader fields (null-safe for old briefs)
    key_bullets: raw.key_bullets?.length ? raw.key_bullets : undefined,
    analysis: raw.analysis ?? undefined,
    primary_entity: raw.primary_entity ?? undefined,
    primary_subject: raw.primary_subject ?? undefined,
    primary_subject_type: raw.primary_subject_type ?? undefined,
    // Narrow via cast — the raw JSON is freeform. Strict narrowing would
    // force us to list every valid category in two places.
    primary_entity_category: (raw.primary_entity_category ?? undefined) as
      | BriefItem["primary_entity_category"]
      | undefined,
    badge_subject: raw.badge_subject ?? undefined,
    badge_subject_type: raw.badge_subject_type ?? undefined,
    badge_subject_category: (raw.badge_subject_category ?? undefined) as
      | BriefItem["badge_subject_category"]
      | undefined,
    exhibits: Array.isArray(raw.exhibits)
      ? raw.exhibits
      : raw.exhibits
        ? [raw.exhibits]
        : undefined,
    audio_url: raw.audio_url ?? undefined,
  };
}

/**
 * Group transformed items in curator-chosen order.
 *
 * Before Phase 5: this function forced canonical SECTION_ORDER (UAE first),
 * overriding whatever cross-section sequence the curator set in the ordering
 * screen. If the curator put Model Releases before UAE, the published brief
 * still led with UAE.
 *
 * After Phase 5: iterate items in the order the curator set. Adjacent items
 * that share a section collapse into one section block; a new section block
 * opens every time the section changes. The result is a flat sequence with
 * section labels where sections transition — the same visual shape the
 * curator saw in the OrderingScreen. If the curator interleaves sections
 * deliberately (e.g. [UAE, Politics, UAE]), the reader sees three blocks,
 * preserving the intent.
 */
function groupBySection(items: BriefItem[]): BriefSection[] {
  if (items.length === 0) return [];

  const sections: BriefSection[] = [];
  let current: BriefSection = { name: items[0].section, items: [items[0]] };
  for (let i = 1; i < items.length; i++) {
    if (items[i].section === current.name) {
      current.items.push(items[i]);
    } else {
      sections.push(current);
      current = { name: items[i].section, items: [items[i]] };
    }
  }
  sections.push(current);
  return sections;
}

/**
 * Normalize significance level from pipeline to frontend enum.
 */
function normalizeSignificance(
  level: string | null | undefined
): "high" | "medium" | "low" {
  if (level === "high") return "high";
  if (level === "medium") return "medium";
  return "low";
}

/**
 * Normalize depth from pipeline string to frontend union type.
 */
function normalizeDepth(depth: string): "full" | "standard" | "brief" {
  if (depth === "full") return "full";
  if (depth === "standard") return "standard";
  return "brief";
}

/**
 * Get all items across all sections sorted by composite score (descending).
 */
export function getTopItems(brief: Brief, count: number = 3): BriefItem[] {
  return brief.items
    .slice()
    .sort((a, b) => {
      if (b.composite_score !== a.composite_score) {
        return b.composite_score - a.composite_score;
      }
      return a.rank - b.rank;
    })
    .slice(0, count);
}

/**
 * Get the lead story from a brief.
 */
export function getLeadStory(brief: Brief): BriefItem | undefined {
  const leadId = brief.metadata.lead_story_id;
  if (!leadId) return undefined;
  return brief.items.find((item) => item.id === leadId);
}

/**
 * Get a section display name that's shorter for nav/tabs.
 */
export function getSectionShortName(name: string): string {
  const shortNames: Record<SectionName, string> = {
    "UAE": "UAE",
    "Regional Research & Academic Events": "Regional",
    "International Politics & Policy": "Intl Politics",
    "International Business & Technology": "Intl Business",
    "Model Releases & Technical Developments": "AI & Tech",
  };
  return shortNames[name as SectionName] ?? name;
}
