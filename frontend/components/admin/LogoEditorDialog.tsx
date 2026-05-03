"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Upload } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ENTITY_LOGO_CATEGORIES,
  type EntityLogoCategory,
} from "@/lib/constants/entity-logo-categories";
import { useToast } from "@/lib/contexts/ToastContext";
import { cn } from "@/lib/utils";

export interface EntityLogo {
  entity_name: string;
  logo_path: string;
  category: string;
  aliases: string[];
  created_at?: string;
  updated_at?: string;
}

interface LogoEditorDialogProps {
  open: boolean;
  mode: "create" | "edit";
  entity: EntityLogo | null;
  /** When creating, pre-select this category (e.g. "country" when the
   *  user clicked "+ New entity" from the Countries view). */
  defaultCategory?: string;
  onClose: () => void;
  onSaved: () => void;
}

function storedLogoUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const base = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  return `${base}/storage/v1/object/public/entity-logos/${path}`;
}

/**
 * Unified create/edit dialog for entity_logos rows.
 *
 * Create mode: POST /api/admin/logos (multipart). All fields editable.
 * Edit mode: PATCH /api/admin/logos/[entityName] (multipart). The entity
 *   name is read-only — renames are done via delete + re-create.
 *
 * The file input is optional in both modes: a create without a file
 * yields a row whose logo_path is empty (the card reader will fall back
 * to the category SVG), and an edit without a file leaves the existing
 * logo in place.
 */
export function LogoEditorDialog({
  open,
  mode,
  entity,
  defaultCategory,
  onClose,
  onSaved,
}: LogoEditorDialogProps) {
  const { showToast } = useToast();

  const initialCategory: EntityLogoCategory = useMemo(() => {
    // In edit mode, use the entity's category. In create mode, honour
    // the defaultCategory prop (e.g. "country" when adding from the
    // Countries view), falling back to "company".
    const cat = entity?.category ?? defaultCategory ?? "company";
    return (ENTITY_LOGO_CATEGORIES as readonly string[]).includes(cat)
      ? (cat as EntityLogoCategory)
      : "company";
  }, [entity, defaultCategory]);

  const [entityName, setEntityName] = useState(entity?.entity_name ?? "");
  const [category, setCategory] =
    useState<EntityLogoCategory>(initialCategory);
  const [aliasesText, setAliasesText] = useState(
    entity?.aliases?.join(", ") ?? "",
  );
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset form state whenever the dialog opens with a new entity. We key
  // off `open` so closing and re-opening reuses the same prop snapshot
  // until the parent updates it — avoids a flash of stale data.
  useEffect(() => {
    if (!open) return;
    setEntityName(entity?.entity_name ?? "");
    setCategory(initialCategory);
    setAliasesText(entity?.aliases?.join(", ") ?? "");
    setFile(null);
    setPreviewUrl(null);
    setSaving(false);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [open, entity, initialCategory]);

  // Revoke any object URLs we created for previews when they change or
  // when the dialog unmounts. Browsers leak these otherwise.
  useEffect(() => {
    return () => {
      if (previewUrl && previewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleFileSelected = useCallback(
    (next: File | null) => {
      setFile(next);
      if (previewUrl && previewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(previewUrl);
      }
      setPreviewUrl(next ? URL.createObjectURL(next) : null);
    },
    [previewUrl],
  );

  const currentLogoUrl = useMemo(() => {
    if (previewUrl) return previewUrl;
    if (mode === "edit" && entity?.logo_path) {
      return storedLogoUrl(entity.logo_path);
    }
    return null;
  }, [previewUrl, mode, entity]);

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setSaving(true);
      setError(null);

      try {
        const payload = new FormData();

        if (mode === "create") {
          const trimmedName = entityName.trim();
          if (!trimmedName) {
            setError("Entity name is required");
            setSaving(false);
            return;
          }
          payload.append("entity_name", trimmedName);
          payload.append("category", category);
          payload.append("aliases", aliasesText);
          if (file) payload.append("file", file);

          const res = await fetch("/api/admin/logos", {
            method: "POST",
            body: payload,
          });
          const body = await res.json().catch(() => null);
          if (!res.ok) {
            setError(body?.error ?? `HTTP ${res.status}`);
            setSaving(false);
            return;
          }
          showToast(`Added ${trimmedName}`, "success");
          onSaved();
          onClose();
          return;
        }

        // Edit mode — only send fields that changed.
        if (!entity) {
          setError("Edit target is missing");
          setSaving(false);
          return;
        }

        const nextAliases = aliasesText;
        const prevAliases = entity.aliases?.join(", ") ?? "";

        if (category !== entity.category) payload.append("category", category);
        if (nextAliases !== prevAliases) payload.append("aliases", nextAliases);
        if (file) payload.append("file", file);

        if (Array.from(payload.keys()).length === 0) {
          setError("Nothing to save");
          setSaving(false);
          return;
        }

        const res = await fetch(
          `/api/admin/logos/${encodeURIComponent(entity.entity_name)}`,
          { method: "PATCH", body: payload },
        );
        const body = await res.json().catch(() => null);
        if (!res.ok) {
          setError(body?.error ?? `HTTP ${res.status}`);
          setSaving(false);
          return;
        }
        showToast(`Updated ${entity.entity_name}`, "success");
        onSaved();
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unexpected error");
        setSaving(false);
      }
    },
    [mode, entity, entityName, category, aliasesText, file, onSaved, onClose, showToast],
  );

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="border-border-primary bg-bg-secondary text-text-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-[20px] text-text-bright">
            {mode === "create" ? "New Entity" : `Edit ${entity?.entity_name ?? "entity"}`}
          </DialogTitle>
          <DialogDescription className="font-mono text-[12px] text-text-muted">
            {mode === "create"
              ? "Create a new entity_logos row. Logo file is optional — the card reader falls back to the category glyph if omitted."
              : "Update category, aliases, or replace the logo image. Entity name is immutable — delete and recreate to rename."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div className="space-y-1.5">
            <label className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
              Entity name
            </label>
            <Input
              value={entityName}
              onChange={(e) => setEntityName(e.target.value)}
              disabled={mode === "edit" || saving}
              placeholder="e.g. NVIDIA"
              className="bg-bg-primary text-text-bright"
            />
          </div>

          {/* Category */}
          <div className="space-y-1.5">
            <label className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
              Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as EntityLogoCategory)}
              disabled={saving}
              className="h-9 w-full rounded-md border border-border-primary bg-bg-primary px-3 text-sm text-text-bright focus:outline-none focus:ring-2 focus:ring-accent-primary"
            >
              {ENTITY_LOGO_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Aliases */}
          <div className="space-y-1.5">
            <label className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
              Aliases <span className="text-text-muted/70">(comma-separated)</span>
            </label>
            <Input
              value={aliasesText}
              onChange={(e) => setAliasesText(e.target.value)}
              disabled={saving}
              placeholder="e.g. NVDA, Nvidia Corporation"
              className="bg-bg-primary text-text-bright"
            />
          </div>

          {/* Logo file */}
          <div className="space-y-1.5">
            <label className="font-mono text-[11px] uppercase tracking-[0.15em] text-text-muted">
              Logo image <span className="text-text-muted/70">(optional, max 2 MB)</span>
            </label>
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  "flex h-20 w-20 items-center justify-center rounded-lg",
                  category === "country"
                    ? "overflow-hidden ring-1 ring-border-primary/40"
                    : "bg-white/95 p-2",
                )}
              >
                {currentLogoUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={currentLogoUrl}
                    alt="Logo preview"
                    className="h-16 w-16 rounded-lg object-contain"
                  />
                ) : (
                  <span className="font-mono text-[10px] text-text-muted/70">
                    No image
                  </span>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif"
                  className="hidden"
                  onChange={(e) => handleFileSelected(e.target.files?.[0] ?? null)}
                  disabled={saving}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={saving}
                >
                  <Upload className="mr-1.5 h-3.5 w-3.5" />
                  {file ? "Change file" : "Choose image"}
                </Button>
                {file && (
                  <p className="font-mono text-[11px] text-text-muted">
                    {file.name} ({(file.size / 1024).toFixed(1)} KB)
                  </p>
                )}
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-sm border border-accent-danger/20 bg-accent-danger/5 p-2 font-mono text-[12px] text-accent-danger">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : mode === "create" ? "Create" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
