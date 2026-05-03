"use client";

import { useState, useEffect } from "react";
import type { BriefItem, ModelReleaseData } from "@/lib/types/brief";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import {
  ExternalLink,
  Pencil,
  Bookmark,
  Share2,
  Search,
  Clock,
} from "lucide-react";
import { renderMarkdown } from "@/lib/rendering/markdown";
import { useBriefInteraction } from "@/lib/contexts/BriefInteractionContext";
import ActionBarButton from "@/components/brief/ActionBarButton";

interface BriefItemCardProps {
  item: BriefItem;
}

function isHttpUrl(url: string | undefined): url is string {
  return typeof url === "string" && /^https?:\/\//i.test(url.trim());
}

const MODEL_CARD_RELEASE_CUE_RE =
  /\b(release(?:d|s)?|launch(?:ed|es)?|unveil(?:ed|s)?|introduc(?:ed|es)?|announce(?:d|s)?|debut(?:ed|s)?|ship(?:ped|s)?|roll(?:ed)? out|made available|developer preview|general availability|model card)\b/i;
const MODEL_CARD_DEPLOYMENT_CUE_RE =
  /\b(api|sdk|docs?|documentation|playground|endpoint|console|platform|model card|developer preview|general availability|chat interface|available in the api|available via api|available on vertex|available on bedrock)\b/i;
const MODEL_CARD_DEPLOYMENT_URL_RE =
  /(platform\.|\/docs\b|model-card|ai\.google\.dev|build\.nvidia\.com|azure|bedrock|vertex)/i;
const MODEL_CARD_FUNDING_CUE_RE =
  /\b(raise(?:s|d)?|raising|funding|valuation|series [a-z]|seed round|backed|investors?|in talks|to build|building|plans to build|aims to build|acquisition|acquire(?:d|s)?|merger|ipo)\b/i;
const MODEL_CARD_MARKET_CUE_RE =
  /\b(token consumption|weekly rankings?|weekly usage|usage volume|market share|dominates?|dominated|surpasses?|surpassed|overtakes?|overtaken|overtook|ecosystem|same period|week of|price advantage)\b/i;
const MODEL_CARD_RESEARCH_CUE_RE =
  /\b(paper|research paper|study|preprint|published|publication|journal|nature|arxiv|evaluation|leaderboard|peer review|scientific work|scientific discovery|automated research system)\b/i;
const MODEL_CARD_SCIENCE_DOMAIN_CUE_RE =
  /\b(fmri|brain activity|brain responses?|neuroscience|algonauts|protein|proteins|genomic|genomics|molecular|structural biology|drug discovery|materials science|subjects|voxels?)\b/i;

/** Uniform styling for all Full Brief section items — steel blue left border. */
const itemStyles = {
  border: "border-l-[3px] border-l-sig-medium",
  bg: "bg-bg-secondary",
  headline: "text-[1.25rem] font-semibold text-text-primary",
  padding: "px-5 py-4",
};

/** Detect whether model_release_data uses the new structured format. */
function isNewFormat(data: ModelReleaseData): boolean {
  return !!(data.summary_pitch || (data.key_numbers && data.key_numbers.length > 0));
}

function shouldRenderModelReleaseCard(item: BriefItem): boolean {
  if (!item.is_model_release || !item.model_release_data) {
    return false;
  }

  const data = item.model_release_data;
  const text = [
    item.headline,
    item.main_bullet,
    item.context,
    item.implication,
    item.section,
    item.source_name,
    item.source_url,
    data.developer,
    data.model_name,
    data.summary_pitch,
    data.architecture,
    data.training,
    data.availability,
    data.specs,
    data.performance,
    data.commercials,
    ...(data.key_numbers ?? []).flatMap((entry) => [
      entry.label,
      entry.value,
      entry.qualifier,
    ]),
    ...(data.benchmarks?.models ?? []),
    ...(data.benchmarks?.rows ?? []).flatMap((row) => [
      row.benchmark,
      ...row.scores,
    ]),
  ]
    .filter(Boolean)
    .join(" ");

  if (!data.model_name || MODEL_CARD_FUNDING_CUE_RE.test(text) || MODEL_CARD_MARKET_CUE_RE.test(text)) {
    return false;
  }

  const hasDeploymentCue =
    MODEL_CARD_DEPLOYMENT_CUE_RE.test(text) ||
    (isHttpUrl(item.source_url) && MODEL_CARD_DEPLOYMENT_URL_RE.test(item.source_url)) ||
    item.additional_sources.some(
      (src) => isHttpUrl(src.url) && MODEL_CARD_DEPLOYMENT_URL_RE.test(src.url)
    );

  if (
    (MODEL_CARD_RESEARCH_CUE_RE.test(text) || MODEL_CARD_SCIENCE_DOMAIN_CUE_RE.test(text)) &&
    !hasDeploymentCue
  ) {
    return false;
  }

  return MODEL_CARD_RELEASE_CUE_RE.test(text) || hasDeploymentCue;
}

/** New 5-section model release card. Falls back to legacy grid for old data. */
function ModelReleaseCard({
  data,
  item,
}: {
  data: ModelReleaseData;
  item: BriefItem;
}) {
  if (!isNewFormat(data)) {
    // Legacy fallback: old label-value grid
    return (
      <div className="rounded-sm border border-accent-primary/30 bg-accent-primary/[0.03] p-4 space-y-3">
        <span className="font-mono text-[13px] uppercase tracking-[0.1em] text-accent-primary">
          Model Release
        </span>
        <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <span className="font-mono text-[13px] text-text-muted">Developer</span>
          <span className="font-sans text-text-primary">{data.developer}</span>
          <span className="font-mono text-[13px] text-text-muted">Model</span>
          <span className="font-sans text-text-bright font-medium">{data.model_name}</span>
          {data.specs && (
            <>
              <span className="font-mono text-[13px] text-text-muted">Specs</span>
              <span className="font-sans text-text-primary">{data.specs}</span>
            </>
          )}
          {data.performance && (
            <>
              <span className="font-mono text-[13px] text-text-muted">Performance</span>
              <span className="font-sans text-text-primary">{data.performance}</span>
            </>
          )}
          {data.commercials && (
            <>
              <span className="font-mono text-[13px] text-text-muted">Pricing</span>
              <span className="font-sans text-text-primary">{data.commercials}</span>
            </>
          )}
        </div>
      </div>
    );
  }

  const benchmarks = data.benchmarks;
  const hasKeyNumbers = data.key_numbers && data.key_numbers.length > 0;
  const hasBenchmarks = benchmarks && benchmarks.rows && benchmarks.rows.length > 0;
  const hasArchOrTraining = data.architecture || data.training;
  const hasAvailability = !!data.availability;
  const highlightedModelIndexes = new Set(
    benchmarks?.highlighted_model_indexes?.length
      ? benchmarks.highlighted_model_indexes
      : benchmarks
        ? [benchmarks.highlighted_model_index]
        : []
  );

  // Collect all source names for the header bar
  const sourceNames: string[] = [];
  if (item.source_name) sourceNames.push(item.source_name);
  for (const src of item.additional_sources) {
    if (src.name && !sourceNames.includes(src.name)) sourceNames.push(src.name);
  }

  return (
    <div className="rounded-sm border border-accent-primary/30 overflow-hidden">
      {/* Section 1: Header bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-primary bg-accent-primary/[0.03]">
        <span className="font-mono text-[13px] uppercase tracking-[0.1em] text-accent-primary font-medium">
          Model Release
        </span>
        {sourceNames.length > 0 && (
          <span className="font-mono text-[13px] text-text-muted truncate ml-4">
            {sourceNames.join(" \u00B7 ")}
          </span>
        )}
      </div>

      {/* Section 2: Identity block */}
      <div className="px-4 pt-3.5 pb-3">
        <p className="font-sans text-[14px] text-text-muted">{data.developer}</p>
        <p className="font-sans text-[22px] font-medium text-text-bright leading-tight mt-0.5">
          {data.model_name}
        </p>
        {data.summary_pitch && (
          <p className="font-sans text-[15px] text-text-secondary leading-relaxed mt-2">
            {data.summary_pitch}
          </p>
        )}
      </div>

      {/* Section 3: Key numbers strip */}
      {hasKeyNumbers && (
        <div className="grid grid-cols-2 sm:grid-cols-4 border-t border-b border-border-primary bg-bg-tertiary/50">
          {data.key_numbers!.map((kn, idx) => (
            <div
              key={kn.label}
              className={cn(
                "px-3 sm:px-4 py-3 text-center",
                idx % 2 !== 0 && "border-l border-border-primary",
                idx >= 2 && "border-t sm:border-t-0",
                idx >= 2 && idx % 2 === 0 && "border-l-0",
                idx >= 1 && "sm:border-l"
              )}
            >
              <p className="font-mono text-[11px] sm:text-[12px] uppercase tracking-[0.08em] text-text-muted">
                {kn.label}
              </p>
              <p className="font-sans text-[15px] sm:text-[17px] font-medium text-text-bright mt-0.5">
                {kn.value}
              </p>
              {kn.qualifier && (
                <p className="font-mono text-[11px] sm:text-[12px] text-text-muted mt-0.5">
                  {kn.qualifier}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Section 4: Benchmark comparison table */}
      {hasBenchmarks && (
        <div className="px-4 py-3 border-b border-border-primary">
          <p className="font-mono text-[12px] uppercase tracking-[0.08em] text-text-muted mb-2">
            Performance
          </p>
          {/* Mobile: stacked benchmark rows */}
          <div className="sm:hidden">
            {benchmarks!.rows.map((row) => (
              <div
                key={row.benchmark}
                className="py-2.5 border-b border-border-primary/50 last:border-0"
              >
                <p className="font-sans text-[13px] text-text-secondary mb-1.5">
                  {row.benchmark}
                </p>
                <div className="flex flex-wrap gap-x-5 gap-y-1">
                  {benchmarks!.models.map((model, idx) => (
                    <span
                      key={model}
                      className={cn(
                        "font-mono text-[13px]",
                        highlightedModelIndexes.has(idx)
                          ? "text-text-bright"
                          : "text-text-muted"
                      )}
                    >
                      <span className="text-[11px] text-text-dim">{model}</span>
                      {" "}
                      {row.scores[idx]}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Desktop: comparison table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-[14px]">
              <thead>
                <tr className="border-b border-border-primary">
                  <th className="text-left font-mono text-[13px] text-text-muted font-normal pb-2 pr-3" />
                  {benchmarks!.models.map((model, idx) => (
                    <th
                      key={model}
                      className={cn(
                        "text-right font-mono text-[13px] font-normal pb-2 px-2 whitespace-nowrap",
                        highlightedModelIndexes.has(idx)
                          ? "text-text-bright font-medium"
                          : "text-text-muted"
                      )}
                    >
                      {model}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {benchmarks!.rows.map((row) => (
                  <tr key={row.benchmark} className="border-b border-border-primary/50 last:border-0">
                    <td className="text-left font-sans text-text-secondary py-1.5 pr-3 whitespace-nowrap">
                      {row.benchmark}
                    </td>
                    {row.scores.map((score: string, idx: number) => (
                      <td
                        key={`${row.benchmark}-${idx}`}
                        className={cn(
                          "text-right font-mono py-1.5 px-2 whitespace-nowrap",
                          highlightedModelIndexes.has(idx)
                            ? "text-text-bright bg-accent-primary/[0.05]"
                            : "text-text-secondary"
                        )}
                      >
                        {score}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {benchmarks!.summary && (
            <p className="font-sans text-[14px] text-text-secondary mt-2 leading-relaxed">
              {benchmarks!.summary}
            </p>
          )}
        </div>
      )}

      {/* Section 5: Architecture & Availability */}
      {(hasArchOrTraining || hasAvailability) && (
        <div className="px-4 py-3 space-y-3">
          {hasArchOrTraining && (
            <div className={cn("grid gap-4", data.architecture && data.training ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1")}>
              {data.architecture && (
                <div>
                  <p className="font-mono text-[12px] uppercase tracking-[0.08em] text-text-muted mb-1">
                    Architecture
                  </p>
                  <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                    {data.architecture}
                  </p>
                </div>
              )}
              {data.training && (
                <div>
                  <p className="font-mono text-[12px] uppercase tracking-[0.08em] text-text-muted mb-1">
                    Training
                  </p>
                  <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                    {data.training}
                  </p>
                </div>
              )}
            </div>
          )}
          {hasAvailability && (
            <div>
              <p className="font-mono text-[12px] uppercase tracking-[0.08em] text-text-muted mb-1">
                Availability
              </p>
              <p className="font-sans text-[14px] text-text-secondary leading-relaxed">
                {data.availability}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function BriefItemCard({ item }: BriefItemCardProps) {
  const [open, setOpen] = useState(false);
  const styles = itemStyles;

  const {
    markAsRead,
    isRead,
    hasFlag,
    toggleFlag,
    getRequestForItem,
    setAnnotationPanelOpen,
    setSelectedItemId,
    setResearchDialogItemId,
    setShareDialogItemId,
    expandedItemId,
    setExpandedItemId,
  } = useBriefInteraction();

  // External expansion trigger (keyboard nav or other external UI actions)
  useEffect(() => {
    if (expandedItemId === item.id) {
      setOpen(true);
      if (!isRead(item.id)) markAsRead(item.id);
      setExpandedItemId(null);
    }
  }, [expandedItemId, item.id, setExpandedItemId, isRead, markAsRead]);

  function handleOpenChange(isOpen: boolean) {
    setOpen(isOpen);
    if (isOpen && !isRead(item.id)) {
      markAsRead(item.id);
    }
  }

  // Action bar handlers
  function handleAnnotate() {
    setSelectedItemId(item.id);
    setAnnotationPanelOpen(true);
  }

  function handleResearch() {
    setResearchDialogItemId(item.id);
  }

  function handleShare() {
    setShareDialogItemId(item.id);
  }

  const researchRequest = getRequestForItem(item.id);
  const isNewsletterProvenance =
    item.source_origin === "newsletter" ||
    (!item.source_url && item.additional_sources.length > 0);
  const linkedSourceLabel =
    !item.source_url && item.additional_sources.length === 1
      ? item.additional_sources[0].name
      : null;
  const provenanceLabel = isNewsletterProvenance
    ? `${item.source_name} digest`
    : item.source_name;
  const modelReleaseData = item.model_release_data;
  const showModelReleaseCard =
    shouldRenderModelReleaseCard(item) && !!modelReleaseData;

  return (
    <Collapsible open={open} onOpenChange={handleOpenChange}>
      <div
        data-item-id={item.id}
        className={cn(
          "rounded-sm transition-colors duration-150 relative",
          styles.border,
          styles.bg,
          "hover:bg-bg-tertiary"
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className={cn(
              "flex w-full items-start gap-3 text-left cursor-pointer",
              styles.padding
            )}
          >
            {/* Chevron caret */}
            <span
              className={cn(
                "mt-1 text-text-muted text-xs shrink-0 transition-transform duration-300 inline-block",
                open && "rotate-90"
              )}
            >
              &#x25B8;
            </span>

            <div className="flex-1 min-w-0">
              <h3 className={cn("font-serif leading-snug", styles.headline)}>
                {item.headline}
              </h3>

              {/* Collapsed metadata — source name */}
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[14px] text-text-muted">
                  {provenanceLabel}
                </span>
                {linkedSourceLabel && linkedSourceLabel !== item.source_name && (
                  <span className="font-mono text-[13px] text-text-muted/80">
                    via {linkedSourceLabel}
                  </span>
                )}
              </div>
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent className="overflow-hidden">
          <div className="px-6 pb-5 pl-12 space-y-0">
            {showModelReleaseCard && modelReleaseData ? (
              /* Model release: structured data card */
              <>
                <ModelReleaseCard data={modelReleaseData} item={item} />

                {item.implication && (
                  <>
                    <div className="border-t border-dotted border-border-primary my-3" />
                    <div>
                      <span className="font-mono text-[13px] uppercase tracking-[0.1em] text-text-muted">
                        Implication
                      </span>
                      <p className="font-sans text-text-secondary text-sm mt-1 leading-relaxed">
                        {renderMarkdown(item.implication)}
                      </p>
                    </div>
                  </>
                )}
              </>
            ) : (
              /* Standard item: main bullet -> context -> implication */
              <>
                <p className="font-sans text-text-primary text-sm leading-relaxed">
                  {renderMarkdown(item.main_bullet)}
                </p>

                {item.context && (
                  <>
                    <div className="border-t border-dotted border-border-primary my-3" />
                    <div>
                      <span className="font-mono text-[13px] uppercase tracking-[0.1em] text-text-muted">
                        Context
                      </span>
                      <p className="font-sans text-text-secondary text-sm mt-1 leading-relaxed">
                        {renderMarkdown(item.context)}
                      </p>
                    </div>
                  </>
                )}

                {item.implication && (
                  <>
                    <div className="border-t border-dotted border-border-primary my-3" />
                    <div>
                      <span className="font-mono text-[13px] uppercase tracking-[0.1em] text-text-muted">
                        Implication
                      </span>
                      <p className="font-sans text-text-secondary text-sm mt-1 leading-relaxed">
                        {renderMarkdown(item.implication)}
                      </p>
                    </div>
                  </>
                )}
              </>
            )}

            {/* Source link */}
            <div className="flex flex-wrap items-center gap-3 pt-3 mt-3 border-t border-border-primary">
              {isHttpUrl(item.source_url) && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-[13px] text-text-muted hover:text-accent-primary transition-colors duration-150"
                >
                  {item.source_name}
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {item.additional_sources.length > 0 &&
                item.additional_sources
                  .filter((src) => isHttpUrl(src.url))
                  .map((src, idx) => (
                  <a
                    key={`${src.name}-${idx}`}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-[13px] text-text-muted hover:text-accent-primary transition-colors duration-150"
                  >
                    {src.name}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ))}
            </div>

            {/* ─── Action Bar ─────────────────────────────────────────── */}
            <div className="border-t border-dotted border-border-primary mt-3 pt-3">
              <div className="flex flex-wrap items-center gap-1">
                <ActionBarButton
                  icon={Pencil}
                  label="Annotate"
                  onClick={handleAnnotate}
                />
                <ActionBarButton
                  icon={Bookmark}
                  label="Flag"
                  active={hasFlag(item.id)}
                  activeColor="text-sig-high"
                  onClick={() => toggleFlag(item.id)}
                />
                <ActionBarButton
                  icon={Share2}
                  label="Share"
                  onClick={handleShare}
                />
                <ActionBarButton
                  icon={Search}
                  label="Research"
                  onClick={handleResearch}
                />
              </div>

              {/* Research request status */}
              {researchRequest && (
                <div className="mt-2 flex items-center gap-2">
                  <Clock className="h-3 w-3 text-continuity" />
                  <span
                    className={cn(
                      "font-mono text-[13px]",
                      researchRequest.status === "pending" &&
                        "text-continuity",
                      researchRequest.status === "in_progress" &&
                        "text-accent-primary",
                      researchRequest.status === "completed" &&
                        "text-accent-success"
                    )}
                  >
                    {researchRequest.status === "pending" &&
                      "Research requested"}
                    {researchRequest.status === "in_progress" &&
                      "Research in progress"}
                    {researchRequest.status === "completed" &&
                      "Research available"}
                  </span>
                </div>
              )}

              {/* Research response block (when completed) */}
              {researchRequest?.status === "completed" &&
                researchRequest.response && (
                  <div className="mt-3 rounded-sm border border-accent-primary/30 bg-accent-primary/[0.03] p-4 space-y-2">
                    <span className="font-mono text-[13px] uppercase tracking-[0.1em] text-accent-primary">
                      Research Response
                    </span>
                    <p className="font-sans text-text-primary text-sm leading-relaxed">
                      {researchRequest.response}
                    </p>
                    {researchRequest.completed_at && (
                      <p className="font-mono text-[13px] text-text-muted">
                        Completed{" "}
                        {new Date(
                          researchRequest.completed_at
                        ).toLocaleString("en-GB", {
                          day: "numeric",
                          month: "long",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                          timeZone: "Asia/Dubai",
                        })}{" "}
                        GST
                      </p>
                    )}
                  </div>
                )}
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
