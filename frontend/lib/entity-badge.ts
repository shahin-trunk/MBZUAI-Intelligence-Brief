import type { LucideIcon } from "lucide-react";

import type { EntityLogoCategory } from "@/lib/constants/entity-logo-categories";
import type { BriefItem } from "@/lib/types/brief";
import { inferEntityCategory } from "@/lib/entity-category";
import { countryCodeFor } from "@/lib/country-flags";
import { sectionMarkFor } from "@/lib/section-icons";

interface EntityLogoLike {
  logoUrl: string | null;
  category: string;
}

interface ResolveEntityBadgeOptions {
  entityLogo?: EntityLogoLike | null;
}

/**
 * Three-tier badge resolution:
 *   1. Entity logo from the `entity_logos` DB table.
 *   2. Country flag via `flag-icons`, when the primary subject is a
 *      recognized country (and no logo was found in the table).
 *   3. Section icon — UAE renders the UAE flag, the other four canonical
 *      sections each have a Lucide icon chosen for unambiguous reading.
 *
 * There is no publication-favicon fallback and no region-mark tier. If a
 * story has no canonical section it falls through to a neutral Newspaper
 * icon via `sectionMarkFor`.
 */
export type ResolvedEntityBadge =
  | {
      kind: "logo";
      category: EntityLogoCategory;
      label: string | null;
      logoUrl: string;
    }
  | {
      kind: "flag";
      category: EntityLogoCategory;
      label: string | null;
      countryCode: string;
    }
  | {
      kind: "icon";
      category: EntityLogoCategory;
      label: string | null;
      Icon: LucideIcon;
    };

function cleanLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  const cleaned = value
    .replace(/\*\*/g, "")
    .replace(/[_`]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return cleaned.length > 0 ? cleaned : null;
}

export function preferredEntityLabelForItem(item: Pick<
  BriefItem,
  | "badge_subject"
  | "primary_subject"
  | "primary_entity"
  | "entities"
  | "model_release_data"
>): string | null {
  const candidates = [
    cleanLabel(item.badge_subject),
    cleanLabel(item.primary_subject),
    cleanLabel(item.primary_entity),
    cleanLabel(item.model_release_data?.model_name),
    ...((item.entities ?? []).map(cleanLabel).filter(Boolean) as string[]),
  ];

  for (const candidate of candidates) {
    if (candidate) return candidate;
  }
  return null;
}

/**
 * Ordered list of entity_logos names to try for a brief item. The primary
 * entity label comes first; when it's absent, a curated section-level
 * logo takes its place. Currently only the UAE section gets one — it
 * maps to the "United Arab Emirates" row (a proper country flag SVG
 * hosted in Supabase) so every UAE brief card renders a flag even when
 * the story has no specific actor.
 */
export function entityLogoLookupNames(item: Pick<
  BriefItem,
  | "badge_subject"
  | "primary_subject"
  | "primary_entity"
  | "entities"
  | "model_release_data"
  | "section"
>): string[] {
  const names: string[] = [];
  const primary = preferredEntityLabelForItem(item);
  if (primary) names.push(primary);
  const sectionName = sectionLogoEntityName(item.section);
  if (sectionName) names.push(sectionName);
  return names;
}

function sectionLogoEntityName(section: string | null | undefined): string | null {
  if (!section) return null;
  if (section.trim() === "UAE") return "United Arab Emirates";
  return null;
}

export function resolveEntityBadge(
  item: Pick<
    BriefItem,
    | "headline"
    | "section"
    | "source_name"
    | "source_domain"
    | "primary_subject"
    | "primary_entity"
    | "primary_entity_category"
    | "badge_subject"
    | "badge_subject_type"
    | "badge_subject_category"
    | "is_model_release"
    | "model_release_data"
    | "entities"
  >,
  options: ResolveEntityBadgeOptions = {}
): ResolvedEntityBadge {
  const category = inferEntityCategory(item, {
    authoritativeCategory:
      options.entityLogo?.category ?? item.badge_subject_category,
  });
  const label = preferredEntityLabelForItem(item);

  // Tier 1 — entity logo from the entity_logos table.
  const logoUrl = options.entityLogo?.logoUrl ?? null;
  if (logoUrl) {
    return { kind: "logo", category, label, logoUrl };
  }

  // Tier 2 — country flag when the subject is a recognized country.
  if (category === "country") {
    const countryLabel =
      item.badge_subject ?? item.primary_subject ?? item.primary_entity ?? label;
    const code = countryLabel ? countryCodeFor(countryLabel) : null;
    if (code) {
      return { kind: "flag", category, label, countryCode: code };
    }
  }

  // Tier 3 — section mark (UAE → flag, others → Lucide icon).
  const mark = sectionMarkFor(item.section);
  if (mark.kind === "flag") {
    return { kind: "flag", category, label, countryCode: mark.countryCode };
  }
  return { kind: "icon", category, label, Icon: mark.Icon };
}
