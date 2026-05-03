"use client";

import { useMemo, useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/utils";
import {
  sortSelectedItemsForOrdering,
} from "@/lib/curation/items";
import type { CurationItem, CurationItemRef } from "@/lib/types/curation";

const SECTION_LABELS: Record<string, string> = {
  UAE: "UAE",
  "Regional Research & Academic Events": "Regional",
  "International Politics & Policy": "Politics",
  "International Business & Technology": "Business",
  "Model Releases & Technical Developments": "Models",
};

const SECTION_COLORS: Record<string, string> = {
  UAE: "bg-amber-500/15 text-amber-400",
  "Regional Research & Academic Events": "bg-green-500/15 text-green-400",
  "International Politics & Policy": "bg-blue-500/15 text-blue-400",
  "International Business & Technology": "bg-purple-500/15 text-purple-400",
  "Model Releases & Technical Developments": "bg-cyan-500/15 text-cyan-400",
};

interface OrderItem {
  id: string;
  kind: CurationItem["kind"];
  section: string;
  headline: string;
  sourceName: string;
}

interface SortableRowProps {
  item: OrderItem;
  index: number;
}

function SortableRow({ item, index }: SortableRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: item.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border-primary bg-surface-secondary hover:border-accent-primary/30 transition-colors"
    >
      <button
        {...listeners}
        className="cursor-grab text-text-muted hover:text-text-primary shrink-0"
        aria-label="Drag to reorder"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <circle cx="5" cy="4" r="1.5" />
          <circle cx="11" cy="4" r="1.5" />
          <circle cx="5" cy="8" r="1.5" />
          <circle cx="11" cy="8" r="1.5" />
          <circle cx="5" cy="12" r="1.5" />
          <circle cx="11" cy="12" r="1.5" />
        </svg>
      </button>

      <span className="text-xs font-mono tabular-nums text-text-muted w-6 text-right shrink-0">
        {index + 1}
      </span>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary truncate">
          {item.headline}
        </p>
        <p className="text-[10px] text-text-muted">{item.sourceName}</p>
      </div>

      <span
        className={cn(
          "text-[10px] px-2 py-0.5 rounded-full shrink-0 font-medium",
          SECTION_COLORS[item.section] ?? "bg-text-muted/10 text-text-muted",
        )}
      >
        {SECTION_LABELS[item.section] ?? item.section}
      </span>

      {item.kind === "manual" && (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400 shrink-0">
          Manual
        </span>
      )}
    </div>
  );
}

interface OrderingScreenProps {
  items: CurationItem[];
  approving: boolean;
  onApprove: () => Promise<void>;
  onReorder: (orderedItems: CurationItemRef[]) => Promise<void>;
  onBack: () => void;
}

export function OrderingScreen({
  items,
  approving,
  onApprove,
  onReorder,
  onBack,
}: OrderingScreenProps) {
  // Initialize from persisted curation order, falling back to alphabetical.
  const initialOrder = useMemo(() => {
    return sortSelectedItemsForOrdering(items).map((item) => ({
      id: item.id,
      kind: item.kind,
      section: item.section,
      headline: item.headline,
      sourceName: item.source_name ?? "Unknown",
    }));
  }, [items]);

  const [orderedItems, setOrderedItems] = useState<OrderItem[]>(initialOrder);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIdx = orderedItems.findIndex((i) => i.id === active.id);
    const newIdx = orderedItems.findIndex((i) => i.id === over.id);
    if (oldIdx === -1 || newIdx === -1) return;

    const reordered = [...orderedItems];
    const [moved] = reordered.splice(oldIdx, 1);
    reordered.splice(newIdx, 0, moved);
    setOrderedItems(reordered);
    void onReorder(reordered.map((item) => ({ id: item.id, kind: item.kind })));
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h2 className="text-lg font-semibold">Review Order</h2>
        <p className="text-sm text-text-muted mt-1">
          Drag items to set the reading order. This is the sequence the reader will see.
        </p>
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={orderedItems.map((i) => i.id)} strategy={verticalListSortingStrategy}>
          <div className="space-y-1.5">
            {orderedItems.map((item, index) => (
              <SortableRow key={`${item.kind}-${item.id}`} item={item} index={index} />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {/* Bottom bar */}
      <div className="sticky bottom-0 z-40 bg-surface-primary border-t border-border-secondary mt-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="px-4 py-2 rounded border border-border-secondary text-sm text-text-muted hover:text-text-primary"
          >
            Back to Selection
          </button>
          <span className="text-xs tabular-nums text-text-muted">
            {orderedItems.length} items
          </span>
        </div>
        <button
          onClick={onApprove}
          disabled={approving}
          className="px-6 py-2 rounded bg-green-600 text-white text-sm font-medium hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {approving ? "Publishing..." : "Approve & Publish"}
        </button>
      </div>
    </div>
  );
}
