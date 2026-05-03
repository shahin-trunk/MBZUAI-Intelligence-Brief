/**
 * Solid section tags for the story hero: soft fill + same-hue type (no border).
 * Full class strings so Tailwind can see them at build time.
 */
const SECTION_TAG_PALETTES = [
  "bg-rose-100 text-rose-900",
  "bg-amber-100 text-amber-900",
  "bg-emerald-100 text-emerald-900",
  "bg-violet-100 text-violet-900",
  "bg-sky-100 text-sky-900",
  "bg-teal-100 text-teal-900",
] as const;

/** Deterministic palette from section label so the same section keeps the same color. */
export function sectionTagPaletteClasses(section: string): string {
  const s = section.trim();
  if (!s) return SECTION_TAG_PALETTES[0];

  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = (h * 33) ^ s.charCodeAt(i);
  }
  const idx = Math.abs(h) % SECTION_TAG_PALETTES.length;
  return SECTION_TAG_PALETTES[idx];
}
