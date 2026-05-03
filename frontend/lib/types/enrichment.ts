/* ─── Enrichment tab types ──────────────────────────────────────────── */

/** Haiku judge result from the enrichment pipeline. */
export interface EnrichmentJudgeResult {
  decision: "SUFFICIENT" | "INSUFFICIENT";
  confidence: number;
  missing_elements: string[];
  recommended_query_terms: string[];
  reasoning: string;
}

/** A single supplementary source fetched during enrichment. */
export interface EnrichedSource {
  url: string;
  title: string;
  extract: string;
  source_step: "url_fetch" | "web_search" | "research_agent";
}

/** Research-agent output (only present when research_agent step triggered). */
export interface EnrichedFacts {
  summary: string;
  key_facts: Array<{ fact: string; source: string }>;
  open_questions: string[];
}

/** Per-item enrichment view for the admin panel. */
export interface EnrichmentItem {
  headline: string;
  source: string;
  source_url: string;
  original_word_count: number;
  enriched_word_count: number;
  was_thin: boolean;
  steps_taken: string[];
  final_source: string;
  judge_1_result: EnrichmentJudgeResult;
  judge_2_result: EnrichmentJudgeResult;
  enriched_sources: EnrichedSource[];
  enriched_facts: EnrichedFacts | null;
  elapsed_seconds: number;
  tokens: { input: number; output: number };
}

/** Aggregate summary metrics for one run date. */
export interface EnrichmentSummary {
  total_items: number;
  thin_items: number;
  enriched_successfully: number;
  total_tokens_input: number;
  total_tokens_output: number;
  total_elapsed_seconds: number;
  final_source_breakdown: Record<string, number>;
  avg_original_word_count: number;
  avg_enriched_word_count: number;
  avg_confidence_judge_1: number;
  avg_confidence_judge_2: number;
  research_agent_count: number;
  /** Per-stage counts: how many items entered each stage. */
  stage_entered: Record<string, number>;
  /** Per-stage counts: how many items resolved at each stage. */
  stage_resolved: Record<string, number>;
}

/** API response shape for mode=single. */
export interface EnrichmentResponse {
  summary: EnrichmentSummary | null;
  items: EnrichmentItem[];
  dates: string[];
}

/** API response shape for mode=history. */
export interface EnrichmentHistoryResponse {
  history: Array<{ date: string; summary: EnrichmentSummary }>;
  dates: string[];
}
