"use client";

import { useState, useCallback } from "react";
import type { EngagementFollowup } from "@/lib/types/executive-engagement";

interface Props {
  engagementId: string;
  initialFollowups: EngagementFollowup[];
}

export function FollowUpSection({ engagementId, initialFollowups }: Props) {
  const [followups, setFollowups] =
    useState<EngagementFollowup[]>(initialFollowups);
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [latestAnswer, setLatestAnswer] = useState<{
    answer: string;
    detail: string | null;
  } | null>(null);
  const [error, setError] = useState("");

  const handleSubmit = useCallback(async () => {
    const trimmed = query.trim();
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
      setLatestAnswer({
        answer: followup.answer,
        detail: followup.detail,
      });
      setFollowups((prev) => [followup, ...prev]);
      setQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setIsSearching(false);
    }
  }, [query, isSearching, engagementId]);

  return (
    <div className="px-6 py-[18px] border-b border-border-primary">
      <h4
        className="text-[11px] uppercase font-semibold text-text-secondary mb-1"
        style={{ letterSpacing: "0.06em" }}
      >
        Ask a Follow-Up
      </h4>
      <p className="text-[12px] text-text-dim mb-3">
        Ask anything about this person or their organization...
      </p>

      {/* Search input */}
      <div
        className="flex items-center gap-2 rounded-[8px] px-3.5 py-2.5 transition-colors"
        style={{
          background: "var(--surface-primary)",
          border: `1px solid ${query ? "rgba(212,168,67,0.4)" : "var(--border-primary)"}`,
        }}
      >
        {/* Magnifying glass */}
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
            if (e.key === "Enter") handleSubmit();
          }}
          placeholder="e.g. What has World Labs published recently?"
          disabled={isSearching}
          className="flex-1 bg-transparent text-[13px] text-text-primary placeholder:text-text-dim outline-none disabled:opacity-50"
        />

        <button
          type="button"
          onClick={handleSubmit}
          disabled={isSearching || !query.trim()}
          className="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] transition-colors disabled:opacity-40 flex items-center gap-1.5"
          style={{
            border: `1px solid ${isSearching ? "var(--sig-high)" : "var(--text-dim)"}`,
            color: isSearching ? "var(--sig-high)" : "var(--text-dim)",
          }}
        >
          {isSearching && (
            <>
              <span
                style={{
                  width: 10,
                  height: 10,
                  border: "1.5px solid rgba(212,168,67,0.3)",
                  borderTopColor: "var(--sig-high)",
                  borderRadius: "50%",
                  display: "inline-block",
                  animation: "followup-spin 0.8s linear infinite",
                }}
              />
              <style>{`@keyframes followup-spin { to { transform: rotate(360deg); } }`}</style>
            </>
          )}
          {isSearching ? "Searching..." : "Search"}
        </button>
      </div>

      {/* Searching indicator */}
      {isSearching && (
        <p
          className="mt-2 text-[12px] font-medium"
          style={{ color: "var(--sig-high)", animation: "skeleton-pulse 1.5s ease-in-out infinite" }}
        >
          Thinking — searching the web and analyzing...
        </p>
      )}

      {/* Error */}
      {error && (
        <p className="mt-2 text-[12px] text-red-400">{error}</p>
      )}

      {/* Answer card */}
      {latestAnswer && (
        <div
          className="mt-3 rounded-[8px] px-4 py-3.5"
          style={{
            background: "rgba(212,168,67,0.03)",
            border: "1px solid rgba(212,168,67,0.12)",
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: "var(--sig-high)" }}
              />
              <span
                className="text-[11px] font-semibold text-sig-high"
                style={{ letterSpacing: "0.06em" }}
              >
                ANSWER
              </span>
            </div>
            <button
              type="button"
              onClick={() => setLatestAnswer(null)}
              className="text-[11px] text-text-dim hover:text-text-secondary transition-colors"
            >
              Dismiss
            </button>
          </div>
          <p className="text-[14px] text-text-bright leading-[1.6]">
            {latestAnswer.answer}
          </p>
          {latestAnswer.detail && (
            <p className="text-[14px] text-text-secondary leading-[1.6] mt-2">
              {latestAnswer.detail}
            </p>
          )}
        </div>
      )}

      {/* Previous followups */}
      {followups.length > 0 && !latestAnswer && (
        <div className="mt-3 space-y-2">
          {followups.slice(0, 3).map((f) => (
            <div
              key={f.id}
              className="rounded-[6px] px-3 py-2"
              style={{ background: "rgba(148,163,184,0.04)" }}
            >
              <p className="text-[12px] text-text-dim mb-1">
                {f.question}
              </p>
              <p className="text-[14px] text-text-secondary leading-[1.6]">
                {f.answer}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
