"use client";

import { cn } from "@/lib/utils";

interface FilterOption {
  key: string;
  label: string;
  count?: number;
}

interface FilterPillsProps {
  options: FilterOption[];
  activeKey: string;
  onChange: (key: string) => void;
  className?: string;
}

export function FilterPills({
  options,
  activeKey,
  onChange,
  className,
}: FilterPillsProps) {
  return (
    <div className={cn("flex gap-2 overflow-x-auto scrollbar-none sm:flex-wrap sm:overflow-visible", className)}>
      {options.map((opt) => (
        <button
          key={opt.key}
          type="button"
          onClick={() => onChange(opt.key)}
          className={cn("intel-pill", activeKey === opt.key && "active")}
        >
          {opt.label}
          {opt.count != null && (
            <span className="text-[11px] opacity-60">{opt.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}
