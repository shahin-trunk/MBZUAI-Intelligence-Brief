import { cn } from "@/lib/utils";

export type ResearchTab =
  | "publications"
  | "ip-patents"
  | "external-funding"
  | "partnership-ecosystem";

interface ResearchModeToggleProps {
  mode: ResearchTab;
  onModeChange: (mode: ResearchTab) => void;
}

const TABS: { key: ResearchTab; label: string }[] = [
  { key: "publications", label: "Publications" },
  { key: "ip-patents", label: "IP & Patents" },
  { key: "external-funding", label: "External Funding" },
  { key: "partnership-ecosystem", label: "Partnership Ecosystem" },
];

export function ResearchModeToggle({ mode, onModeChange }: ResearchModeToggleProps) {
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
