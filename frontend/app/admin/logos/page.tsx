"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  LogoEditorDialog,
  type EntityLogo,
} from "@/components/admin/LogoEditorDialog";
import { LogoDeleteDialog } from "@/components/admin/LogoDeleteDialog";

interface LogoThumbProps {
  entityName: string;
  primarySrc: string;
  fallbackSrc: string;
  onError: () => void;
}

/**
 * Renders the primary logo URL and swaps to the fallback category SVG
 * if the primary fails to load. Calls onError once so the parent can
 * track "real logo loaded" vs "real logo broken → fallback shown".
 */
function LogoThumb({ entityName, primarySrc, fallbackSrc, onError }: LogoThumbProps) {
  const [broken, setBroken] = useState(false);
  useEffect(() => {
    setBroken(false);
  }, [primarySrc]);

  return (
    <img
      src={broken ? fallbackSrc : primarySrc}
      alt={entityName}
      className="w-16 h-16 object-contain rounded-lg"
      onError={() => {
        if (!broken) {
          setBroken(true);
          onError();
        }
      }}
    />
  );
}

/* ─── Fallback SVG (mirrors CardFace.tsx) ─────────────────────────── */

// Categories that have their own fallback-{cat}.svg in storage. "country"
// is deliberately omitted — every country entry has a real flag, and if
// one ever 404s we drop to the generic "other" glyph.
const VALID_CATEGORIES = [
  "government", "university", "company", "energy", "finance", "defense", "other",
];

function fallbackSvgUrl(category: string): string {
  const base = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const cat = VALID_CATEGORIES.includes(category) ? category : "other";
  return `${base}/storage/v1/object/public/entity-logos/fallback-${cat}.svg`;
}

function logoUrl(path: string): string {
  if (path.startsWith("http")) return path;
  const base = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  return `${base}/storage/v1/object/public/entity-logos/${path}`;
}

/* ─── Category badge colors ──────────────────────────────────────── */

const CATEGORY_COLORS: Record<string, string> = {
  government: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  country: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
  university: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  company: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  energy: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  finance: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  defense: "bg-red-500/10 text-red-400 border-red-500/20",
  org: "bg-teal-500/10 text-teal-400 border-teal-500/20",
  model: "bg-pink-500/10 text-pink-400 border-pink-500/20",
  other: "bg-bg-tertiary text-text-muted border-border-primary",
};

/* ─── Component ──────────────────────────────────────────────────────── */

export default function LogosPage() {
  const [entities, setEntities] = useState<EntityLogo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Names whose primary logo URL failed to load and fell back to category SVG.
  const [brokenNames, setBrokenNames] = useState<Set<string>>(new Set());
  // Editor modal: open only when `mode` is set.
  const [editorState, setEditorState] = useState<{
    open: boolean;
    mode: "create" | "edit";
    entity: EntityLogo | null;
    defaultCategory?: string;
  }>({ open: false, mode: "create", entity: null });
  const [deleteTarget, setDeleteTarget] = useState<EntityLogo | null>(null);
  const [view, setView] = useState<"all" | "countries" | "entities">("all");

  const fetchLogos = useCallback(async () => {
    setLoading(true);
    setError(null);
    setBrokenNames(new Set());
    try {
      const res = await fetch("/api/admin/logos");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setEntities(json.entities ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogos();
  }, [fetchLogos]);

  const markBroken = useCallback((entityName: string) => {
    setBrokenNames((prev) => {
      if (prev.has(entityName)) return prev;
      const next = new Set(prev);
      next.add(entityName);
      return next;
    });
  }, []);

  // Filter entities by the active view toggle.
  const filtered = entities.filter((e) =>
    view === "all" ? true
      : view === "countries" ? e.category === "country"
      : e.category !== "country",
  );

  // Summary stats based on the active view.
  const total = filtered.length;
  const claimedLogos = filtered.filter(
    (e) => e.logo_path && !e.logo_path.startsWith("fallback"),
  );
  const workingLogos = claimedLogos.filter((e) => !brokenNames.has(e.entity_name)).length;
  const brokenLogos = claimedLogos.filter((e) => brokenNames.has(e.entity_name)).length;
  const usingFallbacks = total - claimedLogos.length;

  const openCreate = useCallback(() => {
    // Pre-select "country" category when the user is in the Countries view.
    const defaultCategory = view === "countries" ? "country" : undefined;
    setEditorState({ open: true, mode: "create", entity: null, defaultCategory });
  }, [view]);

  const openEdit = useCallback((entity: EntityLogo) => {
    setEditorState({ open: true, mode: "edit", entity });
  }, []);

  const closeEditor = useCallback(() => {
    setEditorState((prev) => ({ ...prev, open: false }));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-serif text-[28px] text-text-bright">Entity Logos</h1>
        <Button onClick={openCreate} size="sm">
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          New entity
        </Button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-text-muted">Loading...</p>
        </div>
      )}

      {error && (
        <div className="rounded-sm border border-accent-danger/20 bg-accent-danger/5 p-3">
          <p className="font-mono text-sm text-accent-danger">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* View toggle */}
          <div className="flex items-center gap-3">
            <div className="flex gap-1 rounded-lg border border-border-primary bg-bg-primary p-1">
              {(["all", "countries", "entities"] as const).map((v) => {
                const label = v === "all" ? "All" : v === "countries" ? "Countries" : "Entities";
                const count = v === "all"
                  ? entities.length
                  : v === "countries"
                    ? entities.filter((e) => e.category === "country").length
                    : entities.filter((e) => e.category !== "country").length;
                return (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setView(v)}
                    className={cn(
                      "rounded-md px-3 py-1.5 font-mono text-[12px] transition-colors",
                      view === v
                        ? "bg-bg-tertiary text-text-bright"
                        : "text-text-muted hover:text-text-secondary",
                    )}
                  >
                    {label} ({count})
                  </button>
                );
              })}
            </div>
          </div>

          {/* Logo grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {filtered.map((entity) => {
              const hasRealLogo = entity.logo_path && !entity.logo_path.startsWith("fallback");
              const primarySrc = hasRealLogo
                ? logoUrl(entity.logo_path)
                : fallbackSvgUrl(entity.category);
              const fallbackSrc = fallbackSvgUrl(entity.category);
              const isBroken = brokenNames.has(entity.entity_name);

              return (
                <div
                  key={entity.entity_name}
                  role="button"
                  tabIndex={0}
                  onClick={() => openEdit(entity)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openEdit(entity);
                    }
                  }}
                  className={cn(
                    "relative rounded-lg border p-4 flex flex-col items-center text-center transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent-primary",
                    isBroken
                      ? "border-accent-danger/30 bg-accent-danger/5 hover:border-accent-danger/50"
                      : "border-border-primary bg-bg-secondary hover:border-border-primary/60",
                  )}
                >
                  {/* Delete affordance — stops propagation so clicking
                      the trash does not also open the editor. */}
                  <button
                    type="button"
                    aria-label={`Delete ${entity.entity_name}`}
                    className="absolute right-2 top-2 rounded-sm p-1 text-text-muted/70 transition-colors hover:bg-bg-tertiary hover:text-accent-danger focus:outline-none focus:ring-2 focus:ring-accent-danger"
                    onClick={(event) => {
                      event.stopPropagation();
                      setDeleteTarget(entity);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                  {/* Logo at card rendering size. Brand logos sit on a
                      white plate so dark monochrome marks stay visible;
                      country flags already have their own color palette
                      and look cleaner without a plate (just a subtle
                      rounded frame). */}
                  <div
                    className={cn(
                      "w-20 h-20 flex items-center justify-center mb-3 rounded-lg",
                      entity.category === "country"
                        ? "overflow-hidden ring-1 ring-border-primary/40"
                        : "bg-white/95 p-2",
                    )}
                  >
                    <LogoThumb
                      entityName={entity.entity_name}
                      primarySrc={primarySrc}
                      fallbackSrc={fallbackSrc}
                      onError={() => markBroken(entity.entity_name)}
                    />
                  </div>

                  {/* Entity name — bright text, not muted */}
                  <p className="font-mono text-[13px] font-semibold text-text-bright leading-tight mb-1.5">
                    {entity.entity_name}
                  </p>

                  {/* Category badge */}
                  <span
                    className={cn(
                      "rounded-sm border px-2 py-0.5 font-mono text-[10px] mb-2",
                      CATEGORY_COLORS[entity.category] ?? CATEGORY_COLORS.other,
                    )}
                  >
                    {entity.category}
                  </span>

                  {/* Aliases */}
                  {entity.aliases?.length > 0 && (
                    <div className="flex flex-wrap justify-center gap-1 mt-1">
                      {entity.aliases.map((alias) => (
                        <span
                          key={alias}
                          className="rounded-sm bg-bg-tertiary px-1.5 py-0.5 font-mono text-[10px] text-text-secondary"
                        >
                          {alias}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Logo status indicator */}
                  <p
                    className={cn(
                      "mt-2 font-mono text-[10px]",
                      isBroken
                        ? "text-accent-danger"
                        : hasRealLogo
                          ? "text-accent-primary"
                          : "text-text-secondary",
                    )}
                  >
                    {isBroken
                      ? `Broken: ${entity.logo_path}`
                      : hasRealLogo
                        ? "Custom logo"
                        : "Fallback"}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Summary */}
          <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <p className="font-mono text-[20px] text-text-bright">{total}</p>
                <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
                  Total Entities
                </p>
              </div>
              <div>
                <p className="font-mono text-[20px] text-accent-primary">{workingLogos}</p>
                <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
                  Working Logos
                </p>
              </div>
              <div>
                <p className="font-mono text-[20px] text-accent-danger">{brokenLogos}</p>
                <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
                  Broken (file missing)
                </p>
              </div>
              <div>
                <p className="font-mono text-[20px] text-text-muted">{usingFallbacks}</p>
                <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
                  No Custom Logo
                </p>
              </div>
            </div>
          </div>

          {entities.length === 0 && (
            <p className="text-center font-mono text-sm text-text-muted py-8">
              No entities in entity_logos table.
            </p>
          )}
        </>
      )}

      <LogoEditorDialog
        open={editorState.open}
        mode={editorState.mode}
        entity={editorState.entity}
        defaultCategory={editorState.defaultCategory}
        onClose={closeEditor}
        onSaved={fetchLogos}
      />
      <LogoDeleteDialog
        entity={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={fetchLogos}
      />
    </div>
  );
}
