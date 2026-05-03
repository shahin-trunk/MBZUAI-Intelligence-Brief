"use client";

interface DeleteConfirmDialogProps {
  headline: string;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteConfirmDialog({
  headline,
  deleting,
  onConfirm,
  onCancel,
}: DeleteConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-surface-secondary border border-border-primary rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h3 className="text-sm font-medium text-text-primary mb-2">
          Remove from published brief?
        </h3>
        <p className="text-xs text-text-muted mb-4 line-clamp-2">
          &ldquo;{headline}&rdquo;
        </p>
        <p className="text-xs text-text-muted mb-4">
          This will remove the item from the live brief immediately. The change
          is logged and can be restored manually.
        </p>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            disabled={deleting}
            className="text-xs px-3 py-1.5 rounded bg-surface-primary text-text-muted hover:text-text-primary"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            className="text-xs px-3 py-1.5 rounded bg-red-600 text-white hover:bg-red-500 disabled:opacity-50"
          >
            {deleting ? "Removing..." : "Remove"}
          </button>
        </div>
      </div>
    </div>
  );
}
