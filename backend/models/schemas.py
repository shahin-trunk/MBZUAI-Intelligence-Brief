from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Literal, Any


def _coerce_none_to_empty_list(v):
    """Validator helper: coerce None into [] for list fields.

    Sonnet sometimes emits `null` instead of `[]` for empty list-typed
    fields (e.g. `missing_fields: null`). The schema declares them as
    `list[...]` with `default_factory=list`, but `default_factory` only
    fires when the field is absent — explicit `null` still trips
    pydantic v2 validation. This validator restores the intuitive
    behavior: missing OR null → empty list.
    """
    return v if v is not None else []


def _coerce_none_to_empty_str(v):
    """Validator helper: coerce None into "" for required str fields.

    Mirror of `_coerce_none_to_empty_list`. Sonnet sometimes emits
    `null` for required string fields (e.g. `date: null` when the source
    item itself had no date). The schema declares them as `str` with no
    default, so explicit `null` trips validation. Coerce None → ""
    (empty string) so the call survives — downstream stages can decide
    how to handle empty strings (most already treat empty as missing).
    """
    return v if v is not None else ""


def _coerce_none_to_zero_float(v):
    """Validator helper: coerce None into 0.0 for required float fields.

    Same pattern as the str/list coercers. Sonnet occasionally emits
    `null` for `composite_score`, `topic_relevance`, or
    `news_significance` when scoring an item it doesn't want to commit
    on. Coerce to 0.0 so the call survives — the orchestrator's
    section-cap logic ranks by composite_score so a 0.0 simply ranks
    last instead of breaking validation.
    """
    return v if v is not None else 0.0


# --- Scout output schemas ---

class ScoutItem(BaseModel):
    headline: str
    source: str
    source_url: str
    date: str
    date_evidence: str = "NO DATE FOUND IN SOURCE"
    summary: str
    raw_content: str
    additional_context: Optional[str] = None
    entities: list[str] = Field(default_factory=list)
    category: str
    significance: Optional[str] = None
    also_covered_by: list = Field(default_factory=list)  # list[str] or list[dict]
    # Optional fields from specific scouts
    uae_exposure: Optional[str] = None
    item_type: Optional[str] = None
    technical_completeness: Optional[dict] = None
    institutions: Optional[list[str]] = None
    event_details: Optional[dict] = None
    competitive_relevance: Optional[str] = None
    source_scout: Optional[str] = None


class SourceRecord(BaseModel):
    source_name: str
    source_url: Optional[str] = None
    published_date: Optional[str] = None
    collector_origin: Optional[str] = None
    raw_extract: str = ""
    source_authority_tier: int = 5
    newsletter_provenance: bool = False
    source_domain: Optional[str] = None


class EvidenceFact(BaseModel):
    fact: str
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    source_authority_tier: int = 5
    confidence: float = 0.7
    fact_type: str = "general"


class RequiredFieldValue(BaseModel):
    field: str
    status: Literal[
        "filled",
        "not_disclosed",
        "not_stated",
        "not_yet_available",
        "missing",
    ] = "missing"
    value: Optional[str] = None
    evidence_urls: list[str] = Field(default_factory=list)


class NormalizedEntity(BaseModel):
    name: str
    role: Optional[str] = None
    entity_type: Optional[str] = None


class CorroboratingSource(BaseModel):
    source_name: str
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    source_authority_tier: int = 5
    corroborates: list[str] = Field(default_factory=list)


class CanonicalDateEntry(BaseModel):
    label: str
    value: Optional[str] = None
    source_url: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "medium"
    note: Optional[str] = None


class CanonicalDates(BaseModel):
    event_date: Optional[str] = None
    event_date_confidence: Literal["high", "medium", "low"] = "medium"
    source_publication_dates: list[CanonicalDateEntry] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class UnresolvedFact(BaseModel):
    field: str
    question: str
    status: Literal[
        "missing",
        "not_disclosed",
        "not_stated",
        "not_yet_available",
    ] = "missing"
    note: Optional[str] = None
    evidence_urls: list[str] = Field(default_factory=list)


class CompletenessSummary(BaseModel):
    required_fields: int = 0
    filled_fields: int = 0
    unresolved_fields: int = 0
    percent: float = 0.0
    statuses: dict[str, str] = Field(default_factory=dict)
    ready_for_writing: bool = False


class ModelReleasePayload(BaseModel):
    developer: Optional[str] = None
    model_family_version: Optional[str] = None
    core_capability_claim: Optional[str] = None
    architecture: Optional[str] = None
    benchmark_results: Optional[str] = None
    predecessor_or_competitor_comparison: Optional[str] = None
    availability_deployment_channels: Optional[str] = None
    pricing_licensing: Optional[str] = None
    open_source_status: Optional[str] = None
    official_announcement_url: Optional[str] = None


class PolicyRegulationPayload(BaseModel):
    authoritative_source_or_policy_text: Optional[str] = None
    effective_date_and_timeline: Optional[str] = None
    scope_and_affected_entities: Optional[str] = None
    enforcement_mechanism: Optional[str] = None
    strategic_context: Optional[str] = None


class ConflictSecurityPayload(BaseModel):
    actors_and_objectives: Optional[str] = None
    date_location_operational_details: Optional[str] = None
    impact: Optional[str] = None
    corroboration: Optional[str] = None
    official_statements: Optional[str] = None
    economic_consequences: Optional[str] = None
    escalation_context: Optional[str] = None
    delta_from_previous: Optional[str] = None


class BusinessTechnologyPayload(BaseModel):
    action_and_scale: Optional[str] = None
    parties_and_roles: Optional[str] = None
    timeline: Optional[str] = None
    strategic_rationale: Optional[str] = None
    operational_consequence: Optional[str] = None


class InstitutionalActionPayload(BaseModel):
    institution_or_entity: Optional[str] = None
    action_decision_or_deployment: Optional[str] = None
    key_people_and_roles: Optional[str] = None
    governance_or_oversight: Optional[str] = None
    strategic_context_and_motivation: Optional[str] = None
    stakeholder_implications: Optional[str] = None


class TechnicalResearchPayload(BaseModel):
    researchers_or_institution: Optional[str] = None
    built_demonstrated_or_published: Optional[str] = None
    performance_metrics_with_baselines: Optional[str] = None
    implementation_details: Optional[str] = None
    practical_impact: Optional[str] = None


# --- Gatekeeper output schemas ---

class GatekeeperSelectedItem(BaseModel):
    # The Gatekeeper JSON uses "_idx" as a stable per-item index for
    # orchestrator-side rejoin. Pydantic v2 treats underscore-prefix names
    # as private attributes, so we alias. Paired with
    # model_dump(by_alias=True) at the validator call site so downstream
    # code can still read drop["_idx"].
    model_config = ConfigDict(populate_by_name=True)

    rank: int
    headline: str
    source: str
    source_url: str
    also_covered_by: list = Field(default_factory=list)  # list[str] or list[dict]
    date: str
    date_evidence: str = "NO DATE FOUND IN SOURCE"
    summary: str
    raw_content: Optional[str] = None
    additional_context: Optional[str] = None
    entities: list[str] = Field(default_factory=list)
    category: str
    brief_section: str
    cluster: Optional[str] = None
    continuity: Optional[str] = None
    topic_relevance: float
    news_significance: float
    composite_score: float
    selection_rationale: str
    dossier_id: Optional[str] = None
    event_key: Optional[str] = None
    story_type: Optional[str] = None
    novelty_status: Optional[str] = None
    continuity_reference: Optional[str] = None
    coverage_completeness: Optional[dict[str, Any]] = None
    missing_fields: list[str] = Field(default_factory=list)
    writer_packet: Optional[dict[str, Any]] = None
    source_richness: Optional[dict[str, Any]] = None
    story_type_confidence: Optional[float] = None
    routing_reason: Optional[str] = None
    delta_from_previous: Optional[str] = None
    confirmed_facts: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_facts: list[dict[str, Any]] = Field(default_factory=list)
    canonical_dates: Optional[dict[str, Any]] = None
    official_source: Optional[dict[str, Any]] = None
    corroborating_sources: list[dict[str, Any]] = Field(default_factory=list)

    # Sonnet sometimes emits explicit `null` for empty list-typed fields.
    # `default_factory=list` only fires when the field is absent; explicit
    # null trips pydantic v2 validation. Coerce null → [] for the
    # commonly-affected fields. (Surfaced 2026-04-23 during the chunked
    # Gatekeeper eval — Model Releases chunk hit this on every retry.)
    _coerce_lists = field_validator(
        "also_covered_by",
        "entities",
        "missing_fields",
        "confirmed_facts",
        "unresolved_facts",
        "corroborating_sources",
        mode="before",
    )(_coerce_none_to_empty_list)

    # Sonnet also emits null on required string fields when the source
    # item itself lacked the value (e.g. date / date_evidence on items
    # with NO DATE FOUND). Coerce null → "" so the call survives.
    _coerce_strs = field_validator(
        "headline",
        "source",
        "source_url",
        "date",
        "date_evidence",
        "summary",
        "category",
        "brief_section",
        "selection_rationale",
        mode="before",
    )(_coerce_none_to_empty_str)

    # And on required float fields: composite_score / topic_relevance /
    # news_significance can come back null when the model declines to
    # commit on a borderline item. Coerce null → 0.0 — the section-cap
    # logic ranks by composite_score so a 0.0 simply ranks last.
    _coerce_floats = field_validator(
        "composite_score",
        "topic_relevance",
        "news_significance",
        mode="before",
    )(_coerce_none_to_zero_float)
    compiled_packet: Optional[dict[str, Any]] = None
    idx: Optional[int] = Field(default=None, alias="_idx")


class GatekeeperDroppedItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    headline: str
    composite_score: float
    drop_reason: str
    idx: Optional[int] = Field(default=None, alias="_idx")

    # Same null-coercion as GatekeeperSelectedItem — Sonnet sometimes
    # emits null for required str/float on dropped items too.
    _coerce_strs = field_validator(
        "headline",
        "drop_reason",
        mode="before",
    )(_coerce_none_to_empty_str)
    _coerce_floats = field_validator(
        "composite_score",
        mode="before",
    )(_coerce_none_to_zero_float)


class GatekeeperBriefSummary(BaseModel):
    total_input_items: int
    after_deduplication: int = 0
    selected: int
    dropped: int
    section_distribution: dict[str, int]
    notable_decisions: Optional[str] = None


class GatekeeperOutput(BaseModel):
    selected: list[GatekeeperSelectedItem]
    dropped: list[GatekeeperDroppedItem]
    brief_summary: GatekeeperBriefSummary


# ---------------------------------------------------------------------------
# Synthesis stage (Phase 2)
#
# The Synthesis stage sits between the Content Filter and the Gatekeeper. It
# groups related items into event-level clusters and annotates each cluster's
# continuity status against the last 3 days of brief history. The output
# frees the Gatekeeper from reasoning about clusters or fuzzy-string overlap
# with prior briefs — it just picks the top-N items with richer metadata.
# ---------------------------------------------------------------------------


class SynthesisItemAnnotation(BaseModel):
    """Per-item annotation linking an input item to its cluster + facet."""
    item_id: int
    cluster_id: str
    facet: Optional[str] = None
    continuity_status: Literal["new_story", "continuation", "restatement"]
    continuity_reference: Optional[str] = None


class SynthesisCluster(BaseModel):
    """A group of related items that collectively describe one event/arc.

    For a 5-item UAE Crown Prince state visit, one SynthesisCluster covers all
    five (arrival, leader bilateral, premier bilateral, CEO meetings, conclusion)
    and the Gatekeeper can unfold it into multiple brief items using the
    member_item_ids + per-item facet tags.
    """
    cluster_id: str
    event_key: str  # Stable across days, used for cross-day continuity
    composite_headline: str
    member_item_ids: list[int]
    continuity_status: Literal["new_story", "continuation", "restatement"]
    continuity_reference: Optional[str] = None
    significance_tier: Literal["head_of_state", "major", "standard"] = "standard"
    rationale: str


class SynthesisOutput(BaseModel):
    """Output of the Synthesis stage. See backend/pipeline/synthesis.py."""
    clusters: list[SynthesisCluster]
    item_annotations: list[SynthesisItemAnnotation]
    skipped_items: list[int] = Field(default_factory=list)


class HistoryDedupVerdict(BaseModel):
    """One verdict from the history-dedup agent.

    The agent returns one verdict per input item. `id` is the integer
    index into the items_json array that was sent in the prompt.

    When `is_repeat=True`, the item is dropped in favor of the matched
    historical entry. `matched_headline` / `matched_brief_date` carry the
    audit trail — `matched_brief_date` is either an ISO date (published
    brief) or "pending YYYY-MM-DD" (draft slate the analyst was shown).
    """
    id: int
    headline: str
    is_repeat: bool
    matched_headline: Optional[str] = None
    matched_brief_date: Optional[str] = None
    reason: Optional[str] = None


class HistoryDedupOutput(BaseModel):
    """Output of the history-dedup stage. See backend/pipeline/history_dedup.py."""
    verdicts: list[HistoryDedupVerdict]


class ContentFilterVerdict(BaseModel):
    id: Optional[int] = None
    index: Optional[int] = None
    # headline was previously required because the old prompt asked the model to
    # echo it back. The new prompt does not (no point echoing data we already
    # have); relaxed to Optional to avoid breaking validation.
    headline: Optional[str] = None
    # New canonical fields (see prompts/content_filter_prompt.md — XML-structured rewrite):
    #   evaluation: one-sentence content-type identification emitted before the decision
    #   decision:   canonical KEEP / DROP verdict
    evaluation: Optional[str] = None
    decision: Optional[Literal["KEEP", "DROP"]] = None
    # Legacy fields — tolerated for backward compatibility while the shadow
    # replay harness compares old-prompt verdicts against the new prompt, and
    # to permit one release cycle of safe rollback. Remove in a follow-up PR
    # after a week of clean runs.
    news_test: Optional[Literal["pass", "fail"]] = None
    duplicate_of: Optional[int] = None
    keep: Optional[bool] = None
    verdict: Optional[str] = None
    reason: Optional[str] = None
    category: Optional[str] = None


class ContentFilterOutput(BaseModel):
    verdicts: list[ContentFilterVerdict]


# --- Ghostwriter output schemas ---

class KeyNumber(BaseModel):
    label: str
    value: str
    qualifier: Optional[str] = None


class BenchmarkData(BaseModel):
    models: list[str]
    highlighted_model_index: int = 0
    highlighted_model_indexes: list[int] = Field(default_factory=list)
    rows: list[dict[str, Any]]
    summary: Optional[str] = None


class ModelReleaseData(BaseModel):
    developer: str
    model_name: str
    summary_pitch: Optional[str] = None
    key_numbers: list[KeyNumber] = Field(default_factory=list)
    benchmarks: Optional[BenchmarkData] = None
    architecture: Optional[str] = None
    training: Optional[str] = None
    availability: Optional[str] = None
    # Legacy fields — kept for backward compat with old briefs in Supabase
    specs: Optional[str] = None
    performance: Optional[str] = None
    commercials: Optional[str] = None


class AdditionalSource(BaseModel):
    name: str
    url: str


class ExhibitData(BaseModel):
    type: str  # benchmark_table, comparison_table, metric_highlight, timeline
    data: dict = Field(default_factory=dict)


SubjectType = Literal[
    "person",
    "organization",
    "country",
    "place",
    "model",
    "asset",
    "other",
]


class GhostwriterItem(BaseModel):
    id: str
    rank: int
    section: str
    headline: str
    source_domain: Optional[str] = None
    source_name: str
    source_url: str
    additional_sources: list[AdditionalSource] = Field(default_factory=list)
    # v2 card fields
    key_bullets: list[str] = Field(default_factory=list)
    analysis: str = ""
    primary_entity: Optional[str] = None
    # Explicit identity fields derived after Ghostwriter. `primary_subject`
    # is the narrative anchor for the story; it is additive to
    # `primary_entity`, which remains for backward compatibility.
    primary_subject: Optional[str] = None
    primary_subject_type: Optional[SubjectType] = None
    # Populated AFTER the Ghostwriter run by the Entity Classifier stage
    # (backend/pipeline/entity_classifier.py). Never set by Ghostwriter itself.
    # See frontend/components/common/EntityIcon.tsx for how it's consumed.
    primary_entity_category: Optional[Literal[
        "company", "university", "government", "energy", "finance",
        "defense", "org", "model", "country", "other"
    ]] = None
    # Populated after entity classification. Lets the UI render a more
    # legible visual identity than the narrative `primary_entity` when needed
    # (e.g. CENTCOM story -> United States badge).
    badge_subject: Optional[str] = None
    badge_subject_type: Optional[SubjectType] = None
    badge_subject_category: Optional[Literal[
        "company", "university", "government", "energy", "finance",
        "defense", "org", "model", "country", "other"
    ]] = None
    exhibits: list[ExhibitData] = Field(default_factory=list)
    # v1 legacy fields (backward compat — empty in v2 output)
    main_bullet: str = ""
    context: str = ""
    implication: str = ""
    entities: list[str] = Field(default_factory=list)
    category: str
    composite_score: float
    cluster: Optional[str] = None
    continuity: Optional[str] = None
    is_model_release: bool = False
    model_release_data: Optional[ModelReleaseData] = None
    depth: str
class GhostwriterOutput(BaseModel):
    date: str
    items: list[GhostwriterItem]


# --- Editor output schemas ---

class FinalBriefItem(BaseModel):
    id: str
    rank: int
    section: str
    headline: str
    source_domain: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    additional_sources: list[AdditionalSource] = Field(default_factory=list)
    # v2 card fields
    key_bullets: list[str] = Field(default_factory=list)
    analysis: Optional[str] = None
    primary_entity: Optional[str] = None
    primary_subject: Optional[str] = None
    primary_subject_type: Optional[SubjectType] = None
    # Populated by the Entity Classifier stage; see GhostwriterItem for docs.
    primary_entity_category: Optional[Literal[
        "company", "university", "government", "energy", "finance",
        "defense", "org", "model", "country", "other"
    ]] = None
    badge_subject: Optional[str] = None
    badge_subject_type: Optional[SubjectType] = None
    badge_subject_category: Optional[Literal[
        "company", "university", "government", "energy", "finance",
        "defense", "org", "model", "country", "other"
    ]] = None
    exhibits: list[ExhibitData] = Field(default_factory=list)
    # v1 legacy fields
    main_bullet: str = ""
    context: Optional[str] = None
    implication: Optional[str] = None
    entities: list[str] = Field(default_factory=list)
    composite_score: float
    significance_level: Optional[str] = None
    cluster: Optional[str] = None
    continuity: Optional[str] = None
    is_model_release: bool = False
    model_release_data: Optional[ModelReleaseData] = None
    depth: str


class BriefMetadata(BaseModel):
    date: str
    generated_at: str
    total_items: int
    section_counts: dict[str, int]
    lead_story_id: str


class FinalBrief(BaseModel):
    brief_metadata: BriefMetadata
    items: list[FinalBriefItem]


class EditLogEntry(BaseModel):
    entry: str
    type: str
    original: str
    corrected: str
    reason: str


class EditorOutput(BaseModel):
    final_brief: FinalBrief
    email_brief: Optional[str] = None
    edit_log: list[EditLogEntry]


# ---------------------------------------------------------------------------
# Entity Classifier stage
#
# Runs AFTER Ghostwriter. Classifies each item's `primary_entity` into one of
# 10 categories aligned with `entity_logos.category`. The frontend uses the
# category to pick an industry-appropriate lucide-react icon when the entity
# doesn't have a real logo in the entity_logos table.
#
# See backend/pipeline/entity_classifier.py and
# prompts/entity_classifier_prompt.md for details.
# ---------------------------------------------------------------------------


EntityCategory = Literal[
    "company", "university", "government", "energy", "finance",
    "defense", "org", "model", "country", "other",
]


class EntityClassification(BaseModel):
    """A single item's classification output."""
    id: str
    primary_entity_category: EntityCategory
    rationale: Optional[str] = None  # one short line, for audit


class EntityClassificationOutput(BaseModel):
    """Output schema for the Entity Classifier agent."""
    classifications: list[EntityClassification]


# ---------------------------------------------------------------------------
# Event-tuple extraction stage (Phase 2 of structural plan)
#
# Runs BETWEEN date-filtering and within-day dedup. Replaces the prompt-clause
# arms race that the LLM-judged dedup stages required (counterpart-aware,
# NEW PRINCIPAL, FORWARD-LOOKING) with mechanical tuple comparison.
#
# The tuple captures the structural identity of an event so downstream stages
# (within-day dedup, cross-day history_dedup) can compare items by event
# fingerprint instead of by free-form Haiku judgment on headline strings.
#
# Live-validated 4/4 against the conflation cases the prompt clauses were
# fighting (Abdullah-UK ↔ Abdullah-US, Vance ↔ Trump Pakistan, GPT-5.5
# paraphrase, Tencent invests/licenses). See `/tmp/structural_tests.py` T2.
#
# See backend/pipeline/event_tuples.py and
# prompts/event_extraction_prompt.md for details.
# ---------------------------------------------------------------------------


# Closed event-type vocabulary. Constrained-decoding via Anthropic Structured
# Outputs (Nov 2025 GA) enforces this enum at inference, so we get a valid
# value or no value — never a hallucinated bucket. The `other` fallback is
# explicit so the judge has somewhere to route hard-to-classify items
# without lying about a more-specific bucket.
EventType = Literal[
    "bilateral_meeting",      # diplomatic / intergovernmental meeting (named counterparts)
    "trade_deal",             # commercial agreement, MoU, partnership
    "acquisition",            # M&A, takeover, asset purchase
    "funding_round",          # equity investment, venture round, IPO
    "product_release",        # model launch, software/SaaS release, hardware unveil
    "personnel_change",       # hire / fire / promote / appoint / resign
    "regulatory_action",      # law, sanction, fine, court ruling, agency directive
    "military_operation",     # strike, deployment, blockade, seizure
    "diplomatic_action",      # statement, withdrawal, visit cancellation, summit
    "earnings",               # quarterly / annual financial results
    "infrastructure",         # data center, plant, network buildout
    "research_finding",       # scientific result, benchmark publication, paper
    "other",                  # explicit fallback when none of the above fits
]


class EventTuple(BaseModel):
    """Structural fingerprint of a news event extracted from a headline.

    Be EXTRACTIVE — every field except `event_type` and `action` may be
    null when the headline doesn't name them. Don't guess.
    """
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    primary_actor: Optional[str] = Field(
        default=None,
        description=(
            "The principal entity taking the action — typically the headline's "
            "subject. For 'Trump cancels Pakistan trip', primary_actor is "
            "'Trump'. For 'OpenAI releases GPT-5.5', primary_actor is 'OpenAI'. "
            "Null only if the headline names no clear actor."
        ),
    )
    counterpart: Optional[str] = Field(
        default=None,
        description=(
            "The other party in a bilateral / transactional event. For "
            "'Abdullah bin Zayed meets UK Foreign Secretary', counterpart is "
            "'UK Foreign Secretary'. For 'Tencent invests in DeepSeek', "
            "counterpart is 'DeepSeek'. Null when the event has only one "
            "principal (e.g. 'OpenAI releases GPT-5.5'). This is the field "
            "that lets the dedup judge distinguish 'Abdullah-UK' from "
            "'Abdullah-US' mechanically."
        ),
    )
    action: str = Field(
        description=(
            "Short verb phrase capturing the action. Lemmatised where "
            "possible (e.g. 'cancels' or 'cancel') so two paraphrases "
            "share an action token. ~1-5 words."
        ),
    )
    location: Optional[str] = Field(default=None)
    date_or_period: Optional[str] = Field(
        default=None,
        description="Calendar reference if any: 'May 20', 'Q1 2026', 'next week'.",
    )
    key_numbers: list[str] = Field(
        default_factory=list,
        description=(
            "Dollar amounts, percentages, counts mentioned in the headline. "
            "Extracted as strings to preserve units ('$10B', '10%', '8,000 employees')."
        ),
    )

    @field_validator("key_numbers", mode="before")
    @classmethod
    def _coerce_key_numbers(cls, v):
        """Sonnet/Haiku occasionally emits null for empty list fields."""
        return _coerce_none_to_empty_list(v)


class EventTupleVerdict(BaseModel):
    """One extracted tuple, keyed back to the input item index."""
    model_config = ConfigDict(extra="forbid")

    id: int = Field(description="0-based index into the input items list.")
    tuple_: EventTuple = Field(
        alias="tuple",
        description="Extracted event tuple. Field name uses alias 'tuple' "
                    "in JSON because `tuple` is reserved in Python.",
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EventTupleBatchOutput(BaseModel):
    """Output schema for the event-tuple extraction stage.

    One verdict per input item, in input order. Anthropic Structured
    Outputs validates this at inference time, so we get either a fully
    valid object or a clear validation error to fall back on.
    """
    model_config = ConfigDict(extra="forbid")

    verdicts: list[EventTupleVerdict]
