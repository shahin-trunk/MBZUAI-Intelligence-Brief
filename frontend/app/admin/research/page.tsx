"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { RotateCcw, Trash2, X } from "lucide-react";

/* ─── Types ──────────────────────────────────────────────────────────── */

type RequestStatus = "pending" | "in_progress" | "completed" | "dismissed";

interface ResearchRequest {
  id: string;
  user_id: string;
  item_id: string | null;
  brief_date: string;
  status: RequestStatus;
  request_note: string | null;
  response: string | null;
  assigned_to: string | null;
  completed_at: string | null;
  created_at: string;
  user_display_name: string | null;
  item_headline: string | null;
}

/* ─── Status config ──────────────────────────────────────────────────── */

const STATUS_CONFIG: Record<
  RequestStatus,
  { label: string; classes: string }
> = {
  pending: {
    label: "Pending",
    classes: "bg-accent-warning/10 text-accent-warning border-accent-warning/20",
  },
  in_progress: {
    label: "In Progress",
    classes: "bg-accent-primary/10 text-accent-primary border-accent-primary/20",
  },
  completed: {
    label: "Completed",
    classes: "bg-accent-success/10 text-accent-success border-accent-success/20",
  },
  dismissed: {
    label: "Dismissed",
    classes: "bg-text-muted/10 text-text-muted border-text-muted/20",
  },
};

const FILTER_TABS: Array<{ label: string; value: RequestStatus | "all" }> = [
  { label: "All", value: "all" },
  { label: "Pending", value: "pending" },
  { label: "In Progress", value: "in_progress" },
  { label: "Completed", value: "completed" },
  { label: "Dismissed", value: "dismissed" },
];

/* ─── Helpers ────────────────────────────────────────────────────────── */

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Dubai",
    }) + " GST";
  } catch {
    return iso;
  }
}

/* ─── Component ──────────────────────────────────────────────────────── */

export default function ResearchPage() {
  const [requests, setRequests] = useState<ResearchRequest[]>([]);
  const [filter, setFilter] = useState<RequestStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Response modal state
  const [modalRequestId, setModalRequestId] = useState<string | null>(null);
  const [responseText, setResponseText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/research", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setRequests(json.requests ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  // Filtered requests
  const filtered =
    filter === "all"
      ? requests
      : requests.filter((r) => r.status === filter);

  // Update status via PATCH
  async function updateStatus(id: string, status: RequestStatus) {
    try {
      const res = await fetch(`/api/admin/research/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // Refresh list
      await fetchRequests();
    } catch (err) {
      console.error("Failed to update status:", err);
    }
  }

  async function deleteRequest(id: string) {
    try {
      const res = await fetch(`/api/admin/research/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setDeleteTargetId(null);
      await fetchRequests();
    } catch (err) {
      console.error("Failed to delete request:", err);
    }
  }

  async function clearFilteredRequests() {
    if (filtered.length === 0) return;

    const label = filter === "all" ? "all research requests" : `${filter} research requests`;
    if (!window.confirm(`Permanently delete ${label}? This cannot be undone.`)) {
      return;
    }

    setClearing(true);
    try {
      const res = await fetch(
        `/api/admin/research?status=${encodeURIComponent(filter)}`,
        { method: "DELETE", cache: "no-store" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRequests((prev) =>
        filter === "all" ? [] : prev.filter((request) => request.status !== filter)
      );
      await fetchRequests();
    } catch (err) {
      console.error("Failed to clear requests:", err);
    } finally {
      setClearing(false);
    }
  }

  // Submit response
  async function submitResponse() {
    if (!modalRequestId || !responseText.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/admin/research/${modalRequestId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "completed",
          response: responseText.trim(),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setModalRequestId(null);
      setResponseText("");
      await fetchRequests();
    } catch (err) {
      console.error("Failed to submit response:", err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-serif text-[28px] text-text-bright">Research Requests</h1>
        <button
          type="button"
          onClick={clearFilteredRequests}
          disabled={clearing || filtered.length === 0}
          className="inline-flex items-center gap-2 rounded-sm border border-border-primary bg-bg-secondary px-3 py-2 font-mono text-[13px] text-text-muted transition-colors hover:text-text-primary hover:bg-bg-tertiary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Trash2 className="h-3.5 w-3.5" />
          {clearing ? "Clearing..." : `Clear ${filter === "all" ? "All" : "Filtered"}`}
        </button>
      </div>

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

      {/* ── Request Cards ──────────────────────────────────────────── */}
      {!loading && !error && (
        <div className="space-y-3">
          {filtered.map((req) => (
            <RequestCard
              key={req.id}
              request={req}
              onStatusChange={updateStatus}
              onDelete={setDeleteTargetId}
              onWriteResponse={(id) => {
                setModalRequestId(id);
                setResponseText("");
              }}
            />
          ))}
          {filtered.length === 0 && (
            <p className="text-center font-mono text-sm text-text-muted py-8">
              No research requests match the current filter.
            </p>
          )}
        </div>
      )}

      {/* ── Response Modal ─────────────────────────────────────────── */}
      {modalRequestId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="mx-4 w-full max-w-lg rounded-sm border border-border-primary bg-bg-secondary p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-serif text-lg text-text-bright">
                Write Response
              </h3>
              <button
                type="button"
                onClick={() => setModalRequestId(null)}
                className="text-text-muted hover:text-text-primary transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <textarea
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
              placeholder="Enter your research response..."
              rows={6}
              className="w-full rounded-sm border border-border-primary bg-bg-tertiary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary resize-none"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setModalRequestId(null)}
                className="rounded-sm border border-border-primary bg-bg-tertiary px-4 py-2 font-mono text-[13px] text-text-muted hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitResponse}
                disabled={submitting || !responseText.trim()}
                className="rounded-sm bg-accent-primary px-4 py-2 font-mono text-[13px] text-white hover:bg-accent-primary/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {submitting ? "Submitting..." : "Submit"}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteTargetId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="mx-4 w-full max-w-sm rounded-sm border border-border-primary bg-bg-secondary p-6">
            <h3 className="font-serif text-lg text-text-bright mb-3">
              Delete Request
            </h3>
            <p className="text-sm text-text-secondary">
              Permanently delete this research request? This cannot be undone.
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
                onClick={() => deleteRequest(deleteTargetId)}
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

/* ─── Request Card ───────────────────────────────────────────────────── */

function RequestCard({
  request,
  onStatusChange,
  onDelete,
  onWriteResponse,
}: {
  request: ResearchRequest;
  onStatusChange: (id: string, status: RequestStatus) => void;
  onDelete: (id: string) => void;
  onWriteResponse: (id: string) => void;
}) {
  const statusConf = STATUS_CONFIG[request.status] ?? STATUS_CONFIG.pending;

  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
      {/* Top row: badge + date */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className={cn(
            "rounded-sm border px-2 py-0.5 font-mono text-[12px]",
            statusConf.classes
          )}
        >
          {statusConf.label}
        </span>
        <span className="font-mono text-[12px] text-text-muted">
          {request.brief_date}
        </span>
      </div>

      {/* Item headline */}
      {request.item_headline && (
        <h4 className="font-serif text-sm text-text-primary leading-snug mb-1">
          {request.item_headline}
        </h4>
      )}

      {/* Requester */}
      <p className="font-mono text-[13px] text-text-muted">
        Requested by {request.user_display_name ?? "Unknown"}
        {" · "}
        {formatTimestamp(request.created_at)}
      </p>

      {/* Note */}
      {request.request_note && (
        <p className="mt-2 text-sm text-text-secondary italic">
          &ldquo;{request.request_note}&rdquo;
        </p>
      )}

      {/* Completed: show response */}
      {request.status === "completed" && request.response && (
        <div className="mt-3 rounded-sm border border-accent-success/20 bg-accent-success/5 p-3">
          <p className="font-mono text-[12px] text-accent-success uppercase tracking-[0.1em] mb-1">
            Response
          </p>
          <p className="text-sm text-text-primary">{request.response}</p>
          {request.completed_at && (
            <p className="mt-1 font-mono text-[12px] text-text-muted">
              Completed {formatTimestamp(request.completed_at)}
            </p>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-3 flex flex-wrap gap-2">
        {request.status !== "pending" && (
          <button
            type="button"
            onClick={() => onStatusChange(request.id, "pending")}
            className="inline-flex items-center gap-1 rounded-sm border border-border-primary bg-bg-tertiary px-3 py-1.5 font-mono text-[12px] text-text-muted hover:text-text-primary transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
            Reset to Pending
          </button>
        )}
        {request.status === "pending" && (
          <>
            <button
              type="button"
              onClick={() => onStatusChange(request.id, "in_progress")}
              className="rounded-sm bg-accent-primary px-3 py-1.5 font-mono text-[12px] text-white hover:bg-accent-primary/80 transition-colors"
            >
              Start Research
            </button>
            <button
              type="button"
              onClick={() => onStatusChange(request.id, "dismissed")}
              className="rounded-sm border border-border-primary bg-bg-tertiary px-3 py-1.5 font-mono text-[12px] text-text-muted hover:text-text-primary transition-colors"
            >
              Dismiss
            </button>
          </>
        )}
        {request.status === "in_progress" && (
          <>
            <button
              type="button"
              onClick={() => onWriteResponse(request.id)}
              className="rounded-sm bg-accent-primary px-3 py-1.5 font-mono text-[12px] text-white hover:bg-accent-primary/80 transition-colors"
            >
              Write Response
            </button>
            <button
              type="button"
              onClick={() => onStatusChange(request.id, "dismissed")}
              className="rounded-sm border border-border-primary bg-bg-tertiary px-3 py-1.5 font-mono text-[12px] text-text-muted hover:text-text-primary transition-colors"
            >
              Dismiss
            </button>
          </>
        )}
        <button
          type="button"
          onClick={() => onDelete(request.id)}
          className="inline-flex items-center gap-1 rounded-sm border border-accent-danger/20 bg-accent-danger/5 px-3 py-1.5 font-mono text-[12px] text-accent-danger hover:bg-accent-danger/10 transition-colors"
        >
          <Trash2 className="h-3 w-3" />
          Delete
        </button>
      </div>
    </div>
  );
}
