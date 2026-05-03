import type {
  EntityCategory,
  ExhibitData,
  SubjectType,
} from "@/lib/types/brief";

// ─── Curation Workflow Types ────────────────────────────────────────────────

export interface PendingBrief {
  id: string;
  brief_date: string;
  status: "pending" | "in_review" | "approved" | "published";
  claimed_by: string | null;
  claimed_at: string | null;
  approved_at: string | null;
  published_at: string | null;
  pipeline_stats: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PendingItem {
  kind: "pending";
  id: string;
  pending_brief_id: string;
  item_id: string;
  section: string;
  headline: string;
  main_bullet: string | null;
  context: string | null;
  implication: string | null;
  source_name: string | null;
  source_url: string | null;
  composite_score: number;
  significance_level: string | null;
  rank: number | null;
  depth: string | null;
  is_model_release: boolean;
  model_release_data: Record<string, unknown> | null;
  key_bullets: string[] | null;
  analysis: string | null;
  primary_entity: string | null;
  primary_subject: string | null;
  primary_subject_type: SubjectType | null;
  primary_entity_category: EntityCategory | null;
  badge_subject: string | null;
  badge_subject_type: SubjectType | null;
  badge_subject_category: EntityCategory | null;
  exhibits: ExhibitData[] | null;
  selected: boolean;
  curation_order: number | null;
  raw_item: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
}

export interface ManualItem {
  kind: "manual";
  id: string;
  pending_brief_id: string;
  item_id: string;
  section: string;
  headline: string;
  main_bullet: string | null;
  context: string | null;
  implication: string | null;
  source_name: string | null;
  source_url: string | null;
  composite_score: number;
  significance_level: string | null;
  key_bullets: string[] | null;
  analysis: string | null;
  primary_entity: string | null;
  primary_subject: string | null;
  primary_subject_type: SubjectType | null;
  primary_entity_category: EntityCategory | null;
  badge_subject: string | null;
  badge_subject_type: SubjectType | null;
  badge_subject_category: EntityCategory | null;
  exhibits: ExhibitData[] | null;
  selected: boolean;
  curation_order: number | null;
  raw_item: Record<string, unknown>;
  depth: string | null;
  is_model_release: boolean;
  model_release_data: Record<string, unknown> | null;
  added_by: string;
  created_at: string;
  updated_at: string | null;
}

export type CurationItem = PendingItem | ManualItem;

export interface CurationItemRef {
  id: string;
  kind: CurationItem["kind"];
}

export interface CurationDecision {
  id: string;
  pending_brief_id: string;
  item_id: string;
  decision:
    | "keep"
    | "remove"
    | "promote"
    | "demote"
    | "edit"
    | "reorder"
    | "add";
  original_tier: string | null;
  original_section: string | null;
  original_rank: number | null;
  final_section: string | null;
  final_rank: number | null;
  edit_fields: Record<string, { before: string; after: string }> | null;
  analyst_id: string;
  created_at: string;
}

/** Full pending brief with items for the curation workspace */
export interface CurationSlate {
  brief: PendingBrief;
  items: CurationItem[];
}
