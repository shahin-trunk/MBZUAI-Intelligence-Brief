// Canonical list of entity_logos categories. Must match the
// entity_logos_category_check constraint defined in
// frontend/supabase/migrations/013_add_country_category.sql. If you add
// a category here, add it to the migration too — the DB will reject
// inserts otherwise.
export const ENTITY_LOGO_CATEGORIES = [
  "company",
  "university",
  "government",
  "energy",
  "finance",
  "defense",
  "org",
  "model",
  "country",
  "other",
] as const;

export type EntityLogoCategory = (typeof ENTITY_LOGO_CATEGORIES)[number];

export function isEntityLogoCategory(value: string): value is EntityLogoCategory {
  return (ENTITY_LOGO_CATEGORIES as readonly string[]).includes(value);
}
