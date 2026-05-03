"use client";

import { useState, useRef, useEffect } from "react";
import { useBriefInteraction } from "@/lib/contexts/BriefInteractionContext";
import { X, Bookmark, MessageSquare, Search as SearchIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import AnnotationCard from "@/components/brief/AnnotationCard";

/**
 * Annotation panel — right rail on desktop, bottom sheet on mobile.
 * Renders in both contexts by detecting viewport width.
 */
export default function AnnotationPanel({
  mode = "both",
}: {
  mode?: "desktop" | "mobile" | "both";
}) {
  return (
    <>
      {/* Desktop: inline right rail */}
      {mode !== "mobile" && <DesktopPanel />}

      {/* Mobile: bottom sheet */}
      {mode !== "desktop" && <MobilePanel />}
    </>
  );
}

function DesktopPanel() {
  const { annotationPanelOpen } = useBriefInteraction();

  if (!annotationPanelOpen) return null;

  return (
    <div className="hidden lg:block">
      <AnnotationPanelContent />
    </div>
  );
}

function MobilePanel() {
  const { annotationPanelOpen, setAnnotationPanelOpen, setSelectedItemId } =
    useBriefInteraction();

  if (!annotationPanelOpen) return null;

  return (
    <div className="fixed inset-0 z-40 lg:hidden">
      <button
        type="button"
        aria-label="Close notes panel"
        className="absolute inset-0 bg-black/35 backdrop-blur-[1px]"
        onClick={() => {
          setAnnotationPanelOpen(false);
          setSelectedItemId(null);
        }}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="absolute inset-x-0 bottom-0 max-h-[70vh] overflow-y-auto rounded-t-lg border-t border-border-accent bg-bg-secondary shadow-lg"
      >
        <div className="p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
          <AnnotationPanelContent />
        </div>
      </div>
    </div>
  );
}

/**
 * Relative timestamp: "just now", "2m ago", "1h ago", "yesterday", "3 Mar"
 */
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "yesterday";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function AnnotationPanelContent() {
  const {
    selectedItemId,
    setSelectedItemId,
    setAnnotationPanelOpen,
    annotations,
    flags,
    requests,
    getAnnotationsForItem,
    addAnnotation,
    updateAnnotation,
    deleteAnnotation,
    findItem,
  } = useBriefInteraction();

  const panelRef = useRef<HTMLDivElement>(null);
  const [newNote, setNewNote] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Scroll panel into view when an item is selected (fixes scroll position issue)
  useEffect(() => {
    if (selectedItemId && panelRef.current) {
      requestAnimationFrame(() => {
        panelRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      });
    }
  }, [selectedItemId]);

  useEffect(() => {
    setNewNote("");
    setIsSaving(false);
  }, [selectedItemId]);

  // Close handler
  function handleClose() {
    setAnnotationPanelOpen(false);
    setSelectedItemId(null);
  }

  async function handleSaveNote() {
    if (!selectedItemId || !newNote.trim()) return;
    setIsSaving(true);
    await addAnnotation(selectedItemId, newNote.trim());
    setNewNote("");
    setIsSaving(false);
  }

  // ─── No item selected: activity summary view ──────────────────────────────
  if (!selectedItemId) {
    const hasActivity = flags.length > 0 || annotations.length > 0 || requests.length > 0;

    return (
      <div ref={panelRef} className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <span className="font-mono text-[14px] uppercase tracking-[0.15em] text-text-bright">
            Activity
          </span>
          <button
            type="button"
            onClick={handleClose}
            className="p-1 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {!hasActivity && (
          <p className="text-[14px] text-text-muted italic">
            No activity yet. Expand items to flag, annotate, or request research.
          </p>
        )}

        {/* ── Flagged Items ── */}
        {flags.length > 0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-2 mb-2">
              <div className="h-px flex-1 bg-border-primary" />
              <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted flex items-center gap-1">
                <Bookmark className="h-3 w-3" /> Flagged Items
              </span>
              <div className="h-px flex-1 bg-border-primary" />
            </div>
            {flags.map((f) => {
              const item = findItem(f.item_id);
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setSelectedItemId(f.item_id)}
                  className="w-full text-left rounded-sm p-2 hover:bg-bg-tertiary transition-colors duration-150 cursor-pointer"
                >
                  <p className="font-serif text-[14px] text-text-secondary truncate">
                    &#x25B8; {item?.headline ?? f.item_id}
                  </p>
                  <p className="font-mono text-[12px] text-text-muted mt-0.5">
                    {item?.section ?? ""}{item?.section ? " \u00B7 " : ""}flagged {relativeTime(f.created_at)}
                  </p>
                </button>
              );
            })}
          </div>
        )}

        {/* ── Notes ── */}
        {annotations.length > 0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-2 mb-2">
              <div className="h-px flex-1 bg-border-primary" />
              <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted flex items-center gap-1">
                <MessageSquare className="h-3 w-3" /> Notes
              </span>
              <div className="h-px flex-1 bg-border-primary" />
            </div>
            {annotations.slice(0, 10).map((a) => {
              const item = findItem(a.item_id);
              return (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => setSelectedItemId(a.item_id)}
                  className="w-full text-left rounded-sm p-2 hover:bg-bg-tertiary transition-colors duration-150 cursor-pointer"
                >
                  <p className="font-serif text-[14px] text-text-secondary truncate">
                    &#x25B8; {item?.headline ?? a.item_id}
                  </p>
                  <p className="font-sans text-[13px] text-text-muted truncate mt-0.5 italic">
                    &ldquo;{a.note_text}&rdquo;
                  </p>
                  <p className="font-mono text-[12px] text-text-muted mt-0.5">
                    {item?.section ?? ""}{item?.section ? " \u00B7 " : ""}{relativeTime(a.created_at)}
                  </p>
                </button>
              );
            })}
          </div>
        )}

        {/* ── Research Requests ── */}
        {requests.length > 0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-2 mb-2">
              <div className="h-px flex-1 bg-border-primary" />
              <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted flex items-center gap-1">
                <SearchIcon className="h-3 w-3" /> Research Requests
              </span>
              <div className="h-px flex-1 bg-border-primary" />
            </div>
            {requests.map((r) => {
              const item = findItem(r.item_id);
              const statusLabel = r.status === "completed" ? "Completed" : r.status === "in_progress" ? "In progress" : "Pending";
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setSelectedItemId(r.item_id)}
                  className="w-full text-left rounded-sm p-2 hover:bg-bg-tertiary transition-colors duration-150 cursor-pointer"
                >
                  <p className="font-serif text-[14px] text-text-secondary truncate">
                    &#x25B8; {item?.headline ?? r.item_id}
                  </p>
                  <p className="font-mono text-[12px] text-text-muted mt-0.5">
                    {statusLabel} &middot; requested {relativeTime(r.created_at)}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // ─── Item selected: annotation editor ─────────────────────────────────────
  const selectedItem = findItem(selectedItemId);
  const itemAnnotations = getAnnotationsForItem(selectedItemId);

  return (
    <div ref={panelRef} className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-[14px] uppercase tracking-[0.15em] text-text-bright">
          Notes
        </span>
        <button
          type="button"
          onClick={handleClose}
          className="p-1 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Item context */}
      <p className="font-serif text-[14px] text-text-secondary leading-snug">
        Re: {selectedItem?.headline ?? "Selected item"}
      </p>

      {/* New note input */}
      <div className="space-y-2">
        <Textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          placeholder="Add a note..."
          className="min-h-[60px] bg-bg-tertiary border-border-primary text-text-primary text-[14px] placeholder:text-text-muted/60 resize-none"
        />
        <Button
          size="sm"
          onClick={handleSaveNote}
          disabled={!newNote.trim() || isSaving}
          className="h-7 px-3 text-[13px] bg-accent-primary hover:bg-accent-primary/80 font-mono"
        >
          {isSaving ? "Saving..." : "Save"}
        </Button>
      </div>

      {/* Existing notes */}
      {itemAnnotations.length > 0 && (
        <>
          <div className="border-t border-dotted border-border-primary" />
          <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
            Previous notes
          </p>
          <div className="space-y-1">
            {itemAnnotations.map((a) => (
              <AnnotationCard
                key={a.id}
                annotation={a}
                onUpdate={updateAnnotation}
                onDelete={deleteAnnotation}
              />
            ))}
          </div>
        </>
      )}

      {/* Back to summary link */}
      <button
        type="button"
        onClick={() => setSelectedItemId(null)}
        className="font-mono text-[13px] text-text-muted hover:text-accent-primary transition-colors cursor-pointer"
      >
        &larr; All notes
      </button>
    </div>
  );
}
