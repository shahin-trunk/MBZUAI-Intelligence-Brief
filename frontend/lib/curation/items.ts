import { SECTION_ORDER } from "@/lib/types/brief";
import type { BriefItem, ExhibitData } from "@/lib/types/brief";
import type {
  CurationItem,
  CurationItemRef,
  ManualItem,
  PendingItem,
} from "@/lib/types/curation";
import { inferEntityCategory } from "@/lib/entity-category";

const COUNTRY_NAMES = new Set([
  "uae",
  "united arab emirates",
  "united states",
  "united states of america",
  "us",
  "usa",
  "united kingdom",
  "uk",
  "saudi arabia",
  "ksa",
  "qatar",
  "oman",
  "bahrain",
  "kuwait",
  "iran",
  "iraq",
  "israel",
  "lebanon",
  "syria",
  "jordan",
  "egypt",
  "turkey",
  "turkiye",
  "china",
  "france",
  "germany",
  "italy",
  "spain",
  "india",
  "japan",
  "singapore",
  "south korea",
]);

const PERSON_TITLE_TERMS =
  /\b(president|prime minister|crown prince|sheikh|emir|king|queen|minister|secretary)\b/i;
const ORG_NAME_TERMS =
  /\b(university|college|institute|ministry|department|agency|command|capital|bank|fund|authority|commission|council|group|labs?|lab|technologies|technology|systems|holdings|foundation|association|alliance|committee|airways|government)\b/i;
const PLACE_TERMS =
  /\b(city|state|province|county|region|emirate|island|port|strait|gulf)\b/i;
const ASSET_TERMS =
  /\b(brent|wti|crude|oil|gas|lng|index|yield|bond|bitcoin|ethereum|gold|silver|nasdaq|dow|s&p)\b/i;

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function normalizeIdentityValue(value: unknown): string {
  return typeof value === "string"
    ? value.toLowerCase().replace(/[^\p{L}\p{N}\s.-]+/gu, " ").replace(/\s+/g, " ").trim()
    : "";
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function normalizeKeyBullets(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  const bullets = value
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter(Boolean);
  return bullets.length > 0 ? bullets : null;
}

export function normalizeExhibits(value: unknown): ExhibitData[] | null {
  if (!Array.isArray(value)) return null;
  return value.length > 0 ? (value as ExhibitData[]) : null;
}

export function buildLegacyTextFields(fields: {
  key_bullets?: unknown;
  analysis?: unknown;
  main_bullet?: unknown;
  context?: unknown;
  implication?: unknown;
}) {
  const bullets = normalizeKeyBullets(fields.key_bullets);
  const analysis = asString(fields.analysis);
  const mainBullet =
    asString(fields.main_bullet) ?? (bullets ? bullets.join(" ") : null);
  const context = asString(fields.context) ?? analysis;
  const implication = asString(fields.implication);
  return {
    key_bullets: bullets,
    analysis,
    main_bullet: mainBullet,
    context,
    implication,
  };
}

function baseRawItem(row: Record<string, unknown>) {
  return (row.raw_item as Record<string, unknown> | null) ?? {};
}

function isInformativeIdentityLabel(label: string | null): boolean {
  if (!label) return false;
  const compact = label.replace(/\./g, "").trim();
  return compact.length >= 3 || compact.split(/\s+/).length >= 2;
}

function deriveSubjectType(
  label: string | null,
  category: PendingItem["primary_entity_category"],
  item: Record<string, unknown>
): PendingItem["primary_subject_type"] {
  if (!label) return null;
  const normalized = normalizeIdentityValue(label);
  const modelData = (item.model_release_data as Record<string, unknown> | null) ?? null;
  const modelName = asString(modelData?.model_name);

  if (modelName && normalizeIdentityValue(modelName) === normalized) return "model";
  if (item.is_model_release) return "model";
  if (COUNTRY_NAMES.has(normalized)) return "country";
  if (PERSON_TITLE_TERMS.test(label)) return "person";
  if (PLACE_TERMS.test(label)) return "place";
  if (ASSET_TERMS.test(label)) return "asset";
  if (ORG_NAME_TERMS.test(label)) return "organization";

  switch (category) {
    case "company":
    case "university":
    case "government":
    case "energy":
    case "finance":
    case "defense":
    case "org":
      return "organization";
    case "country":
      return "country";
    case "model":
      return "model";
    default:
      break;
  }

  if (isInformativeIdentityLabel(label)) return "other";
  return null;
}

function deriveIdentityFields(
  item: Record<string, unknown>,
  previousRaw: Record<string, unknown>,
  primaryEntityChanged: boolean
) {
  const primaryEntity = asString(item.primary_entity);
  const modelData = (item.model_release_data as Record<string, unknown> | null) ?? null;
  const primarySubjectCandidate =
    primaryEntity ?? asString(modelData?.developer) ?? asString(modelData?.model_name);
  const primaryEntityCategory = inferEntityCategory({
    headline: asString(item.headline) ?? "",
    section: asString(item.section) ?? "",
    source_name: asString(item.source_name) ?? "",
    source_domain: asString(item.source_domain) ?? "",
    primary_subject: primarySubjectCandidate ?? undefined,
    primary_entity: primaryEntity ?? undefined,
    badge_subject: undefined,
    primary_entity_category: undefined,
    is_model_release: Boolean(item.is_model_release),
    model_release_data:
      (item.model_release_data as BriefItem["model_release_data"] | null)
      ?? undefined,
    entities: Array.isArray(item.entities)
      ? item.entities.filter((value): value is string => typeof value === "string")
      : [],
  });
  const primarySubjectType = deriveSubjectType(
    primarySubjectCandidate,
    primaryEntityCategory,
    item
  );
  const primarySubject =
    primarySubjectCandidate
    && (
      isInformativeIdentityLabel(primarySubjectCandidate)
      || primarySubjectType !== null
    )
      ? primarySubjectCandidate
      : null;

  const badgeSubject = primaryEntityChanged
    ? primarySubject
    : asString(previousRaw.badge_subject) ?? primarySubject;
  const badgeSubjectCategory = primaryEntityChanged
    ? primaryEntityCategory
    : (asString(previousRaw.badge_subject_category) as PendingItem["badge_subject_category"])
      ?? primaryEntityCategory;
  const badgeSubjectType = deriveSubjectType(
    badgeSubject,
    badgeSubjectCategory,
    item
  );

  return {
    primary_entity_category: primaryEntityCategory,
    primary_subject: primarySubject,
    primary_subject_type: primarySubject ? primarySubjectType : null,
    badge_subject: badgeSubject,
    badge_subject_type: badgeSubject ? badgeSubjectType : null,
    badge_subject_category: badgeSubject ? badgeSubjectCategory : null,
  };
}

export function mergeRawItem(
  row: Record<string, unknown>,
  fields: Record<string, unknown>
): Record<string, unknown> {
  const current = baseRawItem(row);
  const legacy = buildLegacyTextFields({
    key_bullets: fields.key_bullets ?? row.key_bullets,
    analysis: fields.analysis ?? row.analysis,
    main_bullet: fields.main_bullet ?? row.main_bullet,
    context: fields.context ?? row.context,
    implication: fields.implication ?? row.implication,
  });
  const primaryEntity =
    asString(fields.primary_entity) ??
    asString(row.primary_entity) ??
    asString(current.primary_entity);
  const primaryEntityChanged = primaryEntity !== asString(current.primary_entity);
  const merged = {
    ...current,
    id: asString(row.item_id) ?? asString(current.id) ?? "",
    section: asString(fields.section) ?? asString(row.section) ?? current.section ?? "",
    headline: asString(fields.headline) ?? asString(row.headline) ?? current.headline ?? "",
    source_name: asString(fields.source_name) ?? asString(row.source_name) ?? current.source_name ?? null,
    source_url: asString(fields.source_url) ?? asString(row.source_url) ?? current.source_url ?? null,
    significance_level:
      asString(fields.significance_level) ??
      asString(row.significance_level) ??
      current.significance_level ??
      "medium",
    depth: asString(fields.depth) ?? asString(row.depth) ?? current.depth ?? "standard",
    is_model_release:
      typeof fields.is_model_release === "boolean"
        ? fields.is_model_release
        : typeof row.is_model_release === "boolean"
          ? row.is_model_release
          : Boolean(current.is_model_release),
    model_release_data:
      fields.model_release_data ?? row.model_release_data ?? current.model_release_data ?? null,
    composite_score:
      typeof fields.composite_score === "number"
        ? fields.composite_score
        : typeof row.composite_score === "number"
          ? row.composite_score
          : Number(current.composite_score ?? 0),
    main_bullet: legacy.main_bullet ?? "",
    context: legacy.context ?? null,
    implication: legacy.implication ?? null,
    key_bullets: legacy.key_bullets ?? null,
    analysis: legacy.analysis ?? null,
    primary_entity: primaryEntity,
    exhibits:
      normalizeExhibits(fields.exhibits) ??
      normalizeExhibits(row.exhibits) ??
      normalizeExhibits(current.exhibits),
  };
  const derivedIdentity = deriveIdentityFields(merged, current, primaryEntityChanged);

  return {
    ...merged,
    ...derivedIdentity,
  };
}

export function mapPendingItem(row: Record<string, unknown>): PendingItem {
  return {
    kind: "pending",
    id: String(row.id),
    pending_brief_id: String(row.pending_brief_id),
    item_id: String(row.item_id),
    section: String(row.section),
    headline: String(row.headline),
    main_bullet: asString(row.main_bullet),
    context: asString(row.context),
    implication: asString(row.implication),
    source_name: asString(row.source_name),
    source_url: asString(row.source_url),
    composite_score: Number(row.composite_score ?? 0),
    significance_level: asString(row.significance_level),
    rank: asNumber(row.rank),
    depth: asString(row.depth),
    is_model_release: Boolean(row.is_model_release),
    model_release_data: (row.model_release_data as Record<string, unknown> | null) ?? null,
    key_bullets: normalizeKeyBullets(row.key_bullets),
    analysis: asString(row.analysis),
    primary_entity: asString(row.primary_entity),
    primary_subject:
      asString(row.primary_subject) ??
      asString(((row.raw_item as Record<string, unknown> | null) ?? {}).primary_subject),
    primary_subject_type:
      (asString(row.primary_subject_type) ??
        asString(((row.raw_item as Record<string, unknown> | null) ?? {}).primary_subject_type)) as PendingItem["primary_subject_type"],
    primary_entity_category: asString(row.primary_entity_category) as PendingItem["primary_entity_category"],
    badge_subject:
      asString(row.badge_subject) ??
      asString(((row.raw_item as Record<string, unknown> | null) ?? {}).badge_subject),
    badge_subject_type:
      (asString(row.badge_subject_type) ??
        asString(((row.raw_item as Record<string, unknown> | null) ?? {}).badge_subject_type)) as PendingItem["badge_subject_type"],
    badge_subject_category:
      (asString(row.badge_subject_category) ??
        asString(((row.raw_item as Record<string, unknown> | null) ?? {}).badge_subject_category)) as PendingItem["badge_subject_category"],
    exhibits: normalizeExhibits(row.exhibits),
    selected: Boolean(row.selected),
    curation_order: asNumber(row.curation_order),
    raw_item: (row.raw_item as Record<string, unknown> | null) ?? {},
    created_at: String(row.created_at),
    updated_at: asString(row.updated_at),
  };
}

export function mapManualItem(row: Record<string, unknown>): ManualItem {
  const legacy = buildLegacyTextFields(row);
  return {
    kind: "manual",
    id: String(row.id),
    pending_brief_id: String(row.pending_brief_id),
    item_id: asString(row.item_id) ?? `manual-${String(row.id).slice(0, 8)}`,
    section: String(row.section),
    headline: String(row.headline),
    main_bullet: legacy.main_bullet,
    context: legacy.context,
    implication: legacy.implication,
    source_name: asString(row.source_name),
    source_url: asString(row.source_url),
    composite_score: Number(row.composite_score ?? 8),
    significance_level: asString(row.significance_level) ?? "medium",
    key_bullets: legacy.key_bullets,
    analysis: legacy.analysis,
    primary_entity: asString(row.primary_entity),
    primary_subject:
      asString(row.primary_subject) ??
      asString(((row.raw_item as Record<string, unknown> | null) ?? {}).primary_subject),
    primary_subject_type:
      (asString(row.primary_subject_type) ??
        asString(((row.raw_item as Record<string, unknown> | null) ?? {}).primary_subject_type)) as ManualItem["primary_subject_type"],
    primary_entity_category: asString(row.primary_entity_category) as ManualItem["primary_entity_category"],
    badge_subject:
      asString(row.badge_subject) ??
      asString(((row.raw_item as Record<string, unknown> | null) ?? {}).badge_subject),
    badge_subject_type:
      (asString(row.badge_subject_type) ??
        asString(((row.raw_item as Record<string, unknown> | null) ?? {}).badge_subject_type)) as ManualItem["badge_subject_type"],
    badge_subject_category:
      (asString(row.badge_subject_category) ??
        asString(((row.raw_item as Record<string, unknown> | null) ?? {}).badge_subject_category)) as ManualItem["badge_subject_category"],
    exhibits: normalizeExhibits(row.exhibits),
    selected: row.selected === undefined ? true : Boolean(row.selected),
    curation_order: asNumber(row.curation_order),
    raw_item: mergeRawItem(row, {}),
    depth: asString(row.depth) ?? "standard",
    is_model_release: Boolean(row.is_model_release),
    model_release_data: (row.model_release_data as Record<string, unknown> | null) ?? null,
    added_by: String(row.added_by),
    created_at: String(row.created_at),
    updated_at: asString(row.updated_at),
  };
}

export function normalizeCurationItems(
  pendingRows: Array<Record<string, unknown>> = [],
  manualRows: Array<Record<string, unknown>> = []
): CurationItem[] {
  return [
    ...pendingRows.map(mapPendingItem),
    ...manualRows.map(mapManualItem),
  ];
}

/** Sort items by composite_score descending (highest relevance first). */
function sortCurationItemsByScore(items: CurationItem[]): CurationItem[] {
  return items
    .slice()
    .sort((a, b) => (b.composite_score ?? 0) - (a.composite_score ?? 0));
}

/**
 * Group items by canonical brief section. Items within each section are
 * sorted by composite_score (highest first), and sections are returned
 * in SECTION_ORDER so the analyst sees a consistent layout. Items whose
 * section does not match any canonical name land in an "Other" bucket
 * at the end.
 *
 * Phase 2 (curation rewrite): by default, every canonical section appears
 * in the output — including empty ones — so the UI can render a "No
 * relevant items today" placeholder under the header rather than hide
 * the section entirely. Callers that want the old behaviour (skip empty
 * sections) can pass `{ includeEmpty: false }`.
 */
export function groupCurationItemsBySection(
  items: CurationItem[],
  options: { includeEmpty?: boolean } = {}
): Array<{ section: string; items: CurationItem[] }> {
  const includeEmpty = options.includeEmpty ?? true;
  const bySection = new Map<string, CurationItem[]>();
  for (const item of items) {
    const section = item.section || "Other";
    const bucket = bySection.get(section);
    if (bucket) {
      bucket.push(item);
    } else {
      bySection.set(section, [item]);
    }
  }

  const groups: Array<{ section: string; items: CurationItem[] }> = [];
  for (const canonical of SECTION_ORDER) {
    const bucket = bySection.get(canonical);
    if (bucket && bucket.length > 0) {
      groups.push({
        section: canonical,
        items: sortCurationItemsByScore(bucket),
      });
      bySection.delete(canonical);
    } else if (includeEmpty) {
      groups.push({ section: canonical, items: [] });
    }
  }

  // Any non-canonical sections get appended at the end in insertion order.
  for (const [section, bucket] of bySection.entries()) {
    if (bucket.length > 0) {
      groups.push({
        section,
        items: sortCurationItemsByScore(bucket),
      });
    }
  }

  return groups;
}

export function sortSelectedItemsForOrdering(items: CurationItem[]): CurationItem[] {
  return items
    .filter((item) => item.selected)
    .slice()
    .sort((a, b) => {
      const orderA = a.curation_order ?? Number.MAX_SAFE_INTEGER;
      const orderB = b.curation_order ?? Number.MAX_SAFE_INTEGER;
      if (orderA !== orderB) return orderA - orderB;
      return a.headline.localeCompare(b.headline, undefined, { sensitivity: "base" });
    });
}

export function toItemRef(item: CurationItem): CurationItemRef {
  return {
    id: item.id,
    kind: item.kind,
  };
}
