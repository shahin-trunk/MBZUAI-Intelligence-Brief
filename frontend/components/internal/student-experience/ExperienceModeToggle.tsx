import { cn } from "@/lib/utils";

interface ExperienceModeToggleProps {
  mode: "graduate" | "undergraduate";
  onModeChange: (mode: "graduate" | "undergraduate") => void;
}

const TABS: { key: "graduate" | "undergraduate"; label: string }[] = [
  { key: "graduate", label: "Graduate" },
  { key: "undergraduate", label: "Undergraduate" },
];

export function ExperienceModeToggle({ mode, onModeChange }: ExperienceModeToggleProps) {
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
