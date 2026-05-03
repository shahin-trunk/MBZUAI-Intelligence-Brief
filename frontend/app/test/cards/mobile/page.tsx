"use client";

import type { Brief, BriefItem, ExhibitData } from "@/lib/types/brief";
import { TestCardReader } from "../TestCardReader";

/* ─── Same 8 test items as /test/cards ───────────────────────────── */

function makeItem(
  id: string,
  section: string,
  overrides: Partial<BriefItem> & { headline: string },
): BriefItem {
  return {
    id,
    headline: overrides.headline,
    main_bullet: "",
    source_name: overrides.source_name ?? "Test Source",
    source_url: overrides.source_url ?? "https://example.com",
    significance: overrides.significance ?? "medium",
    composite_score: overrides.composite_score ?? 7.5,
    topic_relevance: 8,
    news_significance: 7,
    is_continuity: false,
    section,
    rank: parseInt(id.split("-").pop() ?? "1"),
    depth: "full",
    entities: overrides.entities ?? [],
    additional_sources: [],
    is_model_release: overrides.is_model_release ?? false,
    key_bullets: overrides.key_bullets,
    analysis: overrides.analysis,
    primary_entity: overrides.primary_entity,
    exhibits: overrides.exhibits,
    audio_url: undefined,
  };
}

const TEST_ITEMS: BriefItem[] = [
  makeItem("2026-04-09-001", "UAE", {
    headline: "ADNOC Launches $2B AI-Driven Drilling Optimization Program",
    primary_entity: "ADNOC",
    source_name: "WAM",
    significance: "high",
    composite_score: 9.2,
    key_bullets: [
      "ADNOC will deploy AI across 40+ offshore drilling platforms by end of 2027",
      "Partnership with Halliburton and G42 to develop predictive maintenance models",
      "Expected to reduce unplanned downtime by 35% and save $400M annually",
    ],
    analysis: "ADNOC's move signals a significant acceleration in the UAE's industrial AI adoption. The partnership with G42 deepens the sovereign AI ecosystem's ties to the energy sector.",
    entities: ["ADNOC", "G42"],
  }),
  makeItem("2026-04-09-002", "Regional Research & Academic Events", {
    headline: "Khalifa University Team Achieves State-of-the-Art in Arabic NLP Benchmarks",
    primary_entity: "Khalifa University",
    source_name: "Khalifa University News",
    significance: "high",
    key_bullets: [
      "New ArabicBERT-XL model tops all standard Arabic NLP benchmarks",
      "Joint work with QCRI researchers; trained on 2TB Arabic web corpus",
    ],
    analysis: "This positions Khalifa University as a serious competitor in Arabic AI research.",
    entities: ["Khalifa University", "QCRI"],
    exhibits: [{
      type: "benchmark_table",
      data: {
        title: "Arabic NLP Benchmark Results",
        columns: ["ArabicBERT-XL", "JAIS-13B", "AraBERT-v2"],
        rows: [
          { benchmark: "ArSEL", scores: { "ArabicBERT-XL": "94.2%", "JAIS-13B": "91.8%", "AraBERT-v2": "89.1%" } },
          { benchmark: "AQAD", scores: { "ArabicBERT-XL": "87.6%", "JAIS-13B": "85.2%", "AraBERT-v2": "82.4%" } },
          { benchmark: "ANERCorp", scores: { "ArabicBERT-XL": "92.1%", "JAIS-13B": "90.5%", "AraBERT-v2": "88.7%" } },
        ],
      },
    } satisfies ExhibitData],
  }),
  makeItem("2026-04-09-003", "Model Releases & Technical Developments", {
    headline: "Mistral Releases Compact Multilingual Model Targeting Emerging Markets",
    primary_entity: "Mistral",
    source_name: "Mistral Blog",
    key_bullets: [
      "4B-parameter model with strong Arabic and Hindi performance",
      "Priced at $0.016 per 1K characters",
    ],
    analysis: "Mistral's compact model directly targets the Gulf market's need for affordable Arabic-capable AI.",
    entities: ["Mistral"],
    is_model_release: true,
    exhibits: [{
      type: "metric_highlight",
      data: { metrics: [{ label: "Parameters", value: "4B" }, { label: "Price", value: "$0.016" }, { label: "Languages", value: "9" }] },
    } satisfies ExhibitData],
  }),
  makeItem("2026-04-09-004", "Regional Research & Academic Events", {
    headline: "JAZARI Institute Opens First Robotics Research Lab in Sharjah Free Zone",
    primary_entity: "JAZARI Institute",
    source_name: "Gulf News",
    key_bullets: [
      "30,000 sq ft facility focused on humanoid robotics and industrial automation",
      "Initial cohort of 12 PhD researchers recruited from regional universities",
    ],
    analysis: "A new entrant in the Gulf research landscape positioning itself in the robotics niche.",
    entities: ["JAZARI Institute"],
  }),
  makeItem("2026-04-09-005", "International Business & Technology", {
    headline: "NovaTech Quantum Unveils Commercial Quantum Key Distribution Network",
    primary_entity: "NovaTech Quantum",
    source_name: "TechCrunch",
    significance: "low",
    composite_score: 5.4,
    key_bullets: [
      "First commercially available QKD network targeting financial institutions",
      "Partnership with three Gulf banks for pilot in Q3 2026",
    ],
    analysis: "An early step toward practical quantum communications in the Gulf.",
    entities: ["NovaTech Quantum"],
  }),
  makeItem("2026-04-09-006", "International Politics & Policy", {
    headline: "EU AI Act Enforcement Timeline Accelerates After Commission Review",
    primary_entity: "European Commission",
    source_name: "Reuters",
    significance: "high",
    key_bullets: [
      "High-risk AI system requirements now effective 6 months earlier than planned",
      "Gulf AI companies exporting to EU must comply by January 2027",
    ],
    analysis: "The accelerated timeline has direct implications for Gulf-based AI companies and research institutions.",
    entities: ["European Commission"],
    exhibits: [{
      type: "timeline",
      data: {
        events: [
          { date: "2026-02-01", description: "Commission publishes accelerated schedule" },
          { date: "2026-04-15", description: "Public comment period closes" },
          { date: "2026-07-01", description: "High-risk registration takes effect" },
          { date: "2027-01-01", description: "Full enforcement begins" },
        ],
      },
    } satisfies ExhibitData],
  }),
  makeItem("2026-04-09-007", "International Business & Technology", {
    headline: "AWS Opens Dedicated Sovereign Cloud Region in Bahrain",
    primary_entity: "AWS",
    source_name: "AWS Blog",
    key_bullets: [
      "First AWS sovereign cloud in the Middle East with full data residency guarantees",
      "Includes dedicated AI/ML infrastructure with NVIDIA H100 clusters",
    ],
    analysis: "AWS's sovereign cloud directly competes with G42's Artemis cloud and Microsoft's UAE offerings.",
    entities: ["AWS"],
    exhibits: [{
      type: "raw_image",
      data: {
        image_url: "https://placehold.co/600x300/1a1a2e/e0e0e0?text=AWS+Sovereign+Cloud",
        caption: "AWS Sovereign Cloud — Bahrain Region",
      },
    } satisfies ExhibitData],
  }),
  makeItem("2026-04-09-008", "Model Releases & Technical Developments", {
    headline: "DeepSeek Releases V3-Mini with Breakthrough Efficiency on Reasoning Tasks",
    primary_entity: "DeepSeek",
    source_name: "DeepSeek Blog",
    significance: "high",
    key_bullets: [
      "8B-parameter model matching GPT-4o on math and coding benchmarks",
      "Open-weight release under Apache 2.0 license",
    ],
    analysis: "DeepSeek V3-Mini represents a significant efficiency breakthrough at a fraction of the compute cost.",
    entities: ["DeepSeek"],
    is_model_release: true,
    exhibits: [
      {
        type: "benchmark_table",
        data: {
          title: "Reasoning Benchmarks",
          columns: ["V3-Mini", "GPT-4o", "Sonnet"],
          rows: [
            { benchmark: "MATH-500", scores: { "V3-Mini": "89.2%", "GPT-4o": "90.1%", "Sonnet": "88.7%" } },
            { benchmark: "HumanEval", scores: { "V3-Mini": "84.6%", "GPT-4o": "86.2%", "Sonnet": "85.1%" } },
          ],
        },
      } satisfies ExhibitData,
      {
        type: "metric_highlight",
        data: { metrics: [{ label: "Total Params", value: "8B" }, { label: "Active", value: "2B" }, { label: "License", value: "Apache 2.0" }] },
      } satisfies ExhibitData,
    ],
  }),
];

function buildTestBrief(): Brief {
  const sectionMap = new Map<string, BriefItem[]>();
  for (const item of TEST_ITEMS) {
    const items = sectionMap.get(item.section) ?? [];
    items.push(item);
    sectionMap.set(item.section, items);
  }

  const sections = [
    "UAE",
    "Regional Research & Academic Events",
    "International Politics & Policy",
    "International Business & Technology",
    "Model Releases & Technical Developments",
  ].map((name) => ({ name, items: sectionMap.get(name) ?? [] }))
    .filter((s) => s.items.length > 0);

  return {
    brief_date: "2026-04-09",
    generated_at: new Date().toISOString(),
    item_count: TEST_ITEMS.length,
    sources_consulted: 8,
    items_reviewed: 45,
    pipeline_cost_usd: 0,
    items: TEST_ITEMS,
    sections,
    metadata: { pipeline_version: "test" },
  };
}

export default function MobileTestCardsPage() {
  const testBrief = buildTestBrief();
  return <TestCardReader brief={testBrief} />;
}
