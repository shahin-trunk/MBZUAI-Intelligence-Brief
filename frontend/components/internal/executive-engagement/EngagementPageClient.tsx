"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/AuthProvider";
import type {
  Engagement,
  GenerateDossierInput,
} from "@/lib/types/executive-engagement";
import { buildEngagementId } from "@/lib/utils/engagement-id";
import { CompactEngagementRow } from "./CompactEngagementRow";
import { NewEngagementDialog } from "./NewEngagementDialog";
import { EmptyState } from "@/components/internal/shared/EmptyState";

interface Props {
  engagements: Engagement[];
}

interface GenerationJob {
  visitorName: string;
  startedAt: number;
  error?: string;
}

/* ── Generating Banner ── */

function GeneratingBanner({
  visitorName,
  startedAt,
  error,
  onDismissError,
}: {
  visitorName: string;
  startedAt: number;
  error: string;
  onDismissError: () => void;
}) {
  const [elapsed, setElapsed] = useState(0);

  // Elapsed timer
  useEffect(() => {
    const interval = setInterval(
      () => setElapsed(Math.floor((Date.now() - startedAt) / 1000)),
      1000
    );
    return () => clearInterval(interval);
  }, [startedAt]);

  if (error) {
    return (
      <div
        className="rounded-[10px] px-5 py-4 flex items-center justify-between"
        style={{
          background: "rgba(239,68,68,0.06)",
          border: "1px solid rgba(239,68,68,0.2)",
        }}
      >
        <div>
          <p className="text-[13px] text-red-400 font-medium">
            Failed to generate dossier for {visitorName}
          </p>
          <p className="text-[12px] text-red-400/70 mt-0.5">{error}</p>
        </div>
        <button
          type="button"
          onClick={onDismissError}
          className="text-[11px] text-text-dim hover:text-text-secondary transition-colors shrink-0 ml-4"
        >
          Dismiss
        </button>
      </div>
    );
  }

  return (
    <div
      className="rounded-[10px] px-5 py-4 flex items-center gap-4"
      style={{
        background: "rgba(212,168,67,0.04)",
        border: "1px solid rgba(212,168,67,0.15)",
      }}
    >
      <svg className="animate-spin h-6 w-6 shrink-0" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="rgba(212,168,67,0.2)" strokeWidth="2.5" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="var(--sig-high)" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      <div className="flex-1 min-w-0">
        <p className="text-[13px] text-text-primary font-medium">Researching {visitorName}...</p>
        <p className="text-[12px] text-text-dim mt-0.5">Searching the web and building a dossier</p>
      </div>
      <span className="text-[12px] text-text-dim font-mono tabular-nums shrink-0">{elapsed}s</span>
    </div>
  );
}

/* ── Main Component ── */

export function EngagementPageClient({ engagements }: Props) {
  const router = useRouter();
  const { isAdmin } = useAuth();

  // Background generation state — supports multiple concurrent jobs
  const [jobs, setJobs] = useState<Map<string, GenerationJob>>(new Map());

  const handleStartGeneration = useCallback(
    async (input: GenerateDossierInput) => {
      const jobId = buildEngagementId(input);

      // Add this job (doesn't touch other running jobs)
      setJobs((prev) => new Map(prev).set(jobId, { visitorName: input.visitorName, startedAt: Date.now() }));

      try {
        const res = await fetch("/api/internal/generate-dossier", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to generate dossier");
        // Remove only this job on success
        setJobs((prev) => { const next = new Map(prev); next.delete(jobId); return next; });
        router.refresh();
      } catch (err) {
        // Mark this job as errored (keep visible so user can dismiss)
        setJobs((prev) => {
          const existing = prev.get(jobId);
          return new Map(prev).set(jobId, {
            visitorName: existing?.visitorName || input.visitorName,
            startedAt: existing?.startedAt || Date.now(),
            error: err instanceof Error ? err.message : "Generation failed",
          });
        });
      }
    },
    [router]
  );

  const isEmpty = engagements.length === 0;
  const [emptyDialogOpen, setEmptyDialogOpen] = useState(false);

  return (
    <div className="space-y-1">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-serif text-[26px] text-text-bright">
            Executive Engagement
          </h1>
          <p className="text-[14px] text-text-dim mt-1">
            Upcoming presidential meetings and engagement dossiers
          </p>
        </div>
        {isAdmin && <NewEngagementDialog onGenerate={handleStartGeneration} />}
      </div>

      {/* Background generation banners (one per concurrent job) */}
      {jobs.size > 0 && (
        <div className="mt-4 space-y-2">
          {[...jobs.entries()].map(([jobId, job]) => (
            <GeneratingBanner
              key={jobId}
              visitorName={job.visitorName}
              startedAt={job.startedAt}
              error={job.error || ""}
              onDismissError={() => setJobs((prev) => { const next = new Map(prev); next.delete(jobId); return next; })}
            />
          ))}
        </div>
      )}

      {isEmpty && jobs.size === 0 ? (
        <>
          <EmptyState
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" />
                <path d="M16 2v4" />
                <path d="M8 2v4" />
                <path d="M3 10h18" />
              </svg>
            }
            headline="No engagements scheduled"
            description="Upcoming presidential meetings and dossiers will appear here"
            action={
              isAdmin
                ? { label: "+ New Engagement", onClick: () => setEmptyDialogOpen(true) }
                : undefined
            }
          />
          {isAdmin && (
            <NewEngagementDialog
              externalOpen={emptyDialogOpen}
              onExternalOpenChange={setEmptyDialogOpen}
              onGenerate={handleStartGeneration}
            />
          )}
        </>
      ) : (
        <div className="mt-6 space-y-2">
          {engagements.map((engagement) => (
            <CompactEngagementRow
              key={engagement.id}
              engagement={engagement}
            />
          ))}
        </div>
      )}
    </div>
  );
}
