import type { BriefSection as BriefSectionType } from "@/lib/types/brief";
import BriefItemCard from "@/components/brief/BriefItemCard";

interface BriefSectionProps {
  section: BriefSectionType;
  showHeader?: boolean;
}

/**
 * Generate a URL-friendly id from a section name for scroll targeting.
 */
function sectionId(name: string): string {
  return `section-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

export default function BriefSection({ section, showHeader = true }: BriefSectionProps) {
  return (
    <section
      id={sectionId(section.name)}
      className="scroll-mt-28 sm:scroll-mt-24 lg:scroll-mt-20"
    >
      {/* Section header — inline horizontal rule treatment */}
      {showHeader && (
        <div className="flex items-center gap-3 mb-4 min-w-0">
          <div className="h-px w-4 bg-border-accent shrink-0" />
          <h2 className="font-sans text-[17px] font-semibold uppercase tracking-[0.08em] text-text-primary min-w-0">
            {section.name}
          </h2>
          <div className="h-px flex-1 bg-border-primary hidden sm:block" />
          <span className="font-mono text-[13px] text-text-muted bg-bg-tertiary rounded-sm px-1.5 py-0.5 shrink-0">
            {section.items.length}
          </span>
        </div>
      )}

      {/* Items */}
      <div className="space-y-3">
        {section.items.length > 0 ? (
          section.items.map((item) => (
            <BriefItemCard key={item.id} item={item} />
          ))
        ) : (
          <div className="rounded-sm border border-border-primary bg-bg-secondary px-4 py-3">
            <p className="font-sans text-sm text-text-secondary">
              No relevant news to report for this section today.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
