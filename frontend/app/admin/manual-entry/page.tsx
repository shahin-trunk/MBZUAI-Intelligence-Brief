"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import type { ExhibitData } from "@/lib/types/brief";
import { buildManualEntryNotes } from "@/lib/curation/manual-entry-metadata";
import { Trash2 } from "lucide-react";

/* ─── Types ──────────────────────────────────────────────────────────── */

type EntryStatus = "pending" | "ingested" | "expired" | "cancelled";

interface ManualEntry {
  id: string;
  created_by: string;
  headline: string | null;
  summary: string;
  source_url: string | null;
  brief_section: string | null;
  notes: string | null;
  target_date: string;
  status: EntryStatus;
  created_at: string;
  ingested_at: string | null;
}

/* ─── Constants ──────────────────────────────────────────────────────── */

const SECTIONS = [
  "UAE",
  "Regional Research & Academic Events",
  "International Politics & Policy",
  "International Business & Technology",
  "Model Releases & Technical Developments",
];

const STATUS_CONFIG: Record<EntryStatus, { label: string; classes: string }> = {
  pending: {
    label: "Pending",
    classes: "bg-accent-warning/10 text-accent-warning border-accent-warning/20",
  },
  ingested: {
    label: "Ingested",
    classes: "bg-accent-success/10 text-accent-success border-accent-success/20",
  },
  expired: {
    label: "Expired",
    classes: "bg-text-muted/10 text-text-muted border-text-muted/20",
  },
  cancelled: {
    label: "Cancelled",
    classes: "bg-text-muted/10 text-text-muted border-text-muted/20",
  },
};

const FILTER_TABS: Array<{ label: string; value: EntryStatus | "all" }> = [
  { label: "All", value: "all" },
  { label: "Pending", value: "pending" },
  { label: "Ingested", value: "ingested" },
  { label: "Expired", value: "expired" },
  { label: "Cancelled", value: "cancelled" },
];

/* ─── Helpers ────────────────────────────────────────────────────────── */

function getNextBusinessDay(): string {
  const now = new Date(
    new Date().toLocaleString("en-US", { timeZone: "Asia/Dubai" })
  );
  const d = new Date(now);
  d.setDate(d.getDate() + 1);
  // Skip weekends (Sat=6, Sun=0 — but MBZUAI uses Sat-Sun weekend)
  while (d.getDay() === 0 || d.getDay() === 6) {
    d.setDate(d.getDate() + 1);
  }
  return d.toISOString().split("T")[0];
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return (
      d.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Dubai",
      }) + " GST"
    );
  } catch {
    return iso;
  }
}

/* ─── Component ──────────────────────────────────────────────────────── */

export default function ManualEntryPage() {
  const [entries, setEntries] = useState<ManualEntry[]>([]);
  const [filter, setFilter] = useState<EntryStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [sourceUrl, setSourceUrl] = useState("");
  const [summary, setSummary] = useState("");
  const [section, setSection] = useState("");
  const [targetDate, setTargetDate] = useState(getNextBusinessDay);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [exhibitFile, setExhibitFile] = useState<File | null>(null);
  const [exhibitUrl, setExhibitUrl] = useState<string | null>(null);

  // Delete confirmation
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/manual-entries", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setEntries(json.entries ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const filtered =
    filter === "all"
      ? entries
      : entries.filter((e) => e.status === filter);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!sourceUrl.trim()) return;
    setSubmitting(true);
    setSuccessMsg(null);
    try {
      // Upload exhibit image if present
      let exhibitImageUrl: string | null = null;
      let extractedExhibit: ExhibitData | null = null;
      if (exhibitFile) {
        const formData = new FormData();
        formData.append("image", exhibitFile);
        formData.append("item_id", `manual-${Date.now()}`);
        const uploadRes = await fetch("/api/curation/extract-exhibit", {
          method: "POST",
          body: formData,
        });
        if (uploadRes.ok) {
          const uploadData = await uploadRes.json();
          exhibitImageUrl = uploadData.image_url;
          extractedExhibit = (uploadData.exhibit as ExhibitData | null) ?? null;
        }
      }

      const notes = buildManualEntryNotes({
        exhibit: extractedExhibit,
        imageUrl: exhibitImageUrl,
      });

      const res = await fetch("/api/admin/manual-entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_url: sourceUrl.trim(),
          summary: summary.trim(),
          brief_section: section || null,
          target_date: targetDate,
          notes,
        }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error || `HTTP ${res.status}`);
      }
      setSuccessMsg(`Entry queued for ${formatDate(targetDate)} brief`);
      setSourceUrl("");
      setSummary("");
      setTargetDate(getNextBusinessDay());
      setExhibitFile(null);
      setExhibitUrl(null);
      await fetchEntries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelEntry(id: string) {
    try {
      const res = await fetch(`/api/admin/manual-entries/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "cancelled" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchEntries();
    } catch (err) {
      console.error("Failed to cancel entry:", err);
    }
  }

  async function deleteEntry(id: string) {
    try {
      const res = await fetch(`/api/admin/manual-entries/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setDeleteTargetId(null);
      await fetchEntries();
    } catch (err) {
      console.error("Failed to delete entry:", err);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-[28px] text-text-bright">Manual Entry</h1>

      {/* ── Submission Form ────────────────────────────────────────── */}
      <form
        onSubmit={handleSubmit}
        className="rounded-sm border border-border-primary bg-bg-secondary p-5 space-y-4"
      >
        <div className="space-y-1">
          <label className="font-mono text-[12px] text-text-muted uppercase tracking-[0.1em]">
            Source URL *
          </label>
          <input
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            required
            placeholder="Paste the article URL"
            className="w-full rounded-sm border border-border-primary bg-bg-tertiary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
          />
        </div>

        <div className="space-y-1">
          <label className="font-mono text-[12px] text-text-muted uppercase tracking-[0.1em]">
            Article Text
          </label>
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Paste article body if URL is paywalled"
            rows={3}
            className="w-full rounded-sm border border-border-primary bg-bg-tertiary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary resize-none"
          />
        </div>

        {/* Exhibit image upload */}
        <div className="space-y-1">
          <label className="font-mono text-[12px] text-text-muted uppercase tracking-[0.1em]">
            Exhibit Image (optional)
          </label>
          {exhibitUrl ? (
            <div className="flex items-center gap-2">
              <img src={exhibitUrl} alt="Exhibit" className="h-16 rounded border border-border-primary" />
              <button
                type="button"
                onClick={() => { setExhibitUrl(null); setExhibitFile(null); }}
                className="text-xs text-red-400 hover:text-red-300"
              >
                Remove
              </button>
            </div>
          ) : (
            <input
              type="file"
              accept=".png,.jpg,.jpeg,.webp"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  setExhibitFile(file);
                  setExhibitUrl(URL.createObjectURL(file));
                }
              }}
              className="w-full rounded-sm border border-border-primary bg-bg-tertiary px-3 py-2 text-sm text-text-primary file:mr-3 file:border-0 file:bg-accent-primary/20 file:text-accent-primary file:text-xs file:px-2 file:py-1 file:rounded"
            />
          )}
          <p className="text-[11px] text-text-muted">
            Upload a screenshot of a benchmark table, chart, or data. It will be extracted into a structured exhibit during curation.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1">
            <label className="font-mono text-[12px] text-text-muted uppercase tracking-[0.1em]">
              Target Section
            </label>
            <select
              value={section}
              onChange={(e) => setSection(e.target.value)}
              className="w-full rounded-sm border border-border-primary bg-bg-tertiary px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-primary"
            >
              <option value="">Auto-assign</option>
              {SECTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="font-mono text-[12px] text-text-muted uppercase tracking-[0.1em]">
              Target Date *
            </label>
            <input
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              required
              className="w-full rounded-sm border border-border-primary bg-bg-tertiary px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button
            type="submit"
            disabled={submitting || !sourceUrl.trim()}
            className="rounded-sm bg-accent-primary px-4 py-2 font-mono text-[13px] text-white hover:bg-accent-primary/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Submitting..." : "Queue URL"}
          </button>
          {successMsg && (
            <span className="font-mono text-[13px] text-accent-success">
              {successMsg}
            </span>
          )}
        </div>
      </form>

      {/* ── Status Filter Tabs ─────────────────────────────────────── */}
      <div className="flex items-center gap-1 overflow-x-auto">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setFilter(tab.value)}
            className={cn(
              "px-3 py-1.5 rounded-sm font-mono text-[13px] transition-colors whitespace-nowrap",
              filter === tab.value
                ? "bg-accent-primary text-white"
                : "bg-bg-secondary text-text-muted hover:text-text-primary hover:bg-bg-tertiary border border-border-primary"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Loading / Error ────────────────────────────────────────── */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-text-muted">Loading...</p>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-accent-danger">Error: {error}</p>
        </div>
      )}

      {/* ── Entry Cards ──────────────────────────────────────────── */}
      {!loading && !error && (
        <div className="space-y-3">
          {filtered.map((entry) => (
            <EntryCard
              key={entry.id}
              entry={entry}
              onCancel={cancelEntry}
              onDelete={setDeleteTargetId}
            />
          ))}
          {filtered.length === 0 && (
            <p className="text-center font-mono text-sm text-text-muted py-8">
              No manual entries match the current filter.
            </p>
          )}
        </div>
      )}

      {/* ── Delete Modal ─────────────────────────────────────────── */}
      {deleteTargetId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="mx-4 w-full max-w-sm rounded-sm border border-border-primary bg-bg-secondary p-6">
            <h3 className="font-serif text-lg text-text-bright mb-3">
              Delete Entry
            </h3>
            <p className="text-sm text-text-secondary">
              Permanently delete this manual entry? This cannot be undone.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteTargetId(null)}
                className="rounded-sm border border-border-primary bg-bg-tertiary px-4 py-2 font-mono text-[13px] text-text-muted hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => deleteEntry(deleteTargetId)}
                className="rounded-sm bg-accent-danger px-4 py-2 font-mono text-[13px] text-white hover:bg-accent-danger/80 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Entry Card ─────────────────────────────────────────────────────── */

function EntryCard({
  entry,
  onCancel,
  onDelete,
}: {
  entry: ManualEntry;
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const statusConf = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.pending;

  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
      {/* Top row: badge + section + date */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span
          className={cn(
            "rounded-sm border px-2 py-0.5 font-mono text-[12px]",
            statusConf.classes
          )}
        >
          {statusConf.label}
        </span>
        {entry.brief_section && (
          <span className="rounded-sm border border-border-primary px-2 py-0.5 font-mono text-[12px] text-text-muted">
            {entry.brief_section}
          </span>
        )}
        <span className="font-mono text-[12px] text-text-muted">
          Target: {formatDate(entry.target_date)}
        </span>
      </div>

      {/* Title: headline or URL domain */}
      <h4 className="font-serif text-sm text-text-primary leading-snug mb-1">
        {entry.headline || (entry.source_url ? new URL(entry.source_url).hostname.replace("www.", "") : "Manual entry")}
      </h4>

      {/* Source URL */}
      {entry.source_url && (
        <a
          href={entry.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[12px] font-mono text-accent-primary hover:underline break-all"
        >
          {entry.source_url}
        </a>
      )}

      {/* Article text snippet */}
      {entry.summary && (
        <p className="mt-1 text-sm text-text-secondary line-clamp-2">
          {entry.summary}
        </p>
      )}

      {/* Meta */}
      <p className="mt-2 font-mono text-[12px] text-text-muted">
        By {entry.created_by} · {formatTimestamp(entry.created_at)}
        {entry.ingested_at && ` · Ingested ${formatTimestamp(entry.ingested_at)}`}
      </p>

      {/* Actions */}
      <div className="mt-3 flex flex-wrap gap-2">
        {entry.status === "pending" && (
          <button
            type="button"
            onClick={() => onCancel(entry.id)}
            className="rounded-sm border border-border-primary bg-bg-tertiary px-3 py-1.5 font-mono text-[12px] text-text-muted hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={() => onDelete(entry.id)}
          className="inline-flex items-center gap-1 rounded-sm border border-accent-danger/20 bg-accent-danger/5 px-3 py-1.5 font-mono text-[12px] text-accent-danger hover:bg-accent-danger/10 transition-colors"
        >
          <Trash2 className="h-3 w-3" />
          Delete
        </button>
      </div>
    </div>
  );
}
