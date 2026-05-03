"use client";

import { useCallback, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useToast } from "@/lib/contexts/ToastContext";
import type { EntityLogo } from "./LogoEditorDialog";

interface LogoDeleteDialogProps {
  entity: EntityLogo | null;
  onClose: () => void;
  onDeleted: () => void;
}

/**
 * Confirm-and-delete dialog. There is no shadcn AlertDialog component in
 * this codebase, so we reuse the regular Dialog shell and just give the
 * primary action a destructive variant.
 *
 * Deletes the entity_logos row only — the associated storage file is
 * intentionally left in place so re-creating the same entity later can
 * reuse it.
 */
export function LogoDeleteDialog({
  entity,
  onClose,
  onDeleted,
}: LogoDeleteDialogProps) {
  const { showToast } = useToast();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = entity !== null;

  const handleConfirm = useCallback(async () => {
    if (!entity) return;
    setDeleting(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/admin/logos/${encodeURIComponent(entity.entity_name)}`,
        { method: "DELETE" },
      );
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setError(body?.error ?? `HTTP ${res.status}`);
        setDeleting(false);
        return;
      }
      showToast(`Deleted ${entity.entity_name}`, "success");
      onDeleted();
      setDeleting(false);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setDeleting(false);
    }
  }, [entity, onDeleted, onClose, showToast]);

  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next && !deleting) onClose();
    },
    [deleting, onClose],
  );

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="border-border-primary bg-bg-secondary text-text-primary sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-serif text-[20px] text-text-bright">
            Delete {entity?.entity_name}?
          </DialogTitle>
          <DialogDescription className="font-mono text-[12px] text-text-muted">
            This removes the row from <span className="text-text-primary">entity_logos</span> and
            deletes the image file from storage.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-sm border border-accent-danger/20 bg-accent-danger/5 p-2 font-mono text-[12px] text-accent-danger">
            {error}
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={deleting}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={deleting}
          >
            {deleting ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
