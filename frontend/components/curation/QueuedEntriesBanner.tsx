"use client";

import { useCallback, useEffect, useState } from "react";

interface QueuedEntry {
  id: string;
  headline: string;
  summary: string;
  source_url: string | null;
  brief_section: string;
  notes: string | null;
  target_date: string;
  created_by: string;
  created_at: string;
}

interface QueuedEntriesBannerProps {
  briefDate: string;
  pendingBriefId: string;
  onImported: () => void;
}

export function QueuedEntriesBanner({
  briefDate,
  pendingBriefId,
  onImported,
}: QueuedEntriesBannerProps) {
  const [entries, setEntries] = useState<QueuedEntry[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchEntries = useCallback(async () => {
    try {
      const res = await fetch(
        `/api/curation/queued-entries?brief_date=${briefDate}`,
      );
      if (!res.ok) return;
      const data = await res.json();
      setEntries(data.entries ?? []);
    } catch {
      // Silently fail — banner just won't show
    }
  }, [briefDate]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  async function handleImport(entryId: string) {
    setImportingId(entryId);
    setError(null);
    try {
      const res = await fetch("/api/curation/import-entry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manual_entry_id: entryId,
          pending_brief_id: pendingBriefId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Import failed");
        return;
      }
      // Remove the imported entry from the local list
      setEntries((prev) => prev.filter((e) => e.id !== entryId));
      onImported();
    } catch {
      setError("Network error during import");
    } finally {
      setImportingId(null);
    }
  }

  if (entries.length === 0) return null;

  return (
    <div className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="text-sm font-medium text-amber-400">
          {entries.length} queued {entries.length === 1 ? "entry" : "entries"} from
          admin
        </span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className={`text-amber-400 transition-transform ${expanded ? "rotate-180" : ""}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          {error && (
            <p className="text-xs text-sig-high mb-2">{error}</p>
          )}
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="flex items-start gap-3 rounded-lg border border-border-secondary bg-surface-secondary p-3"
            >
              <div className="flex-1 min-w-0">
                {entry.headline && (
                  <p className="text-sm font-medium text-text-primary truncate">
                    {entry.headline}
                  </p>
                )}
                {entry.source_url && (
                  <p className="text-xs text-accent-primary truncate mt-0.5">
                    {entry.source_url}
                  </p>
                )}
                {entry.summary && (
                  <p className="text-xs text-text-muted mt-1 line-clamp-2">
                    {entry.summary}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-1.5">
                  {entry.brief_section && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-primary text-text-muted">
                      {entry.brief_section}
                    </span>
                  )}
                  <span className="text-[10px] text-text-muted">
                    by {entry.created_by}
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleImport(entry.id)}
                disabled={importingId !== null}
                className="shrink-0 px-3 py-1.5 rounded bg-amber-500/20 text-amber-400 text-xs font-medium hover:bg-amber-500/30 disabled:opacity-50"
              >
                {importingId === entry.id ? "Importing..." : "Import"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
