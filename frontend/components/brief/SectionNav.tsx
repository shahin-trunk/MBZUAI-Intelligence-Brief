"use client";

import { useState, useEffect } from "react";
import type { BriefSection } from "@/lib/types/brief";
import { getSectionShortName } from "@/lib/transforms/brief";
import { cn } from "@/lib/utils";

interface SectionNavProps {
  sections: BriefSection[];
}

/**
 * Generate a URL-friendly id from a section name, matching BriefSection's id generation.
 */
function sectionId(name: string): string {
  return `section-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

export default function SectionNav({ sections }: SectionNavProps) {
  const [activeSection, setActiveSection] = useState<string>(
    sections[0]?.name ?? ""
  );

  // Track active section via IntersectionObserver
  useEffect(() => {
    const ids = sections.map((s) => sectionId(s.name));
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter(Boolean) as HTMLElement[];

    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Find the first visible section
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const name = sections.find(
              (s) => sectionId(s.name) === entry.target.id
            )?.name;
            if (name) setActiveSection(name);
            break;
          }
        }
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 }
    );

    for (const el of elements) {
      observer.observe(el);
    }

    return () => observer.disconnect();
  }, [sections]);

  function scrollToSection(name: string) {
    const el = document.getElementById(sectionId(name));
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveSection(name);
    }
  }

  return (
    <nav className="space-y-1" aria-label="Brief sections">
      <p className="font-mono text-[12px] uppercase tracking-[0.15em] text-text-muted mb-3 px-3">
        Sections
      </p>
      {sections.map((section) => {
        const isActive = activeSection === section.name;
        const totalCount = section.items.length;
        return (
          <button
            key={section.name}
            type="button"
            onClick={() => scrollToSection(section.name)}
            className={cn(
              "flex w-full items-center justify-between gap-2 rounded-sm px-3 py-2 text-left transition-all duration-150",
              "text-sm font-sans cursor-pointer",
              isActive
                ? "border-l-2 border-l-accent-primary text-text-bright"
                : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary border-l-2 border-l-transparent"
            )}
          >
            <span className="truncate">
              {getSectionShortName(section.name)}
            </span>
            <span className="font-mono text-[12px] shrink-0 text-text-muted">
              {totalCount}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
