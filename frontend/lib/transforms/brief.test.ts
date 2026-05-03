// @vitest-environment node

import { describe, expect, it } from "vitest";
import { transformBrief } from "@/lib/transforms/brief";
import type { RawPipelineBrief } from "@/lib/types/brief";

describe("transformBrief section preservation", () => {
  it("preserves edited item sections in the published brief output", () => {
    const rawBrief: RawPipelineBrief = {
      brief_metadata: {
        date: "2026-04-17",
        generated_at: "2026-04-17T08:00:00Z",
        total_items: 2,
        section_counts: {
          "International Politics & Policy": 1,
          "Model Releases & Technical Developments": 1,
        },
        lead_story_id: "2026-04-17-001",
      },
      items: [
        {
          id: "2026-04-17-001",
          rank: 1,
          section: "International Politics & Policy",
          headline: "UAE item moved to politics",
          source_domain: "example.com",
          source_name: "Example",
          source_url: "https://example.com/politics",
          additional_sources: [],
          main_bullet: "Main bullet",
          context: "Context",
          implication: "Implication",
          entities: [],
          composite_score: 9,
          significance_level: "high",
          cluster: null,
          continuity: null,
          is_model_release: false,
          model_release_data: null,
          depth: "standard",
          key_bullets: ["Main bullet"],
          analysis: "Analysis",
          primary_entity: "Example Entity",
          exhibits: null,
        },
        {
          id: "2026-04-17-002",
          rank: 2,
          section: "Model Releases & Technical Developments",
          headline: "Business item moved to models",
          source_domain: "example.com",
          source_name: "Example",
          source_url: "https://example.com/models",
          additional_sources: [],
          main_bullet: "Main bullet",
          context: "Context",
          implication: "Implication",
          entities: [],
          composite_score: 8,
          significance_level: "medium",
          cluster: null,
          continuity: null,
          is_model_release: true,
          model_release_data: null,
          depth: "standard",
          key_bullets: ["Main bullet"],
          analysis: "Analysis",
          primary_entity: "Model Vendor",
          exhibits: null,
        },
      ],
    };

    const brief = transformBrief(rawBrief);

    expect(brief.items[0].section).toBe("International Politics & Policy");
    expect(brief.items[1].section).toBe("Model Releases & Technical Developments");
    expect(
      brief.sections.find((section) => section.name === "International Politics & Policy")?.items[0]?.headline
    ).toBe("UAE item moved to politics");
    expect(
      brief.sections.find((section) => section.name === "Model Releases & Technical Developments")?.items[0]?.headline
    ).toBe("Business item moved to models");
  });
});

// Phase 5 (2026-04-17): sections should preserve the curator's cross-section
// ordering, not be forced into canonical SECTION_ORDER. These tests lock the
// new behavior so we don't regress into "UAE is always first" again.
describe("transformBrief curator-ordering preservation", () => {
  function mkItem(id: string, section: string, rank: number) {
    return {
      id,
      rank,
      section,
      headline: `Headline ${id}`,
      source_domain: "example.com",
      source_name: "Example",
      source_url: "https://example.com/" + id,
      additional_sources: [],
      main_bullet: "Main bullet",
      context: null,
      implication: null,
      entities: [],
      composite_score: 7,
      significance_level: "medium" as const,
      cluster: null,
      continuity: null,
      is_model_release: false,
      model_release_data: null,
      depth: "standard" as const,
      key_bullets: ["Main bullet"],
      analysis: null,
      primary_entity: null,
      exhibits: null,
    };
  }

  it("orders sections by the curator's first-item-in-section appearance", () => {
    // Curator ordered: Models → UAE → Politics → UAE → Business.
    // Published brief should render sections in that sequence (with two
    // separate UAE blocks), NOT forced into canonical UAE-first order.
    const rawBrief: RawPipelineBrief = {
      brief_metadata: {
        date: "2026-04-17",
        generated_at: "2026-04-17T08:00:00Z",
        total_items: 5,
        section_counts: {},
        lead_story_id: "a",
      },
      items: [
        mkItem("a", "Model Releases & Technical Developments", 1),
        mkItem("b", "UAE", 2),
        mkItem("c", "International Politics & Policy", 3),
        mkItem("d", "UAE", 4),
        mkItem("e", "International Business & Technology", 5),
      ],
    };

    const brief = transformBrief(rawBrief);
    const sectionNames = brief.sections.map((s) => s.name);

    // Models leads, UAE appears twice (split by Politics), Business last.
    expect(sectionNames).toEqual([
      "Model Releases & Technical Developments",
      "UAE",
      "International Politics & Policy",
      "UAE",
      "International Business & Technology",
    ]);
    // Each section block carries exactly the right items in order.
    expect(brief.sections[0].items.map((i) => i.id)).toEqual(["a"]);
    expect(brief.sections[1].items.map((i) => i.id)).toEqual(["b"]);
    expect(brief.sections[2].items.map((i) => i.id)).toEqual(["c"]);
    expect(brief.sections[3].items.map((i) => i.id)).toEqual(["d"]);
    expect(brief.sections[4].items.map((i) => i.id)).toEqual(["e"]);
  });

  it("collapses adjacent same-section items into one block", () => {
    // Curator ordered: UAE → UAE → UAE → Models → UAE.
    // First three UAE items form one block; Models in the middle breaks
    // the sequence, so the last UAE item starts a new block.
    const rawBrief: RawPipelineBrief = {
      brief_metadata: {
        date: "2026-04-17",
        generated_at: "2026-04-17T08:00:00Z",
        total_items: 5,
        section_counts: {},
        lead_story_id: "a",
      },
      items: [
        mkItem("a", "UAE", 1),
        mkItem("b", "UAE", 2),
        mkItem("c", "UAE", 3),
        mkItem("d", "Model Releases & Technical Developments", 4),
        mkItem("e", "UAE", 5),
      ],
    };

    const brief = transformBrief(rawBrief);
    expect(brief.sections.map((s) => s.name)).toEqual([
      "UAE",
      "Model Releases & Technical Developments",
      "UAE",
    ]);
    expect(brief.sections[0].items.map((i) => i.id)).toEqual(["a", "b", "c"]);
    expect(brief.sections[1].items.map((i) => i.id)).toEqual(["d"]);
    expect(brief.sections[2].items.map((i) => i.id)).toEqual(["e"]);
  });

  it("returns empty sections array on empty input", () => {
    const rawBrief: RawPipelineBrief = {
      brief_metadata: {
        date: "2026-04-17",
        generated_at: "2026-04-17T08:00:00Z",
        total_items: 0,
        section_counts: {},
        lead_story_id: "",
      },
      items: [],
    };
    expect(transformBrief(rawBrief).sections).toEqual([]);
  });
});
