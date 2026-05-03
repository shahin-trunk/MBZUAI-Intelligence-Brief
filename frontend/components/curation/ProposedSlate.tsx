"use client";

import type { CurationItem } from "@/lib/types/curation";
import { CurationItemCard } from "./CurationItemCard";

interface ItemSlateProps {
  items: CurationItem[];
  onToggleSelect: (item: CurationItem) => Promise<void>;
  onEdit: (item: CurationItem, fields: Record<string, unknown>) => Promise<void>;
}

export function ItemSlate({
  items,
  onToggleSelect,
  onEdit,
}: ItemSlateProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border-secondary p-8 text-center text-text-muted text-sm">
        No candidate items yet.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <CurationItemCard
          key={`${item.kind}-${item.id}`}
          item={item}
          onToggleSelect={() => onToggleSelect(item)}
          onEdit={onEdit}
        />
      ))}
    </div>
  );
}
