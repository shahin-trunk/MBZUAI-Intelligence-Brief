"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { SECTION_ORDER, type ExhibitData } from "@/lib/types/brief";
import type { CurationItem } from "@/lib/types/curation";
import { renderMarkdown } from "@/lib/rendering/markdown";
import { ExhibitUploader } from "./ExhibitUploader";
import { ExhibitRenderer } from "@/components/card-reader/ExhibitRenderer";

interface CurationItemCardProps {
  item: CurationItem;
  onToggleSelect: () => void;
  onEdit: (item: CurationItem, fields: Record<string, unknown>) => Promise<void>;
}

export function CurationItemCard({
  item,
  onToggleSelect,
  onEdit,
}: CurationItemCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showExhibitUploader, setShowExhibitUploader] = useState(false);
  const [editPrimaryEntity, setEditPrimaryEntity] = useState(item.primary_entity ?? "");
  const [editSection, setEditSection] = useState(item.section);

  // v2 fields with v1 fallback
  const initialBullets = item.key_bullets?.length
    ? item.key_bullets
    : item.main_bullet
      ? [item.main_bullet]
      : [""];
  const initialAnalysis = item.analysis
    ?? [item.context, item.implication].filter(Boolean).join(" ")
    ?? "";

  const [editHeadline, setEditHeadline] = useState(item.headline);
  const [editBullets, setEditBullets] = useState<string[]>(initialBullets);
  const [editAnalysis, setEditAnalysis] = useState(initialAnalysis);
  const [editExhibits, setEditExhibits] = useState<ExhibitData[]>(item.exhibits ?? []);

  function updateBullet(idx: number, val: string) {
    setEditBullets((prev) => { const next = [...prev]; next[idx] = val; return next; });
  }
  function addBullet() {
    if (editBullets.length < 5) setEditBullets((prev) => [...prev, ""]);
  }
  function removeBullet(idx: number) {
    if (editBullets.length > 1) setEditBullets((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSave() {
    setSaving(true);
    try {
      const bullets = editBullets.filter((b) => b.trim());
      await onEdit(item, {
        section: editSection,
        headline: editHeadline,
        primary_entity: editPrimaryEntity.trim() || null,
        key_bullets: bullets,
        analysis: editAnalysis,
        main_bullet: bullets.join(" "),
        context: editAnalysis,
        implication: "",
        exhibits: editExhibits,
      });
      setIsExpanded(false);
    } finally {
      setSaving(false);
    }
  }

  const displayBullets = item.key_bullets?.length
    ? item.key_bullets
    : item.main_bullet
      ? [item.main_bullet]
      : [];

    return (
      <div className={cn(
        "rounded-lg border p-4 transition-colors",
      item.selected ? "border-accent-primary/50 bg-accent-primary/5" : "border-border-primary bg-surface-secondary",
    )}>
      <div className="flex items-start gap-3">
        <button onClick={onToggleSelect}
          className={cn("mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors",
            item.selected ? "bg-accent-primary border-accent-primary text-white" : "border-border-secondary hover:border-accent-primary/50")}
          aria-label={item.selected ? "Deselect" : "Select"}>
          {item.selected && <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 6l3 3 5-5"/></svg>}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-text-muted">{item.source_name}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-primary/10 text-accent-primary">
              {item.section}
            </span>
            {item.kind === "manual" && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">
                Manual
              </span>
            )}
          </div>
          <h3 className="font-medium text-sm leading-snug cursor-pointer hover:text-accent-primary"
            onClick={() => setIsExpanded(!isExpanded)}>
            {item.headline}
          </h3>
          {!isExpanded && displayBullets.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {displayBullets.slice(0, 3).map((b, i) => (
                <li key={i} className="text-xs text-text-muted flex gap-1.5 items-start">
                  <span className="w-1 h-1 rounded-full bg-text-muted/40 shrink-0 mt-1.5" />
                  <span className="line-clamp-1">{renderMarkdown(b)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="mt-3 space-y-3 border-t border-border-secondary pt-3">
          <div>
            <label className="text-[10px] uppercase tracking-wider text-text-muted">Section</label>
            <select
              value={editSection}
              onChange={(e) => setEditSection(e.target.value)}
              className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary"
            >
              {SECTION_ORDER.map((section) => (
                <option key={section} value={section}>
                  {section}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-wider text-text-muted">Headline</label>
            <input value={editHeadline} onChange={(e) => setEditHeadline(e.target.value)}
              className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary" />
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-wider text-text-muted">Key Bullets</label>
            <div className="mt-1 space-y-1.5">
              {editBullets.map((bullet, i) => (
                <div key={i} className="flex gap-1.5">
                  <span className="text-xs text-text-muted mt-2 w-4 shrink-0 text-center">{i + 1}.</span>
                  <input value={bullet} onChange={(e) => updateBullet(i, e.target.value)}
                    placeholder="One factual statement..."
                    className="flex-1 rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary" />
                  {editBullets.length > 1 && (
                    <button onClick={() => removeBullet(i)} className="text-red-400/50 hover:text-red-400 text-xs px-1">✕</button>
                  )}
                </div>
              ))}
              {editBullets.length < 5 && (
                <button onClick={addBullet} className="text-[10px] text-accent-primary hover:underline ml-5">+ Add bullet</button>
              )}
            </div>
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-wider text-text-muted">Primary Entity</label>
            <input
              value={editPrimaryEntity}
              onChange={(e) => setEditPrimaryEntity(e.target.value)}
              placeholder="Optional logo entity..."
              className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary"
            />
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-wider text-text-muted">Analysis</label>
            <textarea value={editAnalysis} onChange={(e) => setEditAnalysis(e.target.value)}
              placeholder="Single fluid paragraph blending context and implications..."
              rows={4}
              className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary resize-y" />
          </div>

          {editExhibits.length > 0 && (
            <div className="space-y-2">
              {editExhibits.map((exhibit, index) => (
                <div key={`${item.id}-exhibit-${index}`} className="relative">
                  <ExhibitRenderer exhibit={exhibit} />
                  <button
                    onClick={() => setEditExhibits((prev) => prev.filter((_, idx) => idx !== index))}
                    className="absolute top-2 right-2 text-red-400 hover:text-red-300 text-xs"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}

          {showExhibitUploader ? (
            <ExhibitUploader itemId={item.id}
              onExhibitAdded={(exhibit) => {
                setEditExhibits((prev) => [...prev, exhibit]);
                setShowExhibitUploader(false);
              }}
              onCancel={() => setShowExhibitUploader(false)} />
          ) : (
            <button onClick={() => setShowExhibitUploader(true)}
              className="text-xs text-accent-primary hover:underline flex items-center gap-1">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M6 2v8M2 6h8"/></svg>
              Attach Exhibit
            </button>
          )}

          <div className="flex gap-2">
            <button onClick={handleSave} disabled={saving}
              className="text-xs px-3 py-1.5 rounded bg-accent-primary text-white hover:bg-accent-primary/90 disabled:opacity-50">
              {saving ? "Saving..." : "Save"}
            </button>
            <button onClick={() => setIsExpanded(false)}
              className="text-xs px-3 py-1.5 rounded bg-surface-primary text-text-muted hover:text-text-primary">Cancel</button>
          </div>

          {item.source_url && (
            <a href={item.source_url} target="_blank" rel="noopener noreferrer"
              className="text-[10px] text-accent-primary hover:underline">Source: {item.source_url}</a>
          )}
        </div>
      )}
    </div>
  );
}
