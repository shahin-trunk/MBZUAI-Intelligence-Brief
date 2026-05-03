"use client";

import { useState, useCallback, useRef, useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type {
  Engagement,
  EngagementFollowup,
  IntelBriefing,
  BioFacts,
  ConciseCV,
  ExtendedCV,
} from "@/lib/types/executive-engagement";
import { DossierSection } from "./DossierSection";
import { MaterialChip } from "./MaterialChip";
import { TeamRequestSection } from "./TeamRequestSection";
import { EditEngagementDialog } from "./EditEngagementDialog";

interface Props {
  engagement: Engagement;
  followups: EngagementFollowup[];
  isAdmin: boolean;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

function formatDayName(dateStr: string): string {
  return new Date(dateStr + "T00:00:00")
    .toLocaleDateString("en-US", { weekday: "long" })
    .toUpperCase();
}

function formatDayNumber(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").getDate().toString();
}

function formatMonth(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
    month: "long",
  });
}

function formatFullDate(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/**
 * Renders text with **bold** markers as gold-highlighted spans.
 * Used for backward-compat with old engagements that use markdown.
 */
function renderHighlightedText(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <span key={i} className="text-sig-high font-medium">
          {part.slice(2, -2)}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function getMiDescription(item: { description?: string; text?: string }): string {
  return item.description || item.text || "";
}

/** Check if engagement has new dual-bio data */
function hasNewBioData(engagement: Engagement): boolean {
  return !!(engagement.bio_concise_narrative && engagement.bio_extended_narrative);
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function MetadataPill({ children }: { children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center rounded-[6px] px-3 py-1 text-[12px]"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid var(--border-subtle)",
        color: "#7A8194",
      }}
    >
      {children}
    </span>
  );
}

/* ── Profile Toggle ── */

function ProfileToggle({
  mode,
  onModeChange,
}: {
  mode: "concise" | "extended";
  onModeChange: (m: "concise" | "extended") => void;
}) {
  return (
    <div
      role="tablist"
      className="flex items-center gap-0.5 rounded-[8px] p-[3px]"
      style={{ background: "rgba(255,255,255,0.07)" }}
    >
      {(["concise", "extended"] as const).map((m) => {
        const isActive = mode === m;
        return (
          <button
            key={m}
            role="tab"
            type="button"
            aria-selected={isActive}
            onClick={() => onModeChange(m)}
            className="rounded-[6px] px-[18px] py-1.5 text-[13px] transition-all duration-150 cursor-pointer"
            style={{
              fontWeight: isActive ? 600 : 500,
              color: isActive ? "#1A1A1A" : "#9BA2B2",
              background: isActive ? "#E8DCC8" : "transparent",
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = "rgba(255,255,255,0.05)";
                e.currentTarget.style.color = "#C8CCD4";
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "#9BA2B2";
              }
            }}
          >
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </button>
        );
      })}
    </div>
  );
}

/* ── CV Sidebar (concise) ── */

function ConciseCVSidebar({ cv }: { cv: ConciseCV }) {
  return (
    <div
      className="w-full md:w-[220px] md:shrink-0 py-5 px-6 border-b md:border-b-0 md:border-r border-white/[0.04]"
    >
      {cv.current.length > 0 && (
        <div>
          <p
            className="font-mono text-[9.5px] uppercase text-text-dim mb-2.5"
            style={{ letterSpacing: "0.07em" }}
          >
            Current
          </p>
          <div className="space-y-2.5">
            {cv.current.map((r, i) => (
              <div key={i}>
                <p className="text-[13px] font-semibold text-text-primary">{r.org}</p>
                <p className="text-[12px] text-text-secondary" style={{ color: "#7A8194" }}>
                  {r.role}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {cv.key_recognition.length > 0 && (
        <div style={{ marginTop: cv.current.length > 0 ? 16 : 0 }}>
          <p
            className="font-mono text-[9.5px] uppercase text-text-dim mb-2.5"
            style={{ letterSpacing: "0.07em" }}
          >
            Key Recognition
          </p>
          <div className="space-y-1.5">
            {cv.key_recognition.map((r, i) => (
              <p key={i} className="text-[12px] text-text-secondary" style={{ lineHeight: 1.5 }}>
                {r}
              </p>
            ))}
          </div>
        </div>
      )}

      {cv.education && cv.education.length > 0 && (
        <div className="mt-4">
          <p
            className="font-mono text-[9.5px] uppercase text-text-dim mb-2.5"
            style={{ letterSpacing: "0.07em" }}
          >
            Education
          </p>
          <div className="space-y-1.5">
            {cv.education.map((r, i) => (
              <p key={i} className="text-[12px] text-text-secondary" style={{ lineHeight: 1.5 }}>
                {r}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── CV Sidebar (extended) ── */

function ExtendedCVSidebar({ cv }: { cv: ExtendedCV }) {
  return (
    <div
      className="w-full md:w-[260px] md:shrink-0 py-5 px-6 border-b md:border-b-0 md:border-r border-white/[0.04]"
    >
      {cv.current.length > 0 && (
        <div>
          <p
            className="font-mono text-[9.5px] uppercase text-text-dim mb-2.5"
            style={{ letterSpacing: "0.07em" }}
          >
            Current
          </p>
          <div className="space-y-2.5">
            {cv.current.map((r, i) => (
              <div key={i}>
                <p className="text-[13px] font-semibold text-text-primary">{r.org}</p>
                <p className="text-[12px]" style={{ color: "#7A8194" }}>
                  {r.role}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {cv.previous.length > 0 && (
        <div className="mt-4">
          <p
            className="font-mono text-[9.5px] uppercase text-text-dim mb-2.5"
            style={{ letterSpacing: "0.07em" }}
          >
            Previous
          </p>
          <div className="space-y-2.5">
            {cv.previous.map((r, i) => (
              <div key={i} className="mb-2.5">
                <p className="text-[13px] font-semibold text-text-primary">{r.org}</p>
                <p className="text-[12px]" style={{ color: "#7A8194" }}>
                  {r.role}
                </p>
                {r.dates && (
                  <p className="text-[11px] text-text-dim">{r.dates}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {cv.recognition.length > 0 && (
        <div className="mt-4">
          <p
            className="font-mono text-[9.5px] uppercase text-text-dim mb-2.5"
            style={{ letterSpacing: "0.07em" }}
          >
            Recognition
          </p>
          <div className="space-y-1.5">
            {cv.recognition.map((r, i) => (
              <p key={i} className="text-[12px] text-text-secondary" style={{ lineHeight: 1.5 }}>
                {r}
              </p>
            ))}
          </div>
        </div>
      )}

      {cv.education && cv.education.length > 0 && (
        <div className="mt-4">
          <p
            className="font-mono text-[9.5px] uppercase text-text-dim mb-2.5"
            style={{ letterSpacing: "0.07em" }}
          >
            Education
          </p>
          <div className="space-y-1.5">
            {cv.education.map((r, i) => (
              <p key={i} className="text-[12px] text-text-secondary" style={{ lineHeight: 1.5 }}>
                {r}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Legacy single-mode bio (backward compat) ── */

function LegacyBioCard({ facts }: { facts: BioFacts }) {
  return (
    <div
      className="w-full md:w-[210px] md:shrink-0 rounded-[14px] p-5 space-y-4"
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "0.5px solid var(--border-primary)",
      }}
    >
      {facts.current_roles.length > 0 && (
        <div>
          <p className="font-mono text-[9.5px] uppercase text-text-muted mb-1.5" style={{ letterSpacing: "0.1em" }}>Current</p>
          <div className="space-y-1">
            {facts.current_roles.map((r, i) => (
              <p key={i} className="text-[12.5px] text-text-secondary leading-[1.5]">
                <span className="font-medium text-text-primary">{r.org}</span>{" — "}{r.role}
              </p>
            ))}
          </div>
        </div>
      )}
      {facts.previous_roles.length > 0 && (
        <div>
          <p className="font-mono text-[9.5px] uppercase text-text-muted mb-1.5" style={{ letterSpacing: "0.1em" }}>Previous</p>
          <div className="space-y-1">
            {facts.previous_roles.map((r, i) => (
              <p key={i} className="text-[12.5px] text-text-secondary leading-[1.5]">
                <span className="font-medium text-text-primary">{r.org}</span>{" — "}{r.role}
                {r.years && <span className="text-text-dim ml-1 text-[11px]">({r.years})</span>}
              </p>
            ))}
          </div>
        </div>
      )}
      {facts.recognition.length > 0 && (
        <div>
          <p className="font-mono text-[9.5px] uppercase text-text-muted mb-1.5" style={{ letterSpacing: "0.1em" }}>Recognition</p>
          <div className="space-y-0.5">
            {facts.recognition.map((r, i) => (
              <p key={i} className="text-[12.5px] text-text-secondary leading-[1.5]">{r}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Intel Briefing Section (replaces Research Assistant) ── */

function IntelBriefingSection({
  engagementId,
  visitorName,
  visitorOrg,
  initialBriefings,
  researchChips,
  initialFollowups,
}: {
  engagementId: string;
  visitorName: string;
  visitorOrg: string;
  initialBriefings: IntelBriefing[];
  researchChips: string[];
  initialFollowups: EngagementFollowup[];
}) {
  const [briefings, setBriefings] = useState<IntelBriefing[]>(initialBriefings);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  // Follow-up input state (compact bar at bottom)
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [followups, setFollowups] = useState<EngagementFollowup[]>(initialFollowups);
  const [latestAnswer, setLatestAnswer] = useState<{
    answer: string;
    detail: string | null;
  } | null>(null);
  const [followupError, setFollowupError] = useState("");

  // Poll for pending briefings
  useEffect(() => {
    const hasPending = briefings.some((b) => b.status === "pending");
    if (!hasPending) return;

    let elapsed = 0;
    const interval = setInterval(async () => {
      elapsed += 5000;
      if (elapsed > 120_000) {
        clearInterval(interval);
        // Timeout — mark remaining pending as error
        setBriefings((prev) =>
          prev.map((b) =>
            b.status === "pending"
              ? { ...b, answer: "Research timed out.", detail: null, status: "error" as const }
              : b
          )
        );
        return;
      }

      try {
        const res = await fetch(`/api/internal/engagements/${engagementId}/intel-briefings`);
        const data = await res.json();
        if (data.briefings) {
          setBriefings(data.briefings);
          if (data.briefings.every((b: IntelBriefing) => b.status !== "pending")) {
            clearInterval(interval);
          }
        }
      } catch {
        // Silently retry on next interval
      }
    }, 5000);

    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engagementId, briefings.filter((b) => b.status === "pending").length]);

  // Follow-up submit handler
  const handleFollowupSubmit = useCallback(
    async (searchQuery?: string) => {
      const trimmed = (searchQuery || query).trim();
      if (!trimmed || isSearching) return;

      setIsSearching(true);
      setFollowupError("");
      setLatestAnswer(null);

      try {
        const res = await fetch("/api/internal/engagement-followup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ engagementId, question: trimmed }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Search failed");

        const followup = data.followup;
        setLatestAnswer({ answer: followup.answer, detail: followup.detail });
        setFollowups((prev) => [followup, ...prev]);
        setQuery("");
      } catch (err) {
        setFollowupError(err instanceof Error ? err.message : "Search failed");
      } finally {
        setIsSearching(false);
      }
    },
    [query, isSearching, engagementId]
  );

  // If no intel briefings, fall back to legacy research chips
  const hasIntelBriefings = briefings.length > 0;

  if (!hasIntelBriefings && researchChips.length === 0) {
    return null; // Nothing to show
  }

  return (
    <DossierSection
      label="Key Questions"
      variant="gold"
      count={briefings.length || undefined}
    >
      {hasIntelBriefings ? (
        <>
          {/* Briefing cards — 2-column grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
            {briefings.map((card) => {
              const isExpanded = expandedCard === card.id;
              const isPending = card.status === "pending";
              const isError = card.status === "error";

              return (
                <button
                  key={card.id}
                  type="button"
                  onClick={() =>
                    setExpandedCard(isExpanded ? null : card.id)
                  }
                  className="text-left rounded-[10px] px-5 py-4 transition-all duration-200"
                  style={{
                    background: isExpanded
                      ? "rgba(212,168,67,0.04)"
                      : "rgba(255,255,255,0.02)",
                    border: `1px solid ${
                      isExpanded
                        ? "rgba(212,168,67,0.2)"
                        : "var(--border-subtle)"
                    }`,
                  }}
                >
                  {/* Header row: topic badge + chevron */}
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <span
                      className="inline-flex items-center rounded-[4px] px-2 py-0.5 font-mono text-[9px] uppercase font-medium shrink-0"
                      style={{
                        background: "rgba(212,168,67,0.12)",
                        color: "#D4A843",
                        letterSpacing: "0.04em",
                      }}
                    >
                      {card.topic}
                    </span>
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 16 16"
                      fill="none"
                      stroke="var(--text-dim)"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="shrink-0 mt-0.5 transition-transform duration-200"
                      style={{
                        transform: isExpanded
                          ? "rotate(90deg)"
                          : "rotate(0deg)",
                      }}
                    >
                      <path d="M6 4l4 4-4 4" />
                    </svg>
                  </div>

                  {/* Question */}
                  <p
                    className="text-[13px] font-medium leading-[1.5]"
                    style={{
                      color: isExpanded
                        ? "var(--text-bright)"
                        : "var(--text-primary)",
                    }}
                  >
                    {card.question}
                  </p>

                  {/* Answer (expanded) */}
                  <div
                    style={{
                      maxHeight: isExpanded ? "500px" : "0",
                      opacity: isExpanded ? 1 : 0,
                      overflow: "hidden",
                      transition:
                        "max-height 300ms ease, opacity 200ms ease",
                    }}
                  >
                    {isPending ? (
                      <div className="mt-3 space-y-2">
                        <div
                          className="h-3 w-3/4 rounded"
                          style={{
                            background: "rgba(212,168,67,0.08)",
                            animation:
                              "skeleton-pulse 1.5s ease-in-out infinite",
                          }}
                        />
                        <div
                          className="h-3 w-1/2 rounded"
                          style={{
                            background: "rgba(212,168,67,0.06)",
                            animation:
                              "skeleton-pulse 1.5s ease-in-out infinite 0.2s",
                          }}
                        />
                        <p
                          className="text-[11px] font-medium mt-2"
                          style={{ color: "var(--sig-high)" }}
                        >
                          Researching...
                        </p>
                      </div>
                    ) : isError ? (
                      <p className="mt-3 text-[13px] text-text-dim italic">
                        {card.answer || "Could not research this topic."}
                      </p>
                    ) : (
                      <div className="mt-3">
                        <p className="text-[13px] text-text-secondary leading-[1.7]">
                          {card.answer}
                        </p>
                        {card.detail && (
                          <p className="text-[13px] text-text-dim leading-[1.7] mt-2">
                            {card.detail}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Compact follow-up bar */}
          <div className="mt-4">
            <div
              className="flex items-center gap-2.5 rounded-[8px] px-3.5 py-2"
              style={{
                background: "rgba(255,255,255,0.02)",
                border: `1px solid ${query ? "rgba(212,168,67,0.3)" : "rgba(255,255,255,0.06)"}`,
              }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 16 16"
                fill="none"
                stroke="var(--text-dim)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="shrink-0"
              >
                <circle cx="7" cy="7" r="5" />
                <path d="M12 12l-2.5-2.5" />
              </svg>

              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleFollowupSubmit();
                }}
                placeholder="Ask anything else about this person or organization..."
                disabled={isSearching}
                className="flex-1 bg-transparent text-[12px] text-text-primary placeholder:text-text-dim outline-none disabled:opacity-50"
              />

              <button
                type="button"
                onClick={() => handleFollowupSubmit()}
                disabled={isSearching || !query.trim()}
                className="shrink-0 rounded-[6px] px-3 py-1 text-[11px] font-medium transition-colors disabled:opacity-40"
                style={{
                  border: "1px solid rgba(212,168,67,0.25)",
                  color: "#D4A843",
                  background: "rgba(212,168,67,0.06)",
                }}
              >
                {isSearching ? "Searching..." : "Search"}
              </button>
            </div>

            {/* Searching indicator */}
            {isSearching && (
              <p
                className="mt-2 text-[11px] font-medium"
                style={{
                  color: "var(--sig-high)",
                  animation: "skeleton-pulse 1.5s ease-in-out infinite",
                }}
              >
                Searching the web...
              </p>
            )}

            {/* Follow-up error */}
            {followupError && (
              <p className="mt-1.5 text-[11px] text-red-400">{followupError}</p>
            )}

            {/* Latest follow-up answer */}
            {latestAnswer && (
              <div
                className="mt-2.5 rounded-[8px] px-3.5 py-3"
                style={{
                  background: "rgba(212,168,67,0.03)",
                  border: "1px solid rgba(212,168,67,0.12)",
                }}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: "var(--sig-high)" }}
                    />
                    <span
                      className="text-[10px] font-semibold text-sig-high"
                      style={{ letterSpacing: "0.06em" }}
                    >
                      ANSWER
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setLatestAnswer(null)}
                    className="text-[10px] text-text-dim hover:text-text-secondary transition-colors"
                  >
                    Dismiss
                  </button>
                </div>
                <p className="text-[13px] text-text-bright leading-[1.6]">
                  {latestAnswer.answer}
                </p>
                {latestAnswer.detail && (
                  <p className="text-[13px] text-text-secondary leading-[1.6] mt-1.5">
                    {latestAnswer.detail}
                  </p>
                )}
              </div>
            )}

            {/* Previous followups */}
            {followups.length > 0 && !latestAnswer && (
              <div className="mt-2.5 space-y-1.5">
                {followups.slice(0, 2).map((f) => (
                  <div
                    key={f.id}
                    className="rounded-[6px] px-3 py-2"
                    style={{ background: "rgba(148,163,184,0.04)" }}
                  >
                    <p className="text-[11px] text-text-dim mb-0.5">
                      {f.question}
                    </p>
                    <p className="text-[13px] text-text-secondary leading-[1.5]">
                      {f.answer}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : (
        /* Legacy fallback: research chips as clickable on-demand searches */
        <LegacyResearchChips
          engagementId={engagementId}
          visitorName={visitorName}
          visitorOrg={visitorOrg}
          researchChips={researchChips}
          initialFollowups={initialFollowups}
        />
      )}
    </DossierSection>
  );
}

/* ── Legacy Research Chips (backward compat for old engagements) ── */

function LegacyResearchChips({
  engagementId,
  visitorName,
  visitorOrg,
  researchChips,
  initialFollowups,
}: {
  engagementId: string;
  visitorName: string;
  visitorOrg: string;
  researchChips: string[];
  initialFollowups: EngagementFollowup[];
}) {
  const [followups, setFollowups] = useState<EngagementFollowup[]>(initialFollowups);
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [latestAnswer, setLatestAnswer] = useState<{
    answer: string;
    detail: string | null;
  } | null>(null);
  const [error, setError] = useState("");

  const handleSubmit = useCallback(
    async (searchQuery?: string) => {
      const trimmed = (searchQuery || query).trim();
      if (!trimmed || isSearching) return;

      setIsSearching(true);
      setError("");
      setLatestAnswer(null);

      try {
        const res = await fetch("/api/internal/engagement-followup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ engagementId, question: trimmed }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Search failed");

        const followup = data.followup;
        setLatestAnswer({ answer: followup.answer, detail: followup.detail });
        setFollowups((prev) => [followup, ...prev]);
        setQuery("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed");
      } finally {
        setIsSearching(false);
      }
    },
    [query, isSearching, engagementId]
  );

  return (
    <div className="space-y-3">
      <p className="text-[13px] text-text-dim">
        AI-powered research on {visitorName}
        {visitorOrg ? `, ${visitorOrg}` : ""}
      </p>

      <div className="flex flex-wrap gap-1.5">
        {researchChips.map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => {
              setQuery(chip);
              handleSubmit(chip);
            }}
            disabled={isSearching}
            className="rounded-full px-2.5 py-1 text-[11px] transition-colors cursor-pointer disabled:opacity-40 hover:opacity-80"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid var(--border-subtle)",
              color: "#7A8194",
            }}
          >
            {chip}
          </button>
        ))}
      </div>

      {isSearching && (
        <p
          className="text-[12px] font-medium"
          style={{
            color: "var(--sig-high)",
            animation: "skeleton-pulse 1.5s ease-in-out infinite",
          }}
        >
          Thinking — searching the web...
        </p>
      )}

      {error && <p className="text-[12px] text-red-400">{error}</p>}

      {latestAnswer && (
        <div
          className="rounded-[8px] px-4 py-3"
          style={{
            background: "rgba(212,168,67,0.03)",
            border: "1px solid rgba(212,168,67,0.12)",
          }}
        >
          <p className="text-[13px] text-text-bright leading-[1.6]">
            {latestAnswer.answer}
          </p>
          {latestAnswer.detail && (
            <p className="text-[13px] text-text-secondary leading-[1.6] mt-2">
              {latestAnswer.detail}
            </p>
          )}
        </div>
      )}

      {followups.length > 0 && !latestAnswer && (
        <div className="space-y-1.5">
          {followups.slice(0, 3).map((f) => (
            <div
              key={f.id}
              className="rounded-[6px] px-3 py-2"
              style={{ background: "rgba(148,163,184,0.04)" }}
            >
              <p className="text-[12px] text-text-dim mb-1">{f.question}</p>
              <p className="text-[13px] text-text-secondary leading-[1.6]">
                {f.answer}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export function FullDossierCard({ engagement, followups, isAdmin }: Props) {
  const router = useRouter();
  const [editOpen, setEditOpen] = useState(false);
  const [bioMode, setBioMode] = useState<"concise" | "extended">("concise");
  const [isUploading, setIsUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const isNewBio = hasNewBioData(engagement);

  // Material upload handler
  const handleUpload = useCallback(
    async (file: File) => {
      setIsUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch(
          `/api/internal/engagements/${engagement.id}/materials`,
          { method: "POST", body: formData }
        );
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.error || "Upload failed");
        }
        router.refresh();
      } catch {
        // Silently fail — user can retry via Edit dialog
      } finally {
        setIsUploading(false);
      }
    },
    [engagement.id, router]
  );

  // Legacy bio facts check
  const hasBioFacts =
    engagement.bio_facts &&
    (engagement.bio_facts.current_roles?.length > 0 ||
      engagement.bio_facts.previous_roles?.length > 0 ||
      engagement.bio_facts.recognition?.length > 0);

  return (
    <div className="space-y-3">
      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* Unified Dossier Card                                          */}
      {/* Header + Profile + Mutual Interest + Research Assistant        */}
      {/* ═══════════════════════════════════════════════════════════════ */}
      <div
        className="rounded-[10px] overflow-hidden"
        style={{
          background: "var(--surface-raised)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        {/* §3 — Header */}
        <div className="p-6">
          <div className="flex gap-5 items-start">
            {/* Initials avatar */}
            <div
              className="w-[56px] h-[56px] shrink-0 flex items-center justify-center rounded-[14px]"
              style={{ background: "rgba(212,168,67,0.12)" }}
            >
              <span className="text-[20px] font-semibold text-sig-high">
                {getInitials(engagement.visitor_name)}
              </span>
            </div>

            {/* Info block */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2.5">
                <p className="text-[22px] font-semibold text-text-primary">
                  {engagement.visitor_name}
                </p>
                {isAdmin && (
                  <button
                    type="button"
                    onClick={() => setEditOpen(true)}
                    className="w-8 h-8 flex items-center justify-center rounded-[8px] transition-colors hover:opacity-80"
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid var(--border-subtle)",
                    }}
                    title="Edit engagement"
                  >
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 16 16"
                      fill="none"
                      stroke="var(--text-dim)"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M11.5 1.5l3 3L5 14H2v-3L11.5 1.5z" />
                    </svg>
                  </button>
                )}
              </div>

              <p className="text-[14px] text-text-secondary mt-0.5 mb-3">
                {engagement.visitor_title}
                {engagement.visitor_organization &&
                  ` · ${engagement.visitor_organization}`}
              </p>

              <div className="flex flex-wrap gap-2">
                {engagement.time && <MetadataPill>{engagement.time}</MetadataPill>}
                {engagement.format && <MetadataPill>{engagement.format}</MetadataPill>}
                {engagement.location && <MetadataPill>{engagement.location}</MetadataPill>}
              </div>
            </div>

            {/* Date block */}
            <div
              className="shrink-0 flex flex-col items-center text-center rounded-[10px] px-[18px] py-3"
              style={{
                minWidth: 90,
                background: "rgba(212,168,67,0.08)",
                border: "1px solid rgba(212,168,67,0.2)",
              }}
              aria-label={formatFullDate(engagement.date)}
            >
              <span
                className="font-mono text-[9px] font-medium text-sig-high uppercase"
                style={{ letterSpacing: "0.08em" }}
              >
                {formatDayName(engagement.date)}
              </span>
              <span className="text-[28px] font-semibold text-text-primary" style={{ lineHeight: 1.1 }}>
                {formatDayNumber(engagement.date)}
              </span>
              <span className="text-[12px] text-text-secondary mt-0.5">
                {formatMonth(engagement.date)}
              </span>
            </div>
          </div>
        </div>

        {/* §4 — Profile (Bio with Toggle) */}
        {(isNewBio || engagement.bio) && (
          <>
            {/* Divider */}
            <div className="px-6">
              <div
                className="h-px w-full"
                style={{
                  background:
                    "linear-gradient(to right, transparent, rgba(212,168,67,0.15), transparent)",
                }}
              />
            </div>

            {/* Header bar */}
            <div
              className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
            >
              <span
                className="font-mono text-[10px] uppercase text-text-dim"
                style={{ letterSpacing: "0.07em" }}
              >
                Profile
              </span>
              {isNewBio && (
                <ProfileToggle mode={bioMode} onModeChange={setBioMode} />
              )}
            </div>

            {/* Body */}
            {isNewBio ? (
              <>
                {/* Concise mode */}
                <div className={bioMode === "concise" ? "flex flex-col md:flex-row" : "hidden"}>
                  <ConciseCVSidebar cv={engagement.bio_concise_cv!} />
                  <div className="flex-1 min-w-0 py-5 px-6">
                    <div
                      className="text-[15px] leading-[1.7]"
                      style={{ color: "#C8CCD4" }}
                      dangerouslySetInnerHTML={{
                        __html: engagement.bio_concise_narrative!,
                      }}
                    />
                  </div>
                </div>

                {/* Extended mode */}
                <div className={bioMode === "extended" ? "flex flex-col md:flex-row" : "hidden"}>
                  <ExtendedCVSidebar cv={engagement.bio_extended_cv!} />
                  <div className="flex-1 min-w-0 py-5 px-6">
                    {engagement.bio_extended_narrative!
                      .split("\n\n")
                      .map((paragraph, i) => (
                        <div
                          key={i}
                          className="text-[14px] text-text-secondary leading-[1.7]"
                          style={{ marginBottom: i < engagement.bio_extended_narrative!.split("\n\n").length - 1 ? 16 : 0 }}
                          dangerouslySetInnerHTML={{ __html: paragraph }}
                        />
                      ))}
                  </div>
                </div>
              </>
            ) : (
              /* Legacy single-mode bio */
              <div className="px-6 py-5">
                <div className="flex flex-col md:flex-row gap-5">
                  {hasBioFacts && <LegacyBioCard facts={engagement.bio_facts!} />}
                  <div className={`${hasBioFacts ? "flex-1 min-w-0" : "w-full"}`}>
                    <div className="text-[14px] text-text-secondary leading-[1.75] space-y-3">
                      {engagement.bio!.split("\n\n").map((paragraph, i) => (
                        <p key={i}>{renderHighlightedText(paragraph)}</p>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* §5 — Areas of Mutual Interest (inside unified card) */}
        {engagement.mutual_interests.length > 0 && (
          <DossierSection
            label="Areas of Mutual Interest"
            variant="gold"
            count={engagement.mutual_interests.length}
          >
            <div className="space-y-2">
              {engagement.mutual_interests.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-col gap-1.5 sm:grid sm:grid-cols-[180px_1fr] sm:items-start sm:gap-[14px] rounded-[10px] px-5 py-4"
                  style={{
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  {/* Topic badge — fixed grid column for consistent alignment */}
                  {item.topic && (
                    <span
                      className="inline-flex items-center justify-center rounded-[4px] px-2.5 py-1 font-mono text-[10px] uppercase font-medium mt-0.5"
                      style={{
                        background: "rgba(212,168,67,0.12)",
                        color: "#D4A843",
                        letterSpacing: "0.04em",
                        whiteSpace: "nowrap",
                        textAlign: "center",
                      }}
                    >
                      {item.topic}
                    </span>
                  )}
                  <span
                    className="text-[13px] text-text-secondary leading-[1.6]"
                    dangerouslySetInnerHTML={{ __html: getMiDescription(item) }}
                  />
                </div>
              ))}
            </div>
          </DossierSection>
        )}

        {/* §7 — Intel Briefing (inside unified card) */}
        <IntelBriefingSection
          engagementId={engagement.id}
          visitorName={engagement.visitor_name}
          visitorOrg={engagement.visitor_organization}
          initialBriefings={engagement.intel_briefings || []}
          researchChips={engagement.research_chips || []}
          initialFollowups={followups}
        />
      </div>

      {/* ═══════════════════════════════════════════════════════════════ */}
      {/* Compact footer sections (outside unified card)                */}
      {/* ═══════════════════════════════════════════════════════════════ */}

      {/* §8 — Prepared Materials (compact bar) */}
      <div
        className="rounded-[10px] px-5 py-3"
        style={{
          background: "var(--surface-raised)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        {/* Hidden file input */}
        {isAdmin && (
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleUpload(f);
              e.target.value = "";
            }}
          />
        )}

        <div className="flex items-center justify-between">
          <h4
            className="text-[11px] uppercase font-semibold font-mono text-text-secondary"
            style={{ letterSpacing: "0.06em" }}
          >
            Prepared Materials
          </h4>
          {isAdmin && engagement.materials.length === 0 && (
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={isUploading}
              className="rounded-[6px] px-3.5 py-1.5 text-[12px] font-medium transition-colors hover:opacity-80 disabled:opacity-40"
              style={{
                border: "1px solid rgba(212,168,67,0.25)",
                color: "#D4A843",
                background: "rgba(212,168,67,0.06)",
              }}
            >
              {isUploading ? "Uploading..." : "+ Add material"}
            </button>
          )}
        </div>

        {engagement.materials.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {engagement.materials.map((material) => (
              <MaterialChip key={material.id} material={material} />
            ))}
            {isAdmin && (
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={isUploading}
                className="inline-flex items-center gap-1.5 rounded-[6px] px-3 py-1.5 text-[12px] text-sig-high transition-colors hover:opacity-80 disabled:opacity-40"
                style={{
                  background: "rgba(212,168,67,0.06)",
                  border: "1px solid rgba(212,168,67,0.2)",
                }}
              >
                {isUploading ? "Uploading..." : "+ Add"}
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Team Request (compact bar) ── */}
      <TeamRequestSection engagementId={engagement.id} />

      {/* Edit dialog */}
      {isAdmin && editOpen && (
        <EditEngagementDialog
          engagement={engagement}
          open={editOpen}
          onOpenChange={setEditOpen}
        />
      )}
    </div>
  );
}
