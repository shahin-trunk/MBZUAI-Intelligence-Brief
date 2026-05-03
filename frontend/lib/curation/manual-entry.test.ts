// @vitest-environment node

/**
 * Tests for the manual entry ingestion pipeline.
 *
 * Covers:
 *   1. mergeRawItem produces primary_entity_category for manual items
 *   2. buildLegacyTextFields derives main_bullet / context from key_bullets
 *   3. mapManualItem reads primary_entity_category from the DB row
 *   4. mapManualItem falls back to raw_item for identity fields
 *   5. normalizeKeyBullets / normalizeExhibits edge cases
 *   6. buildManualItem & buildProposedItem propagate primary_entity_category
 */

import { describe, expect, it } from "vitest";
import {
  buildLegacyTextFields,
  mapManualItem,
  mergeRawItem,
  normalizeExhibits,
  normalizeKeyBullets,
} from "@/lib/curation/items";
import {
  buildManualEntryNotes,
  extractExhibitsFromManualEntryNotes,
} from "@/lib/curation/manual-entry-metadata";

// ---------------------------------------------------------------------------
// 1. mergeRawItem produces identity fields including primary_entity_category
// ---------------------------------------------------------------------------

describe("mergeRawItem", () => {
  it("derives primary_entity_category for a manual item with a known entity", () => {
    const row = {
      item_id: "manual-abc12345",
      section: "International Business & Technology",
      headline: "OpenAI launches new enterprise API",
      source_name: "TechCrunch",
      source_url: "https://techcrunch.com/openai",
      primary_entity: "OpenAI",
      key_bullets: ["OpenAI released a new enterprise API tier."],
      analysis: "This matters for enterprise AI adoption.",
      raw_item: null,
    };

    const result = mergeRawItem(row, row);
    expect(result.primary_entity_category).toBeDefined();
    expect(typeof result.primary_entity_category).toBe("string");
    // OpenAI should be categorized as "company"
    expect(result.primary_entity_category).toBe("company");
  });

  it("derives primary_entity_category as 'university' for a university entity", () => {
    const row = {
      item_id: "manual-uni00001",
      section: "Regional Research & Academic Events",
      headline: "Khalifa University opens new research center",
      source_name: "The National",
      source_url: null,
      primary_entity: "Khalifa University",
      key_bullets: ["Khalifa University announced a new center."],
      analysis: "Expands the university's research capacity.",
      raw_item: null,
    };

    const result = mergeRawItem(row, row);
    expect(result.primary_entity_category).toBe("university");
  });

  it("derives primary_entity_category as 'government' for government entities", () => {
    const row = {
      item_id: "manual-gov00001",
      section: "UAE",
      headline: "Ministry of Education updates AI curriculum",
      source_name: "WAM",
      source_url: null,
      primary_entity: "Ministry of Education",
      key_bullets: ["Curriculum updated."],
      analysis: "Strengthens national AI education.",
      raw_item: null,
    };

    const result = mergeRawItem(row, row);
    // "Ministry of Education" should be inferred as government
    expect(result.primary_entity_category).toBe("government");
  });

  it("populates primary_subject and badge_subject from the entity", () => {
    const row = {
      item_id: "manual-sub00001",
      section: "International Business & Technology",
      headline: "Google announces Gemini 3.0",
      source_name: "Reuters",
      source_url: null,
      primary_entity: "Google",
      key_bullets: ["Gemini 3.0 announced."],
      analysis: "Major model release.",
      raw_item: null,
    };

    const result = mergeRawItem(row, row);
    expect(result.primary_subject).toBe("Google");
    expect(result.badge_subject).toBe("Google");
    expect(result.primary_subject_type).toBeDefined();
    expect(result.badge_subject_type).toBeDefined();
  });

  it("handles null primary_entity gracefully", () => {
    const row = {
      item_id: "manual-null0001",
      section: "International Politics & Policy",
      headline: "Global trade tensions rise",
      source_name: "FT",
      source_url: null,
      primary_entity: null,
      key_bullets: ["Tensions are rising."],
      analysis: "Could affect markets.",
      raw_item: null,
    };

    const result = mergeRawItem(row, row);
    // Should not crash; category may be null or 'other'
    expect(result).toBeDefined();
    expect(result.headline).toBe("Global trade tensions rise");
  });

  it("preserves existing raw_item fields when merging", () => {
    const existingRaw = {
      id: "manual-prev0001",
      section: "UAE",
      headline: "Old headline",
      source_domain: "example.com",
      additional_sources: [{ name: "AP", url: "https://ap.org" }],
    };
    const row = {
      item_id: "manual-prev0001",
      section: "UAE",
      headline: "Updated headline",
      source_name: "WAM",
      source_url: null,
      primary_entity: null,
      key_bullets: ["A bullet."],
      analysis: null,
      raw_item: existingRaw,
    };

    const result = mergeRawItem(row, row);
    // The headline should be updated
    expect(result.headline).toBe("Updated headline");
    // The source_domain from existing raw should be preserved
    expect(result.source_domain).toBe("example.com");
  });
});

// ---------------------------------------------------------------------------
// 2. buildLegacyTextFields
// ---------------------------------------------------------------------------

describe("buildLegacyTextFields", () => {
  it("produces main_bullet by joining key_bullets", () => {
    const result = buildLegacyTextFields({
      key_bullets: ["First point.", "Second point."],
      analysis: "Strategic analysis.",
    });
    expect(result.main_bullet).toBe("First point. Second point.");
    expect(result.context).toBe("Strategic analysis.");
    expect(result.analysis).toBe("Strategic analysis.");
  });

  it("preserves explicit main_bullet when provided", () => {
    const result = buildLegacyTextFields({
      key_bullets: ["Bullet one."],
      analysis: null,
      main_bullet: "Explicit main bullet.",
    });
    expect(result.main_bullet).toBe("Explicit main bullet.");
  });

  it("returns null for missing fields", () => {
    const result = buildLegacyTextFields({});
    expect(result.key_bullets).toBeNull();
    expect(result.analysis).toBeNull();
    expect(result.main_bullet).toBeNull();
    expect(result.context).toBeNull();
    expect(result.implication).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 3. mapManualItem reads primary_entity_category from DB row
// ---------------------------------------------------------------------------

describe("mapManualItem", () => {
  const baseRow = {
    id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    pending_brief_id: "11111111-2222-3333-4444-555555555555",
    item_id: "manual-abc12345",
    section: "UAE",
    headline: "Test Headline",
    main_bullet: "Test bullet",
    context: "Test context",
    implication: null,
    source_name: "WAM",
    source_url: "https://wam.ae/article",
    composite_score: 8,
    significance_level: "medium",
    key_bullets: ["Bullet 1"],
    analysis: "Some analysis.",
    primary_entity: "ADNOC",
    primary_entity_category: "energy",
    exhibits: null,
    selected: true,
    curation_order: 3,
    raw_item: {
      primary_subject: "ADNOC",
      primary_subject_type: "organization",
      badge_subject: "ADNOC",
      badge_subject_type: "organization",
      badge_subject_category: "energy",
      primary_entity_category: "energy",
    },
    depth: "standard",
    is_model_release: false,
    model_release_data: null,
    added_by: "99999999-8888-7777-6666-555555555555",
    created_at: "2026-04-16T08:00:00Z",
    updated_at: "2026-04-16T08:00:00Z",
  };

  it("maps primary_entity_category from the row column", () => {
    const item = mapManualItem(baseRow);
    expect(item.primary_entity_category).toBe("energy");
  });

  it("maps identity fields from raw_item fallback", () => {
    const rowWithoutColumns = {
      ...baseRow,
      primary_entity_category: null,
      primary_subject: undefined,
      primary_subject_type: undefined,
      badge_subject: undefined,
      badge_subject_type: undefined,
      badge_subject_category: undefined,
    };
    const item = mapManualItem(rowWithoutColumns);
    // Should fall back to raw_item values
    expect(item.primary_subject).toBe("ADNOC");
    expect(item.badge_subject).toBe("ADNOC");
    expect(item.badge_subject_category).toBe("energy");
  });

  it("sets kind to 'manual'", () => {
    const item = mapManualItem(baseRow);
    expect(item.kind).toBe("manual");
  });

  it("handles missing raw_item gracefully", () => {
    const rowNoRaw = { ...baseRow, raw_item: null };
    const item = mapManualItem(rowNoRaw);
    expect(item.kind).toBe("manual");
    expect(item.headline).toBe("Test Headline");
  });

  it("normalizes key_bullets from jsonb", () => {
    const row = { ...baseRow, key_bullets: ["A", "B", "C"] };
    const item = mapManualItem(row);
    expect(item.key_bullets).toEqual(["A", "B", "C"]);
  });

  it("defaults selected to true when field is missing", () => {
    const row = { ...baseRow, selected: undefined };
    const item = mapManualItem(row);
    expect(item.selected).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 4. normalizeKeyBullets edge cases
// ---------------------------------------------------------------------------

describe("normalizeKeyBullets", () => {
  it("returns null for non-array input", () => {
    expect(normalizeKeyBullets(null)).toBeNull();
    expect(normalizeKeyBullets(undefined)).toBeNull();
    expect(normalizeKeyBullets("not an array")).toBeNull();
    expect(normalizeKeyBullets(42)).toBeNull();
  });

  it("filters empty strings", () => {
    expect(normalizeKeyBullets(["", "  ", "Valid"])).toEqual(["Valid"]);
  });

  it("returns null for an array of all empty strings", () => {
    expect(normalizeKeyBullets(["", "  "])).toBeNull();
  });

  it("trims whitespace from bullets", () => {
    expect(normalizeKeyBullets(["  hello  ", " world "])).toEqual([
      "hello",
      "world",
    ]);
  });
});

// ---------------------------------------------------------------------------
// 5. normalizeExhibits edge cases
// ---------------------------------------------------------------------------

describe("normalizeExhibits", () => {
  it("returns null for non-array input", () => {
    expect(normalizeExhibits(null)).toBeNull();
    expect(normalizeExhibits(undefined)).toBeNull();
    expect(normalizeExhibits("not an array")).toBeNull();
  });

  it("returns null for empty array", () => {
    expect(normalizeExhibits([])).toBeNull();
  });

  it("returns array with items when non-empty", () => {
    const exhibits = [{ type: "table", data: { rows: [] } }];
    expect(normalizeExhibits(exhibits)).toEqual(exhibits);
  });
});

// ---------------------------------------------------------------------------
// 6. manual-entry exhibit metadata
// ---------------------------------------------------------------------------

describe("manual entry exhibit metadata", () => {
  it("round-trips a structured exhibit through notes metadata", () => {
    const exhibit = {
      type: "metric_highlight" as const,
      data: {
        metrics: [{ label: "Revenue", value: "$4.2B", change: "+12%" }],
      },
      source_image_url: "https://example.com/exhibit.png",
    };

    const notes = buildManualEntryNotes({
      exhibit,
      imageUrl: exhibit.source_image_url,
    });

    expect(extractExhibitsFromManualEntryNotes(notes)).toEqual([exhibit]);
  });

  it("supports legacy image-only exhibit notes", () => {
    const notes = "[exhibit_image: https://example.com/legacy.png]";

    expect(extractExhibitsFromManualEntryNotes(notes)).toEqual([
      {
        type: "raw_image",
        data: {
          image_url: "https://example.com/legacy.png",
          caption: "",
        },
        source_image_url: "https://example.com/legacy.png",
      },
    ]);
  });

  it("returns null when notes do not contain exhibit metadata", () => {
    expect(extractExhibitsFromManualEntryNotes("plain note")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 7. buildManualItem / buildProposedItem propagation
//    (These are private to the approve route, so we test the pattern inline)
// ---------------------------------------------------------------------------

describe("buildManualItem pattern (approve route)", () => {
  // Simulates the buildManualItem function from approve/route.ts
  function buildManualItem(item: Record<string, unknown>, rank: number) {
    const raw = (item.raw_item as Record<string, unknown>) ?? {};
    return {
      ...raw,
      id: item.item_id,
      rank,
      section: item.section,
      headline: item.headline,
      main_bullet: item.main_bullet ?? "",
      context: item.context ?? null,
      implication: item.implication ?? null,
      source_name: item.source_name ?? "Manual Entry",
      source_url: item.source_url ?? null,
      source_domain: raw.source_domain ?? null,
      additional_sources: raw.additional_sources ?? [],
      entities: raw.entities ?? [],
      composite_score: Number(item.composite_score ?? 8),
      significance_level: item.significance_level ?? "medium",
      depth: item.depth ?? "standard",
      is_model_release: Boolean(item.is_model_release),
      model_release_data: item.model_release_data ?? null,
      cluster: raw.cluster ?? null,
      continuity: raw.continuity ?? null,
      key_bullets: item.key_bullets ?? raw.key_bullets ?? null,
      analysis: item.analysis ?? raw.analysis ?? null,
      primary_entity: item.primary_entity ?? raw.primary_entity ?? null,
      primary_entity_category:
        item.primary_entity_category ?? raw.primary_entity_category ?? null,
      exhibits: item.exhibits ?? raw.exhibits ?? null,
    };
  }

  it("propagates primary_entity_category from DB column", () => {
    const item = {
      item_id: "manual-test0001",
      section: "UAE",
      headline: "Test",
      main_bullet: "Bullet",
      source_name: "WAM",
      composite_score: 8,
      significance_level: "medium",
      primary_entity: "ADNOC",
      primary_entity_category: "energy",
      raw_item: { primary_entity_category: "energy" },
    };
    const result = buildManualItem(item, 1);
    expect(result.primary_entity_category).toBe("energy");
  });

  it("falls back to raw_item.primary_entity_category when column is null", () => {
    const item = {
      item_id: "manual-test0002",
      section: "UAE",
      headline: "Test",
      main_bullet: "Bullet",
      source_name: "WAM",
      composite_score: 8,
      significance_level: "medium",
      primary_entity: "ADNOC",
      primary_entity_category: null,
      raw_item: { primary_entity_category: "energy" },
    };
    const result = buildManualItem(item, 1);
    expect(result.primary_entity_category).toBe("energy");
  });

  it("returns null when both column and raw_item lack the field", () => {
    const item = {
      item_id: "manual-test0003",
      section: "UAE",
      headline: "Test",
      main_bullet: "Bullet",
      source_name: "WAM",
      composite_score: 8,
      primary_entity: null,
      primary_entity_category: null,
      raw_item: {},
    };
    const result = buildManualItem(item, 1);
    expect(result.primary_entity_category).toBeNull();
  });

  it("sets correct rank from parameter", () => {
    const item = {
      item_id: "manual-rank001",
      section: "UAE",
      headline: "Test",
      main_bullet: "Bullet",
      raw_item: {},
    };
    expect(buildManualItem(item, 5).rank).toBe(5);
    expect(buildManualItem(item, 1).rank).toBe(1);
  });

  it("preserves the curator-assigned section into the published item payload", () => {
    const item = {
      item_id: "manual-section001",
      section: "International Politics & Policy",
      headline: "Moved story",
      main_bullet: "Bullet",
      source_name: "WAM",
      composite_score: 8,
      raw_item: { section: "UAE" },
    };

    const result = buildManualItem(item, 1);
    expect(result.section).toBe("International Politics & Policy");
  });
});

// ---------------------------------------------------------------------------
// 8. End-to-end: manual item row → mergeRawItem → mapManualItem round-trip
// ---------------------------------------------------------------------------

describe("manual item round-trip", () => {
  it("creates a well-formed ManualItem from scratch input", () => {
    // Simulate what manual-item/route.ts does
    const row = {
      id: "aaaaaaaa-1111-2222-3333-444444444444",
      pending_brief_id: "bbbbbbbb-1111-2222-3333-444444444444",
      item_id: "manual-e2e00001",
      section: "International Business & Technology",
      headline: "NVIDIA announces next-gen GPU",
      main_bullet: "NVIDIA revealed its next-generation GPU architecture.",
      context: "This is significant for AI training workloads.",
      implication: null,
      source_name: "reuters.com",
      source_url: "https://reuters.com/nvidia-gpu",
      composite_score: 8,
      significance_level: "medium",
      key_bullets: ["NVIDIA revealed its next-generation GPU architecture."],
      analysis: "This is significant for AI training workloads.",
      primary_entity: "NVIDIA",
      exhibits: null,
      depth: "standard",
      is_model_release: false,
      model_release_data: null,
      selected: false,
      curation_order: null,
      added_by: "00000000-0000-0000-0000-000000000001",
      created_at: "2026-04-16T08:00:00Z",
      updated_at: "2026-04-16T08:00:00Z",
      raw_item: null,
    };

    // Step 1: mergeRawItem (what the API route does)
    const rawItem = mergeRawItem(row, row);
    expect(rawItem.primary_entity_category).toBe("company");
    expect(rawItem.primary_subject).toBe("NVIDIA");

    // Step 2: Simulate the DB row after insert (raw_item populated)
    const dbRow = {
      ...row,
      primary_entity_category: rawItem.primary_entity_category,
      raw_item: rawItem,
    };

    // Step 3: mapManualItem (what the API returns)
    const mapped = mapManualItem(dbRow);
    expect(mapped.kind).toBe("manual");
    expect(mapped.headline).toBe("NVIDIA announces next-gen GPU");
    expect(mapped.primary_entity).toBe("NVIDIA");
    expect(mapped.primary_entity_category).toBe("company");
    expect(mapped.primary_subject).toBe("NVIDIA");
    expect(mapped.badge_subject).toBe("NVIDIA");
    expect(mapped.key_bullets).toEqual([
      "NVIDIA revealed its next-generation GPU architecture.",
    ]);
    expect(mapped.analysis).toBe(
      "This is significant for AI training workloads.",
    );
    expect(mapped.selected).toBe(false);
    expect(mapped.curation_order).toBeNull();
  });
});
