"use client";

import { cn } from "@/lib/utils";

type ProgramFilter = "all" | "msc" | "phd";
type NationalityFilter = "all" | "uae" | "international";

interface OutcomesFiltersProps {
  programFilter: ProgramFilter;
  nationalityFilter: NationalityFilter;
  onProgramFilterChange: (filter: ProgramFilter) => void;
  onNationalityFilterChange: (filter: NationalityFilter) => void;
}

const PROGRAM_OPTIONS: { key: ProgramFilter; label: string }[] = [
  { key: "all", label: "All Programs" },
  { key: "msc", label: "MSc only" },
  { key: "phd", label: "PhD only" },
];

const NATIONALITY_OPTIONS: { key: NationalityFilter; label: string }[] = [
  { key: "all", label: "All Nationalities" },
  { key: "uae", label: "UAE Nationals only" },
  { key: "international", label: "International only" },
];

function FilterRow<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-4 flex-wrap">
      <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted w-16 shrink-0">
        {label}
      </span>
      {options.map((opt) => (
        <label
          key={opt.key}
          className="flex items-center gap-1.5 cursor-pointer group"
        >
          <input
            type="radio"
            name={label}
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
  );
}

export function OutcomesFilters({
  programFilter,
  nationalityFilter,
  onProgramFilterChange,
  onNationalityFilterChange,
}: OutcomesFiltersProps) {
  return (
    <div className="bg-bg-tertiary rounded-sm border border-border-primary px-4 py-3 space-y-2 mb-4">
      <FilterRow
        label="Program"
        options={PROGRAM_OPTIONS}
        value={programFilter}
        onChange={onProgramFilterChange}
      />
      <FilterRow
        label="Origin"
        options={NATIONALITY_OPTIONS}
        value={nationalityFilter}
        onChange={onNationalityFilterChange}
      />
    </div>
  );
}
