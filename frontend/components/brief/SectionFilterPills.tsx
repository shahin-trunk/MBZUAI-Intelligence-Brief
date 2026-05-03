import type { Brief } from "@/lib/types/brief";
import { getSectionShortName } from "@/lib/transforms/brief";
import { cn } from "@/lib/utils";

interface SectionFilterPillsProps {
  sections: Brief["sections"];
  activeSection: string | null;
  onSelect: (section: string | null) => void;
}

export default function SectionFilterPills({
  sections,
  activeSection,
  onSelect,
}: SectionFilterPillsProps) {
  const totalItems = sections.reduce((sum, s) => sum + s.items.length, 0);

  return (
    <div className="inline-flex flex-wrap items-center gap-0 rounded-[8px] bg-bg-tertiary p-1">
      {/* "All" pill */}
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={cn(
          "px-4 py-2 text-[14px] font-medium rounded-[6px] transition-colors cursor-pointer whitespace-nowrap",
          activeSection === null
            ? "bg-bg-secondary text-text-bright border border-border-primary"
            : "bg-transparent text-text-muted border border-transparent hover:text-text-secondary"
        )}
      >
        All
        <span className="ml-1 opacity-60">{totalItems}</span>
      </button>

      {/* Section pills */}
      {sections.map((section) => {
        const isActive = activeSection === section.name;
        return (
          <button
            key={section.name}
            type="button"
            onClick={() => onSelect(section.name)}
            className={cn(
              "px-4 py-2 text-[14px] font-medium rounded-[6px] transition-colors cursor-pointer whitespace-nowrap",
              isActive
                ? "bg-bg-secondary text-text-bright border border-border-primary"
                : "bg-transparent text-text-muted border border-transparent hover:text-text-secondary"
            )}
          >
            {getSectionShortName(section.name)}
            <span className="ml-1 opacity-60">{section.items.length}</span>
          </button>
        );
      })}
    </div>
  );
}
