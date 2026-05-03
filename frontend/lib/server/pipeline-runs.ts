import "server-only";

import { promises as fs } from "fs";
import path from "path";

import type { AdminPipelineRun } from "@/lib/types/admin";
import type {
  EnrichmentItem,
  EnrichmentSummary,
  EnrichedSource,
  EnrichedFacts,
  EnrichmentJudgeResult,
} from "@/lib/types/enrichment";

type JsonObject = Record<string, unknown>;

const OUTPUT_DIR_CANDIDATES = [
  path.resolve(process.cwd(), "backend", "output"),
  path.resolve(process.cwd(), "..", "backend", "output"),
];
let outputDirPromise: Promise<string | null> | null = null;
const ENABLE_LOCAL_PIPELINE_HYDRATION =
  process.env.NODE_ENV !== "production" ||
  process.env.ENABLE_LOCAL_PIPELINE_HYDRATION === "1";

async function findOutputDir(): Promise<string | null> {
  if (!ENABLE_LOCAL_PIPELINE_HYDRATION) {
    return null;
  }

  if (outputDirPromise) {
    return outputDirPromise;
  }

  outputDirPromise = (async () => {
    for (const candidate of OUTPUT_DIR_CANDIDATES) {
      try {
        const stat = await fs.stat(candidate);
        if (stat.isDirectory()) {
          return candidate;
        }
      } catch {
        // Try the next candidate.
      }
    }
    return null;
  })();

  return outputDirPromise;
}

async function readJsonFile(
  outputDir: string | null,
  filename: string
): Promise<JsonObject | unknown[] | null> {
  if (!outputDir) return null;

  try {
    const text = await fs.readFile(path.join(outputDir, filename), "utf8");
    return JSON.parse(text) as JsonObject | unknown[];
  } catch {
    return null;
  }
}

async function readArtifactMtimes(
  outputDir: string | null,
  runDate: string
): Promise<number[]> {
  if (!outputDir) return [];

  const filenames = [
    `collection_log_${runDate}.json`,
    `scout_output_raw_${runDate}.json`,
    `scout_output_${runDate}.json`,
    `content_filter_output_${runDate}.json`,
    `gatekeeper_output_${runDate}.json`,
    `ghostwriter_output_${runDate}.json`,
    `editor_output_${runDate}.json`,
    `brief_${runDate}.json`,
    `pipeline_stats_${runDate}.json`,
  ];

  const stats = await Promise.all(
    filenames.map(async (filename) => {
      try {
        const stat = await fs.stat(path.join(outputDir, filename));
        return stat.mtimeMs;
      } catch {
        return null;
      }
    })
  );

  return stats.filter((value): value is number => value !== null);
}

function getNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function getObject(value: unknown): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : null;
}

function countBriefItems(brief: JsonObject | unknown[] | null): number | null {
  if (!brief || Array.isArray(brief)) return null;

  const items = Array.isArray(brief.items) ? brief.items : null;
  if (!items) return null;
  return items.reduce((count, item) => {
    const entry = getObject(item);
    const isPlaceholder = entry?.is_placeholder === true || entry?.depth === "placeholder";
    return count + (isPlaceholder ? 0 : 1);
  }, 0);
}

function countArrayItems(data: JsonObject | unknown[] | null): number | null {
  return Array.isArray(data) ? data.length : null;
}

function countContentFilterKept(data: JsonObject | unknown[] | null): number | null {
  if (!data || Array.isArray(data)) return null;

  if (typeof data.news_count === "number") {
    return data.news_count;
  }

  const verdicts = Array.isArray(data.verdicts) ? data.verdicts : [];
  return verdicts.reduce((count, verdict) => {
    const entry = getObject(verdict);
    return count + (entry?.keep === true ? 1 : 0);
  }, 0);
}

function countGatekeeperSelected(data: JsonObject | unknown[] | null): number | null {
  if (!data || Array.isArray(data)) return null;
  return Array.isArray(data.selected) ? data.selected.length : null;
}

function readMetaGeneratedAt(brief: JsonObject | unknown[] | null): string | null {
  if (!brief || Array.isArray(brief)) return null;
  return getString(getObject(brief.brief_metadata)?.generated_at);
}

function normalizeSourceErrors(value: unknown): Record<string, string> | null {
  const obj = getObject(value);
  if (!obj) return null;

  const entries = Object.entries(obj).filter(
    ([key, message]) => key && typeof message === "string"
  );
  return entries.length > 0
    ? (Object.fromEntries(entries) as Record<string, string>)
    : null;
}

function normalizeItemsPerSource(value: unknown): Record<string, number> | null {
  const obj = getObject(value);
  if (!obj) return null;

  const entries = Object.entries(obj).filter(
    ([key, count]) => key && typeof count === "number" && Number.isFinite(count)
  );
  return entries.length > 0
    ? (Object.fromEntries(entries) as Record<string, number>)
    : null;
}

function normalizeCost(
  stats: JsonObject | null,
  row: JsonObject
): number | null {
  const statsCost = getNumber(stats?.total_cost_usd);
  if (statsCost !== null) return statsCost;

  const dbCost =
    getNumber(row.total_cost_usd) ??
    getNumber(row.total_cost);

  if (dbCost === 0) {
    return null;
  }
  return dbCost;
}

function normalizePipelineCounts(counts: {
  items_collected: number | null;
  items_after_triage: number | null;
  items_after_date_filter: number | null;
  items_after_dedup: number | null;
  items_after_content_filter: number | null;
  items_after_gatekeeper: number | null;
  items_in_final_brief: number | null;
}): typeof counts {
  const normalized = { ...counts };
  const candidateFlowOrder: Array<keyof typeof normalized> = [
    "items_after_triage",
    "items_after_date_filter",
    "items_after_dedup",
    "items_after_content_filter",
    "items_after_gatekeeper",
    "items_in_final_brief",
  ];

  let ceiling: number | null = null;
  for (const key of candidateFlowOrder) {
    const value = normalized[key];
    if (value === null) {
      continue;
    }
    if (ceiling !== null && value > ceiling) {
      normalized[key] = ceiling;
      continue;
    }
    ceiling = normalized[key];
  }

  return normalized;
}

export async function hydratePipelineRun(rawRow: JsonObject): Promise<AdminPipelineRun> {
  const runDate = getString(rawRow.run_date) ?? "";
  const outputDir = await findOutputDir();

  const [stats, collection, triage, rawPool, postFilter, contentFilter, gatekeeper, brief, droppedByDate, mtimes] =
    await Promise.all([
      readJsonFile(outputDir, `pipeline_stats_${runDate}.json`),
      readJsonFile(outputDir, `collection_log_${runDate}.json`),
      readJsonFile(outputDir, `triage_output_${runDate}.json`),
      readJsonFile(outputDir, `scout_output_raw_${runDate}.json`),
      readJsonFile(outputDir, `scout_output_${runDate}.json`),
      readJsonFile(outputDir, `content_filter_output_${runDate}.json`),
      readJsonFile(outputDir, `gatekeeper_output_${runDate}.json`),
      readJsonFile(outputDir, `brief_${runDate}.json`),
      readJsonFile(outputDir, `dropped_by_date_${runDate}.json`),
      readArtifactMtimes(outputDir, runDate),
    ]);

  const collectionObj = getObject(collection);
  const triageObj = getObject(triage);
  const statsObj = getObject(stats);
  const droppedByDateObj = getObject(droppedByDate);
  const collectionSources = Array.isArray(collectionObj?.sources)
    ? collectionObj.sources
    : [];

  const collectionItemsPerSource = Object.fromEntries(
    collectionSources.flatMap((source) => {
      const entry = getObject(source);
      const name = getString(entry?.name);
      const articles = getNumber(entry?.articles);
      if (!name || articles === null) {
        return [];
      }
      return [[name, articles]];
    })
  ) as Record<string, number>;

  const itemsPerSource =
    normalizeItemsPerSource(collectionObj?.items_per_source) ??
    normalizeItemsPerSource(collectionItemsPerSource) ??
    normalizeItemsPerSource(rawRow.items_per_source);

  const sourceErrors =
    normalizeSourceErrors(collectionObj?.source_errors) ??
    normalizeSourceErrors(
      collectionSources.length > 0
        ? Object.fromEntries(
            collectionSources.flatMap((source) => {
              const entry = getObject(source);
              const name = getString(entry?.name);
              const status = getString(entry?.status);
              if (!name || !status || status === "success") {
                return [];
              }
              return [[name, `Status: ${status}`]];
            })
          ) as Record<string, string>
        : null
    ) ??
    normalizeSourceErrors(rawRow.source_errors);

  let durationSeconds =
    getNumber(statsObj?.duration_seconds) ??
    getNumber(rawRow.duration_seconds);
  if (durationSeconds === null && mtimes.length > 1) {
    durationSeconds = Math.round((Math.max(...mtimes) - Math.min(...mtimes)) / 1000);
  }

  const completedAt =
    getString(statsObj?.completed_at) ??
    readMetaGeneratedAt(getObject(brief)) ??
    getString(rawRow.completed_at) ??
    getString(rawRow.created_at);

  const startedAt =
    getString(statsObj?.started_at) ??
    getString(rawRow.started_at) ??
    (mtimes.length > 0
      ? new Date(Math.min(...mtimes)).toISOString()
      : null);

  const normalizedCounts = normalizePipelineCounts({
    items_collected:
      getNumber(triageObj?.total_input) ??
      getNumber(rawRow.items_collected) ??
      getNumber(collectionObj?.total_articles) ??
      countArrayItems(rawPool),
    items_after_triage:
      getNumber(triageObj?.kept) ??
      getNumber(rawRow.items_after_triage) ??
      getNumber(rawRow.items_triaged),
    items_after_date_filter:
      getNumber(rawRow.items_after_date_filter) ??
      (() => {
        const triaged =
          getNumber(triageObj?.kept) ??
          getNumber(rawRow.items_after_triage) ??
          getNumber(rawRow.items_triaged);
        const droppedCount =
          getNumber(droppedByDateObj?.dropped_count) ??
          (Array.isArray(droppedByDateObj?.dropped)
            ? droppedByDateObj.dropped.length
            : null);
        if (triaged !== null && droppedCount !== null) {
          return Math.max(triaged - droppedCount, 0);
        }
        return null;
      })(),
    items_after_dedup:
      countArrayItems(rawPool) ??
      getNumber(rawRow.items_after_dedup),
    items_after_content_filter:
      countArrayItems(postFilter) ??
      countContentFilterKept(contentFilter) ??
      getNumber(rawRow.items_after_content_filter),
    items_after_gatekeeper:
      countGatekeeperSelected(gatekeeper) ??
      getNumber(rawRow.items_after_gatekeeper),
    items_in_final_brief:
      countBriefItems(getObject(brief)) ??
      getNumber(rawRow.items_in_final_brief),
  });

  return {
    id: getString(rawRow.id) ?? runDate,
    run_date: runDate,
    status: getString(rawRow.status) ?? "success",
    items_collected: normalizedCounts.items_collected,
    items_after_triage: normalizedCounts.items_after_triage,
    items_after_date_filter: normalizedCounts.items_after_date_filter,
    items_after_dedup: normalizedCounts.items_after_dedup,
    items_after_content_filter: normalizedCounts.items_after_content_filter,
    items_after_gatekeeper: normalizedCounts.items_after_gatekeeper,
    items_in_final_brief: normalizedCounts.items_in_final_brief,
    items_per_source: itemsPerSource,
    source_errors: sourceErrors,
    duration_seconds: durationSeconds,
    total_cost_usd: normalizeCost(statsObj, rawRow),
    sources_count:
      (itemsPerSource ? Object.keys(itemsPerSource).length : null) ??
      getNumber(rawRow.sources_count),
    started_at: startedAt,
    completed_at: completedAt,
    created_at: getString(rawRow.created_at),
  };
}

export async function hydratePipelineRuns(
  rows: JsonObject[]
): Promise<AdminPipelineRun[]> {
  return Promise.all(rows.map((row) => hydratePipelineRun(row)));
}

/* ─── Enrichment data utilities ─────────────────────────────────────── */

function normalizeJudgeResult(value: unknown): EnrichmentJudgeResult {
  const obj = getObject(value);
  return {
    decision: (getString(obj?.decision) as "SUFFICIENT" | "INSUFFICIENT") ?? "INSUFFICIENT",
    confidence: getNumber(obj?.confidence) ?? 0,
    missing_elements: Array.isArray(obj?.missing_elements)
      ? (obj.missing_elements as unknown[]).filter((v): v is string => typeof v === "string")
      : [],
    recommended_query_terms: Array.isArray(obj?.recommended_query_terms)
      ? (obj.recommended_query_terms as unknown[]).filter((v): v is string => typeof v === "string")
      : [],
    reasoning: getString(obj?.reasoning) ?? "",
  };
}

function normalizeEnrichedSource(value: unknown): EnrichedSource | null {
  const obj = getObject(value);
  if (!obj) return null;
  return {
    url: getString(obj.url) ?? "",
    title: getString(obj.title) ?? "",
    extract: getString(obj.extract) ?? "",
    source_step: (getString(obj.source_step) as EnrichedSource["source_step"]) ?? "web_search",
  };
}

function normalizeEnrichedFacts(value: unknown): EnrichedFacts | null {
  const obj = getObject(value);
  if (!obj) return null;
  const summary = getString(obj.summary);
  if (!summary) return null;
  return {
    summary,
    key_facts: Array.isArray(obj.key_facts)
      ? (obj.key_facts as unknown[]).flatMap((f) => {
          const fo = getObject(f);
          const fact = getString(fo?.fact);
          const source = getString(fo?.source) ?? "";
          return fact ? [{ fact, source }] : [];
        })
      : [],
    open_questions: Array.isArray(obj.open_questions)
      ? (obj.open_questions as unknown[]).filter((v): v is string => typeof v === "string")
      : [],
  };
}

function parseEnrichmentItem(raw: unknown): EnrichmentItem | null {
  const obj = getObject(raw);
  if (!obj) return null;

  const meta = getObject(obj._enrichment);
  if (!meta) return null;

  const enrichedSources = Array.isArray(obj.enriched_sources)
    ? (obj.enriched_sources as unknown[])
        .map(normalizeEnrichedSource)
        .filter((s): s is EnrichedSource => s !== null)
    : [];

  const stepsTaken = Array.isArray(meta.steps_taken)
    ? (meta.steps_taken as unknown[]).filter((v): v is string => typeof v === "string")
    : [];

  const tokens = getObject(meta.tokens);

  return {
    headline: getString(obj.headline) ?? getString(obj.title) ?? "(no headline)",
    source: getString(obj.source) ?? "",
    source_url: getString(obj.source_url) ?? "",
    original_word_count: getNumber(meta.original_word_count) ?? 0,
    enriched_word_count: getNumber(meta.enriched_word_count) ?? 0,
    was_thin: meta.was_thin === true,
    steps_taken: stepsTaken,
    final_source: getString(meta.final_source) ?? "none",
    judge_1_result: normalizeJudgeResult(meta.judge_1_result),
    judge_2_result: normalizeJudgeResult(meta.judge_2_result),
    enriched_sources: enrichedSources,
    enriched_facts: normalizeEnrichedFacts(obj.enriched_facts),
    elapsed_seconds: getNumber(meta.elapsed_seconds) ?? 0,
    tokens: {
      input: getNumber(tokens?.input) ?? 0,
      output: getNumber(tokens?.output) ?? 0,
    },
  };
}

function computeEnrichmentSummary(items: EnrichmentItem[]): EnrichmentSummary {
  const thinItems = items.filter((i) => i.was_thin);
  const enrichedOk = items.filter((i) => i.was_thin && i.final_source !== "none");

  const finalSourceBreakdown: Record<string, number> = {};
  const stageEntered: Record<string, number> = {};
  const stageResolved: Record<string, number> = {};

  let totalTokensIn = 0;
  let totalTokensOut = 0;
  let totalElapsed = 0;
  let totalOrigWc = 0;
  let totalEnrWc = 0;
  let totalConf1 = 0;
  let totalConf2 = 0;
  let conf1Count = 0;
  let conf2Count = 0;
  let researchCount = 0;

  for (const item of items) {
    // Final source breakdown
    const fs = item.final_source || "none";
    finalSourceBreakdown[fs] = (finalSourceBreakdown[fs] ?? 0) + 1;

    // Accumulate totals for thin items only
    if (item.was_thin) {
      totalTokensIn += item.tokens.input;
      totalTokensOut += item.tokens.output;
      totalElapsed += item.elapsed_seconds;
      totalOrigWc += item.original_word_count;
      totalEnrWc += item.enriched_word_count;

      if (item.judge_1_result.confidence > 0) {
        totalConf1 += item.judge_1_result.confidence;
        conf1Count++;
      }
      if (item.judge_2_result.confidence > 0) {
        totalConf2 += item.judge_2_result.confidence;
        conf2Count++;
      }
      if (item.final_source === "research_agent") {
        researchCount++;
      }
    }

    // Stage flow counts (from steps_taken)
    const stages = ["url_fetch", "web_search", "research_agent"];
    for (const stage of stages) {
      if (item.steps_taken.includes(stage)) {
        stageEntered[stage] = (stageEntered[stage] ?? 0) + 1;
      }
    }
    // Stage resolved = final_source
    if (stages.includes(fs)) {
      stageResolved[fs] = (stageResolved[fs] ?? 0) + 1;
    }
  }

  const thinCount = thinItems.length || 1; // avoid division by zero

  return {
    total_items: items.length,
    thin_items: thinItems.length,
    enriched_successfully: enrichedOk.length,
    total_tokens_input: totalTokensIn,
    total_tokens_output: totalTokensOut,
    total_elapsed_seconds: totalElapsed,
    final_source_breakdown: finalSourceBreakdown,
    avg_original_word_count: Math.round(totalOrigWc / thinCount),
    avg_enriched_word_count: Math.round(totalEnrWc / thinCount),
    avg_confidence_judge_1: conf1Count > 0 ? totalConf1 / conf1Count : 0,
    avg_confidence_judge_2: conf2Count > 0 ? totalConf2 / conf2Count : 0,
    research_agent_count: researchCount,
    stage_entered: stageEntered,
    stage_resolved: stageResolved,
  };
}

/**
 * Read enrichment data for a single run date.
 * Tries local file first, then accepts optional preloaded JSON (e.g. from Supabase gatekeeper_log).
 * Returns null if no enrichment data is available.
 */
export async function readEnrichmentData(
  runDate: string,
  preloaded?: Record<string, unknown> | null
): Promise<{ summary: EnrichmentSummary; items: EnrichmentItem[] } | null> {
  let raw: JsonObject | unknown[] | null = preloaded ?? null;
  if (!raw) {
    const outputDir = await findOutputDir();
    raw = await readJsonFile(outputDir, `enriched_gatekeeper_output_${runDate}.json`);
  }
  if (!raw || Array.isArray(raw)) return null;

  const selected = Array.isArray(raw.selected) ? raw.selected : [];
  const items = selected
    .map(parseEnrichmentItem)
    .filter((i): i is EnrichmentItem => i !== null);

  if (items.length === 0) return null;

  return { summary: computeEnrichmentSummary(items), items };
}

/**
 * Read enrichment summaries for all available dates (for historical charts).
 */
export async function readEnrichmentHistory(): Promise<
  Array<{ date: string; summary: EnrichmentSummary }>
> {
  const outputDir = await findOutputDir();
  if (!outputDir) return [];

  let files: string[];
  try {
    files = await fs.readdir(outputDir);
  } catch {
    return [];
  }

  const PREFIX = "enriched_gatekeeper_output_";
  const SUFFIX = ".json";
  const enrichmentFiles = files
    .filter((f) => f.startsWith(PREFIX) && f.endsWith(SUFFIX))
    .sort();

  const results: Array<{ date: string; summary: EnrichmentSummary }> = [];

  for (const filename of enrichmentFiles) {
    const date = filename.slice(PREFIX.length, -SUFFIX.length);
    const raw = await readJsonFile(outputDir, filename);
    if (!raw || Array.isArray(raw)) continue;

    const selected = Array.isArray(raw.selected) ? raw.selected : [];
    const items = selected
      .map(parseEnrichmentItem)
      .filter((i): i is EnrichmentItem => i !== null);

    if (items.length > 0) {
      results.push({ date, summary: computeEnrichmentSummary(items) });
    }
  }

  return results;
}


// ---------------------------------------------------------------------------
// Brief Rationalization helpers
// ---------------------------------------------------------------------------

/**
 * Read brief_rationalization_{date}.json from the local output directory.
 * Returns the parsed JSON object or null if the file doesn't exist.
 */
export async function readRationalizationData(
  date: string
): Promise<Record<string, unknown> | null> {
  const outputDir = await findOutputDir();
  const data = await readJsonFile(outputDir, `brief_rationalization_${date}.json`);
  if (!data || Array.isArray(data)) return null;
  return data as Record<string, unknown>;
}
