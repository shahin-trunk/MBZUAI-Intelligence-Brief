"use client";

import type { Brief, BriefItem, ExhibitData } from "@/lib/types/brief";
import { TestCardReader } from "./TestCardReader";

/* ─── Helper to build a BriefItem with defaults ────────────────────── */

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

/* ─── 8 Test Items ───────────────────────────────────────────────────── */

const TEST_ITEMS: BriefItem[] = [
  // 1. ADNOC — no exhibit, Tier 1 logo
  makeItem("2026-04-09-001", "UAE", {
    headline: "ADNOC Launches $2B AI-Driven Drilling Optimization Program",
    primary_entity: "ADNOC",
    source_name: "WAM",
    source_url: "https://wam.ae/en/article/123",
    significance: "high",
    composite_score: 9.2,
    key_bullets: [
      "ADNOC will deploy AI across 40+ offshore drilling platforms by end of 2027",
      "Partnership with Halliburton and G42 to develop predictive maintenance models",
      "Expected to reduce unplanned downtime by 35% and save $400M annually",
    ],
    analysis:
      "ADNOC's move signals a significant acceleration in the UAE's industrial AI adoption. The partnership with G42 is particularly noteworthy as it deepens the sovereign AI ecosystem's ties to the energy sector. This program is the largest single AI deployment in the Gulf energy industry to date, surpassing Saudi Aramco's announced but smaller-scale digital twin initiative. For MBZUAI, this presents potential research collaboration opportunities in predictive analytics and industrial AI applications.",
    entities: ["ADNOC", "G42", "Halliburton"],
  }),

  // 2. Khalifa University — benchmark table exhibit
  makeItem("2026-04-09-002", "Regional Research & Academic Events", {
    headline: "Khalifa University Team Achieves State-of-the-Art in Arabic NLP Benchmarks",
    primary_entity: "Khalifa University",
    source_name: "Khalifa University News",
    source_url: "https://ku.ac.ae/news/arabic-nlp",
    significance: "high",
    composite_score: 8.8,
    key_bullets: [
      "New ArabicBERT-XL model tops all standard Arabic NLP benchmarks",
      "Joint work with QCRI researchers; trained on 2TB Arabic web corpus",
    ],
    analysis:
      "This achievement positions Khalifa University as a serious competitor in Arabic AI research, a domain MBZUAI has been building toward with its own Arabic LLM efforts. The collaboration with QCRI suggests a strengthening Gulf research corridor that could either complement or compete with MBZUAI's initiatives. The 2TB training corpus is notable — comparable to what was previously only achievable by well-funded industry labs.",
    entities: ["Khalifa University", "QCRI"],
    exhibits: [
      {
        type: "benchmark_table",
        data: {
          title: "Arabic NLP Benchmark Results",
          columns: ["ArabicBERT-XL", "JAIS-13B", "AraBERT-v2"],
          rows: [
            { benchmark: "ArSEL (Sentiment)", scores: { "ArabicBERT-XL": "94.2%", "JAIS-13B": "91.8%", "AraBERT-v2": "89.1%" } },
            { benchmark: "AQAD (QA)", scores: { "ArabicBERT-XL": "87.6%", "JAIS-13B": "85.2%", "AraBERT-v2": "82.4%" } },
            { benchmark: "ANERCorp (NER)", scores: { "ArabicBERT-XL": "92.1%", "JAIS-13B": "90.5%", "AraBERT-v2": "88.7%" } },
            { benchmark: "ASTD (Dialect)", scores: { "ArabicBERT-XL": "78.9%", "JAIS-13B": "76.3%", "AraBERT-v2": "71.2%" } },
          ],
        },
      } satisfies ExhibitData,
    ],
  }),

  // 3. Mistral — metric highlight exhibit
  makeItem("2026-04-09-003", "Model Releases & Technical Developments", {
    headline: "Mistral Releases Compact Multilingual Model Targeting Emerging Markets",
    primary_entity: "Mistral",
    source_name: "Mistral Blog",
    source_url: "https://mistral.ai/news/multilingual-compact",
    significance: "medium",
    composite_score: 7.8,
    key_bullets: [
      "4B-parameter model with strong Arabic and Hindi performance",
      "Priced at $0.016 per 1K characters — targeting cost-sensitive deployments",
      "Supports 9 languages with single-model architecture",
    ],
    analysis:
      "Mistral's compact multilingual model directly targets the Gulf market's need for affordable Arabic-capable AI. At 4B parameters it can run on-device, making it attractive for government deployments where data sovereignty matters. This puts competitive pressure on JAIS and other Arabic-focused models from the region. The pricing model is aggressive and could undercut local offerings.",
    entities: ["Mistral"],
    is_model_release: true,
    exhibits: [
      {
        type: "metric_highlight",
        data: {
          metrics: [
            { label: "Parameters", value: "4B", change: "-75% vs 7B" },
            { label: "Price", value: "$0.016", change: "per 1K chars" },
            { label: "Languages", value: "9" },
          ],
        },
      } satisfies ExhibitData,
    ],
  }),

  // 4. JAZARI Institute — unknown entity, fallback university icon
  makeItem("2026-04-09-004", "Regional Research & Academic Events", {
    headline: "JAZARI Institute Opens First Robotics Research Lab in Sharjah Free Zone",
    primary_entity: "JAZARI Institute",
    source_name: "Gulf News",
    source_url: "https://gulfnews.com/tech/jazari-robotics-lab",
    significance: "medium",
    composite_score: 6.9,
    key_bullets: [
      "30,000 sq ft facility focused on humanoid robotics and industrial automation",
      "Initial cohort of 12 PhD researchers recruited from regional universities",
    ],
    analysis:
      "The JAZARI Institute is a new entrant in the Gulf research landscape, positioning itself in the robotics niche that remains relatively uncrowded compared to AI/ML. Its location in Sharjah Free Zone suggests favorable regulatory and cost conditions. While not a direct competitor to MBZUAI, the institute's recruitment of regional PhD talent could create competition for the same candidate pool.",
    entities: ["JAZARI Institute"],
  }),

  // 5. Unknown entity, no category match — generic fallback
  makeItem("2026-04-09-005", "International Business & Technology", {
    headline: "NovaTech Quantum Unveils Commercial Quantum Key Distribution Network",
    primary_entity: "NovaTech Quantum",
    source_name: "TechCrunch",
    source_url: "https://techcrunch.com/novatech-qkd",
    significance: "low",
    composite_score: 5.4,
    key_bullets: [
      "First commercially available QKD network targeting financial institutions",
      "Partnership with three Gulf banks for pilot deployment in Q3 2026",
    ],
    analysis:
      "NovaTech Quantum's commercial QKD network represents an early step toward practical quantum communications in the Gulf. While not directly related to AI, quantum-safe encryption is increasingly relevant to the region's sovereign technology agenda. The banking sector pilot could accelerate adoption if successful.",
    entities: ["NovaTech Quantum"],
  }),

  // 6. Timeline exhibit
  makeItem("2026-04-09-006", "International Politics & Policy", {
    headline: "EU AI Act Enforcement Timeline Accelerates After Commission Review",
    primary_entity: "European Commission",
    source_name: "Reuters",
    source_url: "https://reuters.com/technology/eu-ai-act-timeline",
    significance: "high",
    composite_score: 8.1,
    key_bullets: [
      "High-risk AI system requirements now effective 6 months earlier than planned",
      "New guidance specifically addresses foundation model providers",
      "Gulf AI companies exporting to EU must comply by January 2027",
    ],
    analysis:
      "The accelerated EU AI Act timeline has direct implications for Gulf-based AI companies and research institutions that collaborate with European partners. MBZUAI's research partnerships with European universities may need compliance reviews. The foundation model provisions are particularly relevant given the region's investments in large language models.",
    entities: ["European Commission"],
    exhibits: [
      {
        type: "timeline",
        data: {
          events: [
            { date: "2026-02-01", description: "Commission publishes accelerated implementation schedule" },
            { date: "2026-04-15", description: "Public comment period closes on foundation model guidelines" },
            { date: "2026-07-01", description: "High-risk AI system registration requirement takes effect" },
            { date: "2027-01-01", description: "Full enforcement begins for all AI providers serving EU market" },
          ],
        },
      } satisfies ExhibitData,
    ],
  }),

  // 7. Raw image exhibit
  makeItem("2026-04-09-007", "International Business & Technology", {
    headline: "AWS Opens Dedicated Sovereign Cloud Region in Bahrain",
    primary_entity: "AWS",
    source_name: "AWS Blog",
    source_url: "https://aws.amazon.com/blogs/sovereign-cloud-bahrain",
    significance: "medium",
    composite_score: 7.2,
    key_bullets: [
      "First AWS sovereign cloud in the Middle East with full data residency guarantees",
      "Includes dedicated AI/ML infrastructure with NVIDIA H100 clusters",
    ],
    analysis:
      "AWS's sovereign cloud in Bahrain directly competes with G42's Artemis cloud and Microsoft's UAE sovereign offerings. The inclusion of dedicated AI infrastructure signals that cloud providers see the Gulf as a key market for sovereign AI workloads. This could benefit MBZUAI by providing additional compute options but also normalizes the idea that sovereign AI doesn't require local providers.",
    entities: ["AWS"],
    exhibits: [
      {
        type: "raw_image",
        data: {
          image_url: "https://placehold.co/600x300/1a1a2e/e0e0e0?text=AWS+Sovereign+Cloud+Architecture",
          caption: "AWS Sovereign Cloud — Bahrain Region Architecture Overview",
        },
      } satisfies ExhibitData,
    ],
  }),

  // 8. Multiple exhibits (benchmark table + metric highlight)
  makeItem("2026-04-09-008", "Model Releases & Technical Developments", {
    headline: "DeepSeek Releases V3-Mini with Breakthrough Efficiency on Reasoning Tasks",
    primary_entity: "DeepSeek",
    source_name: "DeepSeek Blog",
    source_url: "https://deepseek.com/blog/v3-mini",
    significance: "high",
    composite_score: 8.9,
    key_bullets: [
      "8B-parameter model matching GPT-4o on math and coding benchmarks",
      "Mixture-of-experts architecture with only 2B active parameters per query",
      "Open-weight release under Apache 2.0 license",
    ],
    analysis:
      "DeepSeek V3-Mini represents a significant efficiency breakthrough — matching frontier model performance at a fraction of the compute cost. The open-weight release under Apache 2.0 makes it immediately usable for research and commercial applications. This is directly relevant to MBZUAI's work on efficient model architectures and could serve as a strong baseline for the university's own research programs.",
    entities: ["DeepSeek"],
    is_model_release: true,
    exhibits: [
      {
        type: "benchmark_table",
        data: {
          title: "Reasoning Benchmark Comparison",
          columns: ["V3-Mini (8B)", "GPT-4o", "Claude Sonnet"],
          rows: [
            { benchmark: "MATH-500", scores: { "V3-Mini (8B)": "89.2%", "GPT-4o": "90.1%", "Claude Sonnet": "88.7%" } },
            { benchmark: "HumanEval", scores: { "V3-Mini (8B)": "84.6%", "GPT-4o": "86.2%", "Claude Sonnet": "85.1%" } },
            { benchmark: "GPQA Diamond", scores: { "V3-Mini (8B)": "61.3%", "GPT-4o": "63.8%", "Claude Sonnet": "59.4%" } },
          ],
        },
      } satisfies ExhibitData,
      {
        type: "metric_highlight",
        data: {
          metrics: [
            { label: "Total Params", value: "8B" },
            { label: "Active Params", value: "2B", change: "per query" },
            { label: "License", value: "Apache 2.0" },
          ],
        },
      } satisfies ExhibitData,
    ],
  }),
];

/* ─── Build Brief object from test items ─────────────────────────── */

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
  ].map((name) => ({
    name,
    items: sectionMap.get(name) ?? [],
  })).filter((s) => s.items.length > 0);

  return {
    brief_date: "2026-04-09",
    generated_at: new Date().toISOString(),
    item_count: TEST_ITEMS.length,
    sources_consulted: 8,
    items_reviewed: 45,
    pipeline_cost_usd: 0,
    items: TEST_ITEMS,
    sections,
    metadata: {
      pipeline_version: "test",
    },
  };
}

/* ─── Page Component ─────────────────────────────────────────────────── */

export default function TestCardsPage() {
  const testBrief = buildTestBrief();

  return (
    <div className="min-h-dvh bg-[#0a0a0a] text-white">
      <TestCardReader brief={testBrief} />
    </div>
  );
}
