"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { BriefItem, ExhibitData } from "@/lib/types/brief";
import { SECTION_ORDER } from "@/lib/types/brief";
import { renderMarkdown } from "@/lib/rendering/markdown";
import { ExhibitUploader } from "./ExhibitUploader";
import { ExhibitRenderer } from "@/components/card-reader/ExhibitRenderer";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";

interface PublishedBriefEditorProps {
  briefDate: string;
  items: BriefItem[];
  onRefresh: () => void;
}

// ─── Individual item card with inline editing ─────────────────────────────────

function PublishedItemCard({
  item,
  briefDate,
  onRefresh,
}: {
  item: BriefItem;
  briefDate: string;
  onRefresh: () => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showExhibitUploader, setShowExhibitUploader] = useState(false);

  // Edit state
  const [editHeadline, setEditHeadline] = useState(item.headline);
  const initialBullets = item.key_bullets?.length
    ? item.key_bullets
    : item.main_bullet
      ? [item.main_bullet]
      : [""];
  const initialAnalysis =
    item.analysis ??
    [item.context, item.implication].filter(Boolean).join(" ") ??
    "";
  const [editBullets, setEditBullets] = useState<string[]>(initialBullets);
  const [editAnalysis, setEditAnalysis] = useState(initialAnalysis);
  const [editPrimaryEntity, setEditPrimaryEntity] = useState(
    item.primary_entity ?? ""
  );
  const [editExhibits, setEditExhibits] = useState<ExhibitData[]>(
    item.exhibits ?? []
  );

  function updateBullet(idx: number, val: string) {
    setEditBullets((prev) => {
      const next = [...prev];
      next[idx] = val;
      return next;
    });
  }
  function addBullet() {
    if (editBullets.length < 5) setEditBullets((prev) => [...prev, ""]);
  }
  function removeBullet(idx: number) {
    if (editBullets.length > 1)
      setEditBullets((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSave() {
    setSaving(true);
    try {
      const bullets = editBullets.filter((b) => b.trim());
      const res = await fetch(
        `/api/briefs/${briefDate}/items/${item.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            headline: editHeadline,
            primary_entity: editPrimaryEntity.trim() || null,
            key_bullets: bullets,
            analysis: editAnalysis,
            exhibits: editExhibits,
          }),
        }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        console.error("Edit failed:", data.error ?? res.statusText);
        return;
      }
      setIsExpanded(false);
      onRefresh();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      const res = await fetch(
        `/api/briefs/${briefDate}/items/${item.id}`,
        { method: "DELETE" }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        console.error("Delete failed:", data.error ?? res.statusText);
        return;
      }
      setDeleteTarget(false);
      onRefresh();
    } finally {
      setDeleting(false);
    }
  }

  const displayBullets = item.key_bullets?.length
    ? item.key_bullets
    : item.main_bullet
      ? [item.main_bullet]
      : [];

  return (
    <>
      <div className="rounded-lg border border-border-primary bg-surface-secondary p-4 transition-colors">
        <div className="flex items-start gap-3">
          {/* Rank badge */}
          <span className="mt-0.5 w-5 h-5 rounded bg-accent-primary/10 text-accent-primary text-[10px] font-medium flex items-center justify-center shrink-0">
            {item.rank}
          </span>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-text-muted">
                {item.source_name}
              </span>
              <span
                className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded",
                  item.significance === "high"
                    ? "bg-red-500/10 text-red-400"
                    : item.significance === "medium"
                      ? "bg-yellow-500/10 text-yellow-400"
                      : "bg-text-muted/10 text-text-muted"
                )}
              >
                {item.significance}
              </span>
            </div>
            <h3
              className="font-medium text-sm leading-snug cursor-pointer hover:text-accent-primary"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {item.headline}
            </h3>
            {!isExpanded && displayBullets.length > 0 && (
              <ul className="mt-1.5 space-y-0.5">
                {displayBullets.slice(0, 3).map((b, i) => (
                  <li
                    key={i}
                    className="text-xs text-text-muted flex gap-1.5 items-start"
                  >
                    <span className="w-1 h-1 rounded-full bg-text-muted/40 shrink-0 mt-1.5" />
                    <span className="line-clamp-1">{renderMarkdown(b)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Delete button */}
          <button
            onClick={() => setDeleteTarget(true)}
            className="text-red-400/40 hover:text-red-400 transition-colors shrink-0 mt-0.5"
            title="Remove from brief"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M3 4h10M6 4V3a1 1 0 011-1h2a1 1 0 011 1v1M5 4v9a1 1 0 001 1h4a1 1 0 001-1V4" />
            </svg>
          </button>
        </div>

        {/* Inline edit form */}
        {isExpanded && (
          <div className="mt-3 space-y-3 border-t border-border-secondary pt-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-text-muted">
                Headline
              </label>
              <input
                value={editHeadline}
                onChange={(e) => setEditHeadline(e.target.value)}
                className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary"
              />
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-wider text-text-muted">
                Key Bullets
              </label>
              <div className="mt-1 space-y-1.5">
                {editBullets.map((bullet, i) => (
                  <div key={i} className="flex gap-1.5">
                    <span className="text-xs text-text-muted mt-2 w-4 shrink-0 text-center">
                      {i + 1}.
                    </span>
                    <input
                      value={bullet}
                      onChange={(e) => updateBullet(i, e.target.value)}
                      placeholder="One factual statement..."
                      className="flex-1 rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary"
                    />
                    {editBullets.length > 1 && (
                      <button
                        onClick={() => removeBullet(i)}
                        className="text-red-400/50 hover:text-red-400 text-xs px-1"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
                {editBullets.length < 5 && (
                  <button
                    onClick={addBullet}
                    className="text-[10px] text-accent-primary hover:underline ml-5"
                  >
                    + Add bullet
                  </button>
                )}
              </div>
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-wider text-text-muted">
                Primary Entity
              </label>
              <input
                value={editPrimaryEntity}
                onChange={(e) => setEditPrimaryEntity(e.target.value)}
                placeholder="Optional logo entity..."
                className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary"
              />
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-wider text-text-muted">
                Analysis
              </label>
              <textarea
                value={editAnalysis}
                onChange={(e) => setEditAnalysis(e.target.value)}
                placeholder="Single fluid paragraph blending context and implications..."
                rows={4}
                className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary resize-y"
              />
            </div>

            {editExhibits.length > 0 && (
              <div className="space-y-2">
                {editExhibits.map((exhibit, index) => (
                  <div
                    key={`${item.id}-exhibit-${index}`}
                    className="relative"
                  >
                    <ExhibitRenderer exhibit={exhibit} />
                    <button
                      onClick={() =>
                        setEditExhibits((prev) =>
                          prev.filter((_, idx) => idx !== index)
                        )
                      }
                      className="absolute top-2 right-2 text-red-400 hover:text-red-300 text-xs"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            {showExhibitUploader ? (
              <ExhibitUploader
                itemId={item.id}
                onExhibitAdded={(exhibit) => {
                  setEditExhibits((prev) => [...prev, exhibit]);
                  setShowExhibitUploader(false);
                }}
                onCancel={() => setShowExhibitUploader(false)}
              />
            ) : (
              <button
                onClick={() => setShowExhibitUploader(true)}
                className="text-xs text-accent-primary hover:underline flex items-center gap-1"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 12 12"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path d="M6 2v8M2 6h8" />
                </svg>
                Attach Exhibit
              </button>
            )}

            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="text-xs px-3 py-1.5 rounded bg-accent-primary text-white hover:bg-accent-primary/90 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setIsExpanded(false)}
                className="text-xs px-3 py-1.5 rounded bg-surface-primary text-text-muted hover:text-text-primary"
              >
                Cancel
              </button>
            </div>

            {item.source_url && (
              <a
                href={item.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-accent-primary hover:underline"
              >
                Source: {item.source_url}
              </a>
            )}
          </div>
        )}
      </div>

      {deleteTarget && (
        <DeleteConfirmDialog
          headline={item.headline}
          deleting={deleting}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(false)}
        />
      )}
    </>
  );
}

// ─── Main published brief editor ──────────────────────────────────────────────

export function PublishedBriefEditor({
  briefDate,
  items,
  onRefresh,
}: PublishedBriefEditorProps) {
  // Group items by section in canonical order
  const grouped: { section: string; items: BriefItem[] }[] = [];
  const sectionMap = new Map<string, BriefItem[]>();

  for (const name of SECTION_ORDER) {
    sectionMap.set(name, []);
  }
  for (const item of items) {
    const list = sectionMap.get(item.section);
    if (list) {
      list.push(item);
    } else {
      sectionMap.set(item.section, [item]);
    }
  }
  for (const [section, sectionItems] of sectionMap) {
    if (sectionItems.length > 0) {
      grouped.push({ section, items: sectionItems });
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <h2 className="text-lg font-medium text-text-primary">
            Published Brief
          </h2>
          <span className="text-xs text-text-muted">{briefDate}</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/10 text-green-400">
            Live &middot; {items.length} items
          </span>
        </div>
        <a
          href={`/brief/${briefDate}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-accent-primary hover:underline flex items-center gap-1"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M5 2H3a1 1 0 00-1 1v6a1 1 0 001 1h6a1 1 0 001-1V7M7 2h3v3M10 2L5 7" />
          </svg>
          View brief
        </a>
      </div>

      <p className="text-xs text-text-muted -mt-3">
        Click a headline to edit. Changes are reflected in the live brief
        immediately.
      </p>

      {/* Sections */}
      {grouped.map(({ section, items: sectionItems }) => (
        <div key={section}>
          <h3 className="text-xs uppercase tracking-wider text-text-muted mb-2 font-medium">
            {section}
          </h3>
          <div className="space-y-2">
            {sectionItems.map((item) => (
              <PublishedItemCard
                key={item.id}
                item={item}
                briefDate={briefDate}
                onRefresh={onRefresh}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
