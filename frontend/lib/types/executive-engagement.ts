/* ------------------------------------------------------------------ */
/*  Executive Engagement types — Supabase-backed                      */
/* ------------------------------------------------------------------ */

export interface BioFacts {
  current_roles: { org: string; role: string }[];
  previous_roles: { org: string; role: string; years: string }[];
  recognition: string[];
}

/** CV sidebar data for concise bio mode (current + top recognition only) */
export interface ConciseCV {
  current: { org: string; role: string }[];
  key_recognition: string[];
  education?: string[];
}

/** CV sidebar data for extended bio mode (full career + recognition) */
export interface ExtendedCV {
  current: { org: string; role: string }[];
  previous: { org: string; role: string; dates?: string }[];
  recognition: string[];
  education?: string[];
}

export interface MutualInterest {
  id: string;
  topic?: string;
  description?: string;
  /** @deprecated old shape — use `description` */
  text?: string;
}

export interface SuggestedQuestion {
  id: string;
  topic?: string;
  question?: string;
  /** @deprecated old shape — use `question` */
  text?: string;
}

export interface IntelBriefing {
  id: string;
  topic: string;       // 1-2 word label, uppercase (e.g., "FUNDING")
  question: string;    // Full strategic question
  answer: string;      // Pre-computed answer (2-4 sentences)
  detail: string | null; // Optional deeper context
  status: "pending" | "ready" | "error";
}

export interface EngagementMaterial {
  id: string;
  name: string;
  url: string | null;
  storage_path?: string | null;
  uploadedAt: string;
}

export type EngagementFormat = "In person" | "Virtual" | "Hybrid";

export interface Engagement {
  id: string;
  visitor_name: string;
  visitor_title: string;
  visitor_organization: string;
  date: string; // ISO date "YYYY-MM-DD"
  time: string; // e.g. "10:00 AM GST"
  location: string;
  format: EngagementFormat;

  /* LLM-generated — old shape (backward compat) */
  bio: string | null;
  bio_facts: BioFacts | null;
  /** @deprecated kept for backward compat with old rows */
  credential_tags?: string[];

  /* LLM-generated — new dual-bio shape */
  bio_concise_cv?: ConciseCV | null;
  bio_concise_narrative?: string | null;   // HTML string
  bio_extended_cv?: ExtendedCV | null;
  bio_extended_narrative?: string | null;  // HTML string
  research_chips?: string[] | null;
  intel_briefings?: IntelBriefing[] | null;

  mutual_interests: MutualInterest[];
  suggested_questions: SuggestedQuestion[];

  /* Admin-uploaded */
  materials: EngagementMaterial[];

  /* Metadata */
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface EngagementFollowup {
  id: string;
  engagement_id: string;
  question: string;
  answer: string;
  detail: string | null;
  asked_by: string;
  created_at: string;
}

export interface EngagementRequest {
  id: string;
  engagement_id: string;
  message: string;
  requested_by: string;
  status: "open" | "in_progress" | "done";
  created_at: string;
  resolved_at: string | null;
}

/* API request body for generating a new dossier */
export interface GenerateDossierInput {
  visitorName: string;
  visitorTitle: string;
  visitorOrganization: string;
  date: string;
  time: string;
  location: string;
  format: EngagementFormat;
}

/* Shape returned by the Sonnet dossier generation call (new dual-bio) */
export interface DossierGenerationResult {
  bio: {
    concise: {
      cv: ConciseCV;
      narrative: string; // HTML
    };
    extended: {
      cv: ExtendedCV;
      narrative: string; // HTML
    };
  };
  areas_of_mutual_interest: { id: string; topic: string; description: string }[];
  suggested_questions?: { id: string; topic: string; question: string }[];
  research_chips: string[];
  intel_questions: { id: string; topic: string; question: string }[];
}

/** @deprecated Old shape — kept for backward compat parsing */
export interface DossierGenerationResultLegacy {
  bio_facts: BioFacts;
  bio_narrative: string;
  areas_of_mutual_interest: { id: string; topic: string; description: string }[];
  suggested_questions: { id: string; topic: string; question: string }[];
}

/* Shape returned by the Sonnet follow-up call */
export interface FollowupResult {
  answer: string;
  detail: string | null;
}
