"use client";

import type { Annotation } from "@/lib/types/brief";
import AnnotationInput from "./AnnotationInput";
import AnnotationList from "./AnnotationList";

interface AnnotationPanelProps {
  itemId: string;
  briefDate: string;
  annotations: Annotation[];
  onAdd: (itemId: string, briefDate: string, noteText: string) => void;
  onUpdate: (id: string, noteText: string) => void;
  onDelete: (id: string) => void;
}

export default function AnnotationPanel({
  itemId,
  briefDate,
  annotations,
  onAdd,
  onUpdate,
  onDelete,
}: AnnotationPanelProps) {
  return (
    <div className="mt-4 border-t border-dotted border-rule pt-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
        Notes {annotations.length > 0 && `(${annotations.length})`}
      </p>

      {annotations.length === 0 && (
        <p className="mt-2 font-body text-[13px] text-text-muted">
          No notes yet. Add one below.
        </p>
      )}

      <AnnotationList
        annotations={annotations}
        onUpdate={onUpdate}
        onDelete={onDelete}
      />

      <AnnotationInput
        onSubmit={(text) => onAdd(itemId, briefDate, text)}
      />
    </div>
  );
}
