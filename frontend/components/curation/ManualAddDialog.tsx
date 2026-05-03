"use client";

import { useState } from "react";
import { SECTION_ORDER, type ExhibitData } from "@/lib/types/brief";
import type { ManualItem } from "@/lib/types/curation";
import { ExhibitUploader } from "./ExhibitUploader";
import { ExhibitRenderer } from "@/components/card-reader/ExhibitRenderer";

interface ManualAddDialogProps {
  pendingBriefId: string;
  onClose: () => void;
  onAdded: (item: ManualItem) => void | Promise<void>;
}

interface GeneratedItem {
  headline: string;
  primary_entity: string | null;
  key_bullets: string[];
  analysis: string;
}

export function ManualAddDialog({ pendingBriefId, onClose, onAdded }: ManualAddDialogProps) {
  const [section, setSection] = useState<string>(SECTION_ORDER[0]);
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState<GeneratedItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [exhibits, setExhibits] = useState<ExhibitData[]>([]);
  const [showExhibitUploader, setShowExhibitUploader] = useState(false);

  // Editable fields (populated after generation)
  const [headline, setHeadline] = useState("");
  const [primaryEntity, setPrimaryEntity] = useState("");
  const [keyBullets, setKeyBullets] = useState<string[]>(["", "", ""]);
  const [analysis, setAnalysis] = useState("");

  function updateBullet(index: number, value: string) {
    setKeyBullets((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  }

  function addBullet() {
    setKeyBullets((prev) => (prev.length >= 3 ? prev : [...prev, ""]));
  }

  function removeBullet(index: number) {
    setKeyBullets((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== index)));
  }

  async function handleGenerate() {
    if (!sourceText.trim()) return;
    setGenerating(true);
    setError("");
    try {
      const res = await fetch("/api/curation/generate-item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_url: sourceUrl.trim() || null,
          source_text: sourceText.trim(),
          section,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Generation failed");
        return;
      }
      const g = data.generated as GeneratedItem;
      setGenerated(g);
      setHeadline(g.headline);
      setPrimaryEntity(g.primary_entity ?? "");
      setKeyBullets(g.key_bullets?.length ? g.key_bullets : ["", "", ""]);
      setAnalysis(g.analysis ?? "");
    } catch {
      setError("Network error during generation");
    } finally {
      setGenerating(false);
    }
  }

  async function handleAdd() {
    const bullets = keyBullets.map((bullet) => bullet.trim()).filter(Boolean).slice(0, 3);
    if (!headline.trim() || bullets.length === 0 || !analysis.trim()) return;
    setSaving(true);
    try {
      let derivedSourceName = "Manual Entry";
      if (sourceUrl) {
        try {
          derivedSourceName = new URL(sourceUrl).hostname.replace("www.", "");
        } catch {
          derivedSourceName = sourceUrl;
        }
      }
      const res = await fetch("/api/curation/manual-item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pending_brief_id: pendingBriefId,
          section,
          headline: headline.trim(),
          primary_entity: primaryEntity.trim() || null,
          key_bullets: bullets,
          analysis: analysis.trim(),
          exhibits,
          source_name: derivedSourceName,
          source_url: sourceUrl.trim() || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.error || "Failed to add item");
        return;
      }
      await onAdded(data.item as ManualItem);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-2xl rounded-xl border border-border-primary bg-surface-secondary p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold mb-6">Add Item</h2>

        {/* Step 1: Source input */}
        {!generated && (
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider">Section</label>
              <select
                value={section}
                onChange={(e) => setSection(e.target.value)}
                className="mt-1.5 w-full rounded-lg bg-surface-primary border border-border-secondary px-3 py-2 text-sm text-text-primary"
              >
                {SECTION_ORDER.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider">Source URL</label>
              <input
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://..."
                type="url"
                className="mt-1.5 w-full rounded-lg bg-surface-primary border border-border-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/40"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider">
                Source Text <span className="text-sig-high">*</span>
              </label>
              <textarea
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                placeholder="Paste the article text or relevant excerpt here..."
                rows={8}
                required
                className="mt-1.5 w-full rounded-lg bg-surface-primary border border-border-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/40 resize-y"
              />
            </div>

            {/* Exhibit upload (available before and after generation) */}
            <div className="border-t border-border-secondary pt-3">
              <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
                Exhibits (optional)
              </p>
              {exhibits.map((ex, i) => (
                <div key={i} className="mb-2 relative">
                  <ExhibitRenderer exhibit={ex} />
                  <button
                    onClick={() => setExhibits(exhibits.filter((_, j) => j !== i))}
                    className="absolute top-2 right-2 text-red-400 hover:text-red-300 text-xs"
                  >
                    Remove
                  </button>
                </div>
              ))}
              {showExhibitUploader ? (
                <ExhibitUploader
                  itemId={`manual-${Date.now()}`}
                  onExhibitAdded={(ex) => {
                    setExhibits([...exhibits, ex]);
                    setShowExhibitUploader(false);
                  }}
                  onCancel={() => setShowExhibitUploader(false)}
                />
              ) : (
                <button
                  onClick={() => setShowExhibitUploader(true)}
                  className="text-xs text-accent-primary hover:underline"
                >
                  + Upload Exhibit Image
                </button>
              )}
            </div>

            {error && (
              <p className="text-xs text-sig-high">{error}</p>
            )}

            <div className="flex gap-3 pt-2">
              <button
                onClick={handleGenerate}
                disabled={generating || !sourceText.trim()}
                className="px-5 py-2.5 rounded-lg bg-accent-primary text-white text-sm font-medium hover:bg-accent-primary/90 disabled:opacity-50"
              >
                {generating ? "Generating..." : "Generate Brief Entry"}
              </button>
              <button
                onClick={onClose}
                className="px-5 py-2.5 rounded-lg bg-surface-primary text-text-muted text-sm hover:text-text-primary"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Review and edit generated draft */}
        {generated && (
          <div className="space-y-4">
            <p className="text-xs text-text-muted">
              Review and edit the generated brief entry, then add it to the brief.
            </p>

            <div>
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider">Headline</label>
              <input
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                className="mt-1.5 w-full rounded-lg bg-surface-primary border border-border-secondary px-3 py-2 text-sm text-text-primary"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider">Primary Entity</label>
              <input
                value={primaryEntity}
                onChange={(e) => setPrimaryEntity(e.target.value)}
                className="mt-1.5 w-full rounded-lg bg-surface-primary border border-border-secondary px-3 py-2 text-sm text-text-primary"
                placeholder="Optional entity name for logo matching"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider">Key Bullets</label>
              <div className="mt-1.5 space-y-2">
                {keyBullets.map((bullet, index) => (
                  <div key={`manual-bullet-${index}`} className="flex gap-2">
                    <input
                      value={bullet}
                      onChange={(e) => updateBullet(index, e.target.value)}
                      className="flex-1 rounded-lg bg-surface-primary border border-border-secondary px-3 py-2 text-sm text-text-primary"
                      placeholder="One factual bullet"
                    />
                    {keyBullets.length > 1 && (
                      <button
                        onClick={() => removeBullet(index)}
                        className="text-xs text-red-400 hover:text-red-300 px-2"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
                {keyBullets.length < 3 && (
                  <button
                    onClick={addBullet}
                    className="text-xs text-accent-primary hover:underline"
                  >
                    + Add Bullet
                  </button>
                )}
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider">Analysis</label>
              <textarea
                value={analysis}
                onChange={(e) => setAnalysis(e.target.value)}
                rows={5}
                className="mt-1.5 w-full rounded-lg bg-surface-primary border border-border-secondary px-3 py-2 text-sm text-text-primary resize-y"
              />
            </div>

            <div className="border-t border-border-secondary pt-3">
              <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
                Exhibits (optional)
              </p>
              {exhibits.map((ex, i) => (
                <div key={i} className="mb-2 relative">
                  <ExhibitRenderer exhibit={ex} />
                  <button
                    onClick={() => setExhibits(exhibits.filter((_, j) => j !== i))}
                    className="absolute top-2 right-2 text-red-400 hover:text-red-300 text-xs"
                  >
                    Remove
                  </button>
                </div>
              ))}
              {showExhibitUploader ? (
                <ExhibitUploader
                  itemId={`manual-${Date.now()}`}
                  onExhibitAdded={(ex) => {
                    setExhibits([...exhibits, ex]);
                    setShowExhibitUploader(false);
                  }}
                  onCancel={() => setShowExhibitUploader(false)}
                />
              ) : (
                <button
                  onClick={() => setShowExhibitUploader(true)}
                  className="text-xs text-accent-primary hover:underline"
                >
                  + Upload Exhibit Image
                </button>
              )}
            </div>

            {error && (
              <p className="text-xs text-sig-high">{error}</p>
            )}

            <div className="flex gap-3 pt-2">
              <button
                onClick={handleAdd}
                disabled={
                  saving ||
                  !headline.trim() ||
                  keyBullets.map((bullet) => bullet.trim()).filter(Boolean).length === 0 ||
                  !analysis.trim()
                }
                className="px-5 py-2.5 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-500 disabled:opacity-50"
              >
                {saving ? "Adding..." : "Add Item"}
              </button>
              <button
                onClick={() => { setGenerated(null); setError(""); }}
                className="px-5 py-2.5 rounded-lg bg-surface-primary text-text-muted text-sm hover:text-text-primary"
              >
                Back
              </button>
              <button
                onClick={onClose}
                className="px-5 py-2.5 rounded-lg text-text-muted text-sm hover:text-text-primary"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
