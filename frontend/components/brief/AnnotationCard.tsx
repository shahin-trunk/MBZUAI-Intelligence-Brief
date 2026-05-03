"use client";

import { useState } from "react";
import type { Annotation } from "@/lib/types/brief";
import { Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface AnnotationCardProps {
  annotation: Annotation;
  onUpdate: (id: string, noteText: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

function relativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return "Yesterday";
  return `${diffDays}d ago`;
}

export default function AnnotationCard({
  annotation,
  onUpdate,
  onDelete,
}: AnnotationCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(annotation.note_text);
  const [isSaving, setIsSaving] = useState(false);

  async function handleSave() {
    if (!editText.trim() || editText.trim() === annotation.note_text) {
      setIsEditing(false);
      return;
    }
    setIsSaving(true);
    await onUpdate(annotation.id, editText.trim());
    setIsSaving(false);
    setIsEditing(false);
  }

  async function handleDelete() {
    await onDelete(annotation.id);
  }

  if (isEditing) {
    return (
      <div className="space-y-2 rounded-sm border border-border-accent bg-bg-tertiary p-3">
        <Textarea
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          className="min-h-[60px] bg-bg-primary border-border-primary text-text-primary text-[14px] resize-none"
          autoFocus
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving}
            className="h-7 px-3 text-[13px] bg-accent-primary hover:bg-accent-primary/80"
          >
            {isSaving ? "Saving..." : "Save"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setEditText(annotation.note_text);
              setIsEditing(false);
            }}
            className="h-7 px-3 text-[13px] text-text-muted"
          >
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="group rounded-sm p-3 hover:bg-bg-tertiary transition-colors duration-150">
      <p className="font-sans text-[14px] text-text-primary leading-relaxed">
        {annotation.note_text}
      </p>
      <div className="mt-1.5 flex items-center justify-between">
        <span className="font-mono text-[13px] text-text-muted">
          {relativeTime(annotation.updated_at || annotation.created_at)}
        </span>
        <div className={cn(
          "flex items-center gap-1 opacity-100 transition-opacity duration-150 sm:opacity-0 sm:group-hover:opacity-100"
        )}>
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="p-1 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            title="Edit"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="p-1 text-text-muted hover:text-accent-danger transition-colors cursor-pointer"
            title="Delete"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
