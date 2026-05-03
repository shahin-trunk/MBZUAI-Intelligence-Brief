import { describe, expect, it } from "vitest";
import { inferEntityCategory } from "@/lib/entity-category";

describe("inferEntityCategory", () => {
  it("prefers the authoritative logo category", () => {
    expect(
      inferEntityCategory(
        {
          headline: "OpenAI expands enterprise offering",
          section: "International Business & Technology",
          source_name: "FT Briefing",
          source_domain: "ft.com",
          primary_entity: "OpenAI",
          primary_entity_category: undefined,
          is_model_release: false,
          model_release_data: undefined,
          entities: [],
        },
        { authoritativeCategory: "company" }
      )
    ).toBe("company");
  });

  it("uses the pipeline category when available", () => {
    expect(
      inferEntityCategory({
        headline: "Khalifa University opens new center",
        section: "Regional Research & Academic Events",
        source_name: "Middle East AI News",
        source_domain: "ku.ac.ae",
        primary_entity: "Khalifa University",
        primary_entity_category: "university",
        is_model_release: false,
        model_release_data: undefined,
        entities: [],
      })
    ).toBe("university");
  });

  it("infers defense entities from military signals", () => {
    expect(
      inferEntityCategory({
        headline: "US blockade of Iranian ports holds through first 24 hours",
        section: "International Politics & Policy",
        source_name: "WSJ Briefing",
        source_domain: "wsj.com",
        primary_entity: "CENTCOM",
        primary_entity_category: undefined,
        is_model_release: false,
        model_release_data: undefined,
        entities: ["CENTCOM", "Iran"],
      })
    ).toBe("defense");
  });

  it("infers government from leadership titles", () => {
    expect(
      inferEntityCategory({
        headline: "President meets delegation in Abu Dhabi",
        section: "UAE",
        source_name: "The National",
        source_domain: "thenationalnews.com",
        primary_entity: "H.H. Sheikh Khaled bin Mohamed bin Zayed Al Nahyan",
        primary_entity_category: undefined,
        is_model_release: false,
        model_release_data: undefined,
        entities: [],
      })
    ).toBe("government");
  });

  it("infers finance entities from investment signals", () => {
    expect(
      inferEntityCategory({
        headline: "Mubadala Capital joins strategic funding round",
        section: "International Business & Technology",
        source_name: "Bloomberg",
        source_domain: "bloomberg.com",
        primary_entity: "Mubadala Capital",
        primary_entity_category: undefined,
        is_model_release: false,
        model_release_data: undefined,
        entities: [],
      })
    ).toBe("finance");
  });

  it("infers country entities from canonical names", () => {
    expect(
      inferEntityCategory({
        headline: "Iran says talks will continue next week",
        section: "International Politics & Policy",
        source_name: "Reuters",
        source_domain: "reuters.com",
        primary_entity: "Iran",
        primary_entity_category: undefined,
        is_model_release: false,
        model_release_data: undefined,
        entities: [],
      })
    ).toBe("country");
  });

  it("falls back to company for uncategorized named entities", () => {
    expect(
      inferEntityCategory({
        headline: "Startup announces new partnership",
        section: "International Business & Technology",
        source_name: "TechCrunch",
        source_domain: "techcrunch.com",
        primary_entity: "Reflection AI",
        primary_entity_category: undefined,
        is_model_release: false,
        model_release_data: undefined,
        entities: [],
      })
    ).toBe("company");
  });
});
