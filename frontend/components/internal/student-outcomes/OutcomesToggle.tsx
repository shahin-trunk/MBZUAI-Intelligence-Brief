"use client";

import { cn } from "@/lib/utils";

interface OutcomesToggleProps {
  mode: "current" | "historical";
  onModeChange: (mode: "current" | "historical") => void;
}

const TABS: { key: "current" | "historical"; label: string }[] = [
  { key: "current", label: "Class of 2025" },
  { key: "historical", label: "Historical Data" },
];

export function OutcomesToggle({ mode, onModeChange }: OutcomesToggleProps) {
  return (
    <div className="inline-flex border-b border-border-primary mb-4">
      {TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onModeChange(tab.key)}
          className={cn(
            "px-[18px] py-[10px] text-[13px] transition-colors duration-150",
            mode === tab.key
              ? "text-text-bright font-semibold border-b-2 border-b-sig-high"
              : "text-text-dim hover:text-text-secondary"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
