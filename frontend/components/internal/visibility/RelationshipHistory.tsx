"use client";

import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import type {
  InstitutionRelationship,
  DelegationCategory,
  RelationshipTier,
} from "@/lib/types/internal-intelligence";

interface RelationshipHistoryProps {
  relationships: InstitutionRelationship[];
}

type CategoryFilter = "all" | DelegationCategory;

const FILTER_OPTIONS: { key: CategoryFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "government", label: "Government" },
  { key: "academic", label: "Academic" },
  { key: "industry", label: "Industry" },
];

const CATEGORY_LABELS: Record<DelegationCategory, string> = {
  government: "Government",
  academic: "Academic",
  industry: "Industry",
};

const TIER_BORDER: Record<RelationshipTier, string> = {
  strategic: "border-l-sig-high",
  active: "border-l-accent-primary",
  dormant: "border-l-text-muted/40",
};

const TIER_LABELS: Record<RelationshipTier, string> = {
  strategic: "Strategic",
  active: "Active",
  dormant: "Dormant",
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function FilterRow({
  value,
  onChange,
}: {
  value: CategoryFilter;
  onChange: (v: CategoryFilter) => void;
}) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary px-4 py-3 mb-4">
      <div className="flex items-center gap-4 flex-wrap">
        <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted w-16 shrink-0">
          Category
        </span>
        {FILTER_OPTIONS.map((opt) => (
          <label
            key={opt.key}
            className="flex items-center gap-1.5 cursor-pointer group"
          >
            <input
              type="radio"
              name="relationship-category"
              checked={value === opt.key}
              onChange={() => onChange(opt.key)}
              className="h-3 w-3 accent-[#3B82F6] cursor-pointer"
            />
            <span
              className={cn(
                "font-mono text-[13px] transition-colors",
                value === opt.key
                  ? "text-text-primary"
                  : "text-text-muted group-hover:text-text-secondary"
              )}
            >
              {opt.label}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

function InstitutionCard({ rel }: { rel: InstitutionRelationship }) {
  return (
    <div
      className={cn(
        "bg-bg-secondary rounded-sm border border-border-primary border-l-2 px-7 py-[22px]",
        TIER_BORDER[rel.tier]
      )}
    >
      {/* Institution name */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <p className="font-serif text-sm text-text-bright leading-snug">
          {rel.institution}
        </p>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
            {CATEGORY_LABELS[rel.category]}
          </span>
          <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
            {TIER_LABELS[rel.tier]}
          </span>
        </div>
      </div>

      {/* One-liner */}
      <p className="font-sans text-[14px] text-text-secondary leading-relaxed line-clamp-2 mt-1">
        {rel.oneLiner}
      </p>

      {/* Stats row */}
      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <span className="font-mono text-[12px] text-text-muted">
          {rel.totalVisits} visit{rel.totalVisits !== 1 ? "s" : ""}
        </span>
        <span className="font-mono text-[12px] text-text-muted">·</span>
        <span className="font-mono text-[12px] text-text-muted">
          Last: {formatDate(rel.lastVisitDate)}
        </span>
        <span className="font-mono text-[12px] text-text-muted">·</span>
        <span className="font-mono text-[12px] text-text-muted">
          MOU: {rel.mouStatus}
        </span>
      </div>

      {/* Key contacts */}
      <div className="mt-2 space-y-0.5">
        <p className="font-mono text-[12px] text-text-muted">
          MBZUAI: {rel.keyContactMBZUAI}
        </p>
        <p className="font-mono text-[12px] text-text-muted">
          Partner: {rel.keyContactPartner}
        </p>
      </div>
    </div>
  );
}

export function RelationshipHistory({ relationships }: RelationshipHistoryProps) {
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");

  const filtered = useMemo(() => {
    if (categoryFilter === "all") return relationships;
    return relationships.filter((r) => r.category === categoryFilter);
  }, [relationships, categoryFilter]);

  return (
    <div>
      <FilterRow value={categoryFilter} onChange={setCategoryFilter} />

      <p className="font-mono text-[13px] text-text-muted mb-3">
        {filtered.length} institution{filtered.length !== 1 ? "s" : ""}
        {categoryFilter !== "all" ? ` (${FILTER_OPTIONS.find((o) => o.key === categoryFilter)?.label})` : ""}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
        {filtered.map((rel) => (
          <InstitutionCard key={rel.id} rel={rel} />
        ))}
      </div>
    </div>
  );
}
