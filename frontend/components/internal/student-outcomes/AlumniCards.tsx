"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { AlumniHighlight } from "@/lib/types/internal-intelligence";
import { AlumniModal } from "./AlumniModal";

interface AlumniCardsProps {
  alumni: AlumniHighlight[];
}

export function AlumniCards({ alumni }: AlumniCardsProps) {
  const [selectedAlumni, setSelectedAlumni] = useState<AlumniHighlight | null>(
    null
  );
  const [modalOpen, setModalOpen] = useState(false);

  function handleCardClick(a: AlumniHighlight) {
    setSelectedAlumni(a);
    setModalOpen(true);
  }

  return (
    <>
      <p className="font-mono text-[14px] leading-[1.6] text-text-muted mb-4">
        {alumni.length} alumni highlight{alumni.length !== 1 ? "s" : ""}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
        {alumni.map((a) => {
          const isEmirati = a.nationality === "Emirati";
          return (
            <button
              key={a.id}
              type="button"
              onClick={() => handleCardClick(a)}
              className={cn(
                "bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer",
                isEmirati && "border-l-2 border-l-sig-high"
              )}
            >
              {/* Current role + organization — main hook */}
              <p className="font-serif text-base text-text-bright leading-snug">
                {a.currentRole}
              </p>
              <p className="font-sans text-sm text-text-secondary mt-0.5">
                {a.organization}
              </p>

              {/* Name */}
              <p className="mt-2 font-sans text-sm text-text-secondary">
                {a.name}
              </p>

              {/* Program + year */}
              <p className="mt-1 font-mono text-[12px] text-text-muted">
                {a.program}, Class of {a.graduationYear}
              </p>

              {/* Achievement headline */}
              <p className="mt-2 font-mono text-[14px] text-text-muted leading-[1.6]">
                {a.achievementHeadline}
              </p>

              {/* Nationality */}
              <p className="mt-2 font-mono text-[12px] text-text-muted">
                {a.nationality}
              </p>
            </button>
          );
        })}
      </div>

      <AlumniModal
        alumni={selectedAlumni}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
