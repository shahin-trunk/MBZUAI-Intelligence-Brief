import { cn } from "@/lib/utils";

export type VisibilityMode = "media" | "engagement" | "outreach";

interface VisibilityTabsProps {
  mode: VisibilityMode;
  onModeChange: (mode: VisibilityMode) => void;
}

const TABS: { key: VisibilityMode; label: string }[] = [
  { key: "media", label: "Media & Brand" },
  { key: "engagement", label: "National Engagement & Outreach" },
  { key: "outreach", label: "The Academy" },
];

export function VisibilityTabs({ mode, onModeChange }: VisibilityTabsProps) {
  return (
    <div className="inline-flex border-b border-border-primary mb-6">
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
