export interface AdminPipelineRun {
  id: string;
  run_date: string;
  status: string;
  items_collected: number | null;
  items_after_triage: number | null;
  items_after_date_filter: number | null;
  items_after_dedup: number | null;
  items_after_content_filter: number | null;
  items_after_gatekeeper: number | null;
  items_in_final_brief: number | null;
  items_per_source: Record<string, number> | null;
  source_errors: Record<string, string> | null;
  duration_seconds: number | null;
  total_cost_usd: number | null;
  sources_count: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}
