"use client";

import { useState } from "react";
import type { Annotation } from "@/lib/types/brief";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

interface AnnotationListProps {
  annotations: Annotation[];
  onUpdate: (id: string, text: string) => void;
  onDelete: (id: string) => void;
}

export default function AnnotationList({ annotations, onUpdate, onDelete }: AnnotationListProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  if (annotations.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      {annotations.map((ann) => (
        <div key={ann.id} className="group rounded-[4px] border border-rule-light bg-bg-surface-2 px-3 py-2.5">
          {editingId === ann.id ? (
            // Edit mode
            <div>
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className="w-full resize-none rounded-[2px] border border-rule bg-bg-surface px-2 py-1.5 font-body text-[13px] text-text-primary focus:border-accent focus:outline-none"
                rows={2}
              />
              <div className="mt-1.5 flex gap-2">
                <button
                  onClick={() => { onUpdate(ann.id, editText); setEditingId(null); }}
                  className="font-ui text-[11px] font-semibold text-accent"
                >
                  Save
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="font-ui text-[11px] text-text-muted"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            // Display mode
            <div>
              <p className="font-body text-[13px] leading-[1.5] text-text-primary">
                {ann.note_text}
              </p>
              <div className="mt-1.5 flex items-center justify-between">
                <span className="font-mono text-[10px] text-text-muted">
                  {relativeTime(ann.created_at)}
                </span>
                <div className="flex gap-2 lg:opacity-0 lg:transition-opacity lg:group-hover:opacity-100">
                  <button
                    onClick={() => { setEditingId(ann.id); setEditText(ann.note_text); }}
                    className="font-ui text-[10px] text-text-muted hover:text-text-primary"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => onDelete(ann.id)}
                    className="font-ui text-[10px] text-text-muted hover:text-accent"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
