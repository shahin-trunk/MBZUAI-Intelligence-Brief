import { cn } from "@/lib/utils";
import type { MediaBrandAssessmentView } from "@/lib/types/internal-intelligence";

interface AssessmentViewToggleProps {
  view: MediaBrandAssessmentView;
  onViewChange: (view: MediaBrandAssessmentView) => void;
}

const TABS: { key: MediaBrandAssessmentView; label: string }[] = [
  { key: "marcomms", label: "MarComms" },
  { key: "ifm", label: "IFM" },
  { key: "rankings", label: "Rankings" },
];

export function AssessmentViewToggle({ view, onViewChange }: AssessmentViewToggleProps) {
  return (
    <div className="inline-flex border-b border-border-primary mb-6">
      {TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onViewChange(tab.key)}
          className={cn(
            "px-[18px] py-[10px] text-[13px] transition-colors duration-150",
            view === tab.key
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
