// ─── Core Brief Types ───────────────────────────────────────────────────────

/** The 5 canonical brief sections, in display order. */
export const SECTION_ORDER = [
  "UAE",
  "Regional Research & Academic Events",
  "International Politics & Policy",
  "International Business & Technology",
  "Model Releases & Technical Developments",
] as const;

export type SectionName = (typeof SECTION_ORDER)[number];
export type SubjectType =
  | "person"
  | "organization"
  | "country"
  | "place"
  | "model"
  | "asset"
  | "other";

// ─── Frontend-facing interfaces ─────────────────────────────────────────────

export interface Brief {
  brief_date: string; // YYYY-MM-DD
  generated_at: string; // ISO timestamp
  item_count: number;
  sources_consulted: number;
  items_reviewed: number;
  pipeline_cost_usd: number;
  executive_summary?: string;
  items: BriefItem[];
  sections: BriefSection[];
  metadata: BriefMetadata;
  // Sprint 6: Audio brief
  audio_url?: string;
  audio_script?: string;
  audio_url_fr?: string;
  audio_script_fr?: string;
  audio_url_ar?: string;
  audio_script_ar?: string;
  audio_segments?: AudioSegment[];
}

export interface BriefSection {
  name: string; // One of the 5 section names
  items: BriefItem[];
}

/** Exhibit types for structured data visualization on cards. */
export interface ExhibitData {
  type:
    | "benchmark_table"
    | "comparison_table"
    | "metric_highlight"
    | "timeline"
    | "raw_image";
  data: Record<string, unknown>;
  source_image_url?: string;
}

export interface BriefItem {
  id: string; // YYYY-MM-DD-NNN
  headline: string; // <=15 words
  main_bullet: string; // v1: "The what". v2: empty string (use key_bullets)
  context?: string; // v1: "The why now". v2: empty (use analysis)
  implication?: string; // v1: "The so what". v2: empty (use analysis)
  source_name: string;
  source_url?: string;
  source_origin?: "canonical" | "newsletter";
  significance: "high" | "medium" | "low";
  composite_score: number;
  topic_relevance: number; // 1-10 (0 if unavailable)
  news_significance: number; // 1-10 (0 if unavailable)
  is_continuity: boolean;
  continuity_days?: number;
  section: string;

  // Extended fields from pipeline data
  rank: number;
  depth: "full" | "standard" | "brief";
  entities: string[];
  additional_sources: { name: string; url: string }[];
  source_domain?: string;
  cluster?: string;
  is_model_release: boolean;
  model_release_data?: ModelReleaseData;

  // v2 card reader fields (optional for backward compat with old briefs)
  key_bullets?: string[];
  analysis?: string;
  primary_entity?: string;
  primary_subject?: string;
  primary_subject_type?: SubjectType;
  /**
   * One of ten entity_logos.category values, populated by the Entity
   * Classifier pipeline stage. Consumed by the badge resolver in
   * `lib/entity-badge.ts` to decide between a logo, country flag, or
   * section-themed icon.
   */
  primary_entity_category?: EntityCategory;
  badge_subject?: string;
  badge_subject_type?: SubjectType;
  badge_subject_category?: EntityCategory;
  exhibits?: ExhibitData[];
  audio_url?: string;
  // Language learning content (per-item)
  learning_fr?: ItemLearningContent;
  learning_ar?: ItemLearningContent;
}

export type EntityCategory =
  | "company"
  | "university"
  | "government"
  | "energy"
  | "finance"
  | "defense"
  | "org"
  | "model"
  | "country"
  | "other";

// ─── Language Learning Types (V3 Sentence-Based) ────────────────────────────

/** Key word breakdown within a sentence. */
export interface KeyWord {
  word: string;
  note: string;
}

/** Grammar and linguistic analysis for a learning sentence. */
export interface PhraseGrammar {
  // Core fields (always populated)
  morphology?: string;
  etymology?: string;
  conjugation?: string;
  register?: string;
  phonetic_guide?: string;
  usage_notes?: string;
  cognate_note?: string;
  // Sentence analysis fields (ITER 18)
  syntax?: string;
  key_words?: KeyWord[];
  phonetic_features?: string;
}

export interface LearningPhrase {
  id: string;
  // Target language content (supports both "phrase" and "sentence" terminology)
  phrase_target: string;
  sentence_target?: string; // Alias for sentence-based content (ITER 18)
  phrase_en: string;
  sentence_en?: string; // Alias for sentence-based content (ITER 18)
  context_anchor?: string;
  script1: string;
  script2: string;
  script3: string;
  script4: string;
  audio_url_1?: string;
  audio_url_2?: string;
  audio_url_3?: string;
  audio_url_4?: string;
  grammar: PhraseGrammar;
  estimated_duration_seconds?: number;
}

/** V3 phrase-based learning content. */
export interface ItemLearningContent {
  version: 3;
  phrases: LearningPhrase[];
  difficulty: "beginner" | "intermediate" | "advanced";
  total_duration_seconds?: number;
  lesson_summary?: string;
}

// ─── V2 Legacy Types (backward compatibility) ───────────────────────────────

/** V2 legacy: Learning vocabulary item. */
export interface LearningVocabulary {
  term: string;
  translation: string;
  definition: string;
  example_sentence: string;
  part_of_speech: string;
  grammar_note?: string;
  pronunciation_guide?: string;
  example_sentences?: string[];
}

/** V2 legacy: Learning phrase within a section. */
export interface LearningPhraseV2 {
  phrase: string;
  translation: string;
  context_note?: string;
  example_sentence?: string;
  part_of_speech?: string;
  grammar_note?: string;
  pronunciation_guide?: string;
  example_sentences?: string[];
  word_root?: string;
  register?: string;
  conjugation?: string;
}

export type LearningSectionType = "narrative" | "phrase_focus" | "vocabulary" | "grammar" | "summary";

export interface LearningSection {
  id: string;
  type: LearningSectionType;
  title: string;
  title_en: string;
  script: string;
  key_phrases?: LearningPhraseV2[];
  audio_url?: string;
  estimated_duration_seconds?: number;
}

/** V2 multi-section learning content (legacy). */
export interface ItemLearningContentV2 {
  sections: LearningSection[];
  vocabulary: LearningVocabulary[];
  difficulty: "beginner" | "intermediate" | "advanced";
  total_audio_duration_seconds?: number;
}

/** V1 legacy flat learning content (single script). */
export interface ItemLearningContentLegacy {
  script: string;
  vocabulary: LearningVocabulary[];
  difficulty: "beginner" | "intermediate" | "advanced";
  audio_url?: string;
}

/** Raw learning content from DB — v1, v2, or v3. */
export type ItemLearningContentRaw = ItemLearningContent | ItemLearningContentV2 | ItemLearningContentLegacy;

export interface AudioSegment {
  item_id: string;
  start: number;
  end: number;
}

export interface FollowUpItem {
  id: string;
  original_item_id: string;
  brief_date: string;
  original_section: string;
  status: "pending" | "responded";
  response_summary?: string;
  responded_at?: string;
  original_headline: string;
  request_note?: string;
  original_source_name?: string;
  original_source_url?: string;
}

export type FeedCard =
  | { type: "story"; item: BriefItem; followUp?: FollowUpItem }
  | { type: "divider"; label: string; kind: "section" | "day" }
  | { type: "end"; itemsReviewed: number; itemsFlagged: number };

export interface KeyNumber {
  label: string;
  value: string;
  qualifier?: string;
}

export interface BenchmarkData {
  models: string[];
  highlighted_model_index: number;
  highlighted_model_indexes?: number[];
  rows: { benchmark: string; scores: string[] }[];
  summary?: string;
}

export interface ModelReleaseData {
  developer: string;
  model_name: string;
  summary_pitch?: string;
  key_numbers?: KeyNumber[];
  benchmarks?: BenchmarkData;
  architecture?: string;
  training?: string;
  availability?: string;
  // Legacy fields (old briefs)
  specs?: string;
  performance?: string;
  commercials?: string;
}

export interface BriefMetadata {
  lead_story_id?: string;
  section_counts?: Record<string, number>;
  pipeline_version?: string;
  run_duration_seconds?: number;
  model_versions?: Record<string, string>;
}

// ─── Raw pipeline JSON shape (what the backend produces) ────────────────────

export interface RawPipelineBrief {
  brief_metadata: {
    date: string;
    generated_at: string;
    total_items: number;
    section_counts: Record<string, number>;
    lead_story_id: string;
    rejected_unknown_sections?: number;
  };
  items: RawPipelineItem[];
}

export interface RawPipelineItem {
  id: string;
  rank: number;
  section: string;
  headline: string;
  source_domain: string | null;
  source_name: string | null;
  source_url: string | null;
  source_origin?: string | null;
  additional_sources: { name: string; url: string }[];
  main_bullet: string;
  context: string | null;
  implication: string | null;
  entities: string[];
  composite_score: number;
  significance_level: string | null;
  cluster: string | null;
  continuity: string | null;
  is_model_release: boolean;
  model_release_data: ModelReleaseData | null;
  depth: string;
  // v2 card reader fields
  key_bullets?: string[] | null;
  analysis?: string | null;
  primary_entity?: string | null;
  primary_subject?: string | null;
  primary_subject_type?: SubjectType | null;
  primary_entity_category?: string | null;
  badge_subject?: string | null;
  badge_subject_type?: SubjectType | null;
  badge_subject_category?: string | null;
  exhibits?: ExhibitData[] | null;
  audio_url?: string | null;
  is_placeholder?: boolean;
  // Language learning content (per-item) — may be v1 legacy or v2 sections
  learning_fr?: ItemLearningContentRaw | null;
  learning_ar?: ItemLearningContentRaw | null;
}

// ─── Sprint 3 shapes (defined now for forward-compatibility) ────────────────

export interface Annotation {
  id: string;
  user_id?: string;
  item_id: string;
  brief_date: string;
  note_text: string;
  created_at: string;
  updated_at?: string;
}

export interface Flag {
  id: string;
  user_id: string;
  item_id: string;
  brief_date: string;
  flag_type: "follow_up" | "important" | "share";
  created_at: string;
}

export interface ResearchRequest {
  id: string;
  user_id: string;
  item_id: string;
  brief_date: string;
  request_note?: string;
  status: "pending" | "in_progress" | "completed" | "dismissed";
  assigned_to?: string;
  response?: string;
  created_at: string;
  completed_at?: string;
}
