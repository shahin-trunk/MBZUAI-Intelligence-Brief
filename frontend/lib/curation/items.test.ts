// @vitest-environment node

/**
 * Tests for groupCurationItemsBySection — Phase 2 curation rewrite.
 *
 * The redesign asks the UI to render every canonical section header even
 * on low-volume days, showing "No relevant items today" under empty ones
 * rather than hiding them. This test locks the default behaviour.
 */

import { describe, expect, it } from "vitest";
import { groupCurationItemsBySection } from "@/lib/curation/items";
import type { PendingItem } from "@/lib/types/curation";
import { SECTION_ORDER } from "@/lib/types/brief";

function mkItem(
  partial: Partial<PendingItem> & { id: string }
): PendingItem {
  return {
    kind: "pending",
    id: partial.id,
    pending_brief_id: partial.pending_brief_id ?? "brief-1",
    item_id: partial.item_id ?? partial.id,
    section: partial.section ?? "UAE",
    headline: partial.headline ?? `Headline ${partial.id}`,
    main_bullet: partial.main_bullet ?? null,
    context: partial.context ?? null,
    implication: partial.implication ?? null,
    source_name: partial.source_name ?? "WAM",
    source_url: partial.source_url ?? null,
    composite_score: partial.composite_score ?? 7.0,
    significance_level: partial.significance_level ?? null,
    rank: partial.rank ?? null,
    depth: partial.depth ?? null,
    is_model_release: partial.is_model_release ?? false,
    model_release_data: partial.model_release_data ?? null,
    key_bullets: partial.key_bullets ?? null,
    analysis: partial.analysis ?? null,
    primary_entity: partial.primary_entity ?? null,
    primary_subject: partial.primary_subject ?? null,
    primary_subject_type: partial.primary_subject_type ?? null,
    primary_entity_category: partial.primary_entity_category ?? null,
    badge_subject: partial.badge_subject ?? null,
    badge_subject_type: partial.badge_subject_type ?? null,
    badge_subject_category: partial.badge_subject_category ?? null,
    exhibits: partial.exhibits ?? null,
    selected: partial.selected ?? false,
    curation_order: partial.curation_order ?? null,
    raw_item: partial.raw_item ?? {},
    created_at: partial.created_at ?? "2026-04-17T00:00:00Z",
    updated_at: partial.updated_at ?? null,
  };
}

describe("groupCurationItemsBySection", () => {
  it("includes empty canonical sections by default", () => {
    const items = [
      mkItem({ id: "a", section: "UAE" }),
      mkItem({ id: "b", section: "UAE" }),
    ];

    const groups = groupCurationItemsBySection(items);

    // All 5 canonical sections should appear, even with zero items.
    expect(groups.map((g) => g.section)).toEqual([...SECTION_ORDER]);
    const uae = groups.find((g) => g.section === "UAE");
    const other = groups.find(
      (g) => g.section === "International Business & Technology"
    );
    expect(uae?.items).toHaveLength(2);
    expect(other?.items).toHaveLength(0);
  });

  it("skips empty sections when includeEmpty: false", () => {
    const items = [mkItem({ id: "a", section: "UAE" })];
    const groups = groupCurationItemsBySection(items, { includeEmpty: false });
    expect(groups.map((g) => g.section)).toEqual(["UAE"]);
  });

  it("preserves SECTION_ORDER ordering", () => {
    const items = [
      mkItem({ id: "mr", section: "Model Releases & Technical Developments" }),
      mkItem({ id: "uae", section: "UAE" }),
      mkItem({ id: "intl", section: "International Politics & Policy" }),
    ];
    const groups = groupCurationItemsBySection(items);
    expect(groups.map((g) => g.section)).toEqual([...SECTION_ORDER]);
  });

  it("sorts items within a section by composite_score descending", () => {
    const items = [
      mkItem({ id: "low", section: "UAE", composite_score: 5.0 }),
      mkItem({ id: "high", section: "UAE", composite_score: 9.0 }),
      mkItem({ id: "mid", section: "UAE", composite_score: 7.0 }),
    ];
    const uae = groupCurationItemsBySection(items).find(
      (g) => g.section === "UAE"
    );
    expect(uae?.items.map((i) => i.id)).toEqual(["high", "mid", "low"]);
  });

  it("appends non-canonical sections at the end even when includeEmpty=true", () => {
    const items = [
      mkItem({ id: "weird", section: "Some Unknown Section" }),
    ];
    const groups = groupCurationItemsBySection(items);
    // Canonical sections first (all empty), then the unknown one.
    const sections = groups.map((g) => g.section);
    expect(sections.slice(0, SECTION_ORDER.length)).toEqual([...SECTION_ORDER]);
    expect(sections[sections.length - 1]).toBe("Some Unknown Section");
  });
});
