"use client";

import { useState } from "react";
import { AcademyModal } from "./AcademyModal";
import type { AcademyProgram } from "@/lib/types/internal-intelligence";

interface AcademyProgramCardsProps {
  programs: AcademyProgram[];
}

function ProgramTypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-primary bg-bg-tertiary px-2 py-0.5 font-mono text-[12px] text-text-muted">
      {type}
    </span>
  );
}

export function AcademyProgramCards({ programs }: AcademyProgramCardsProps) {
  const [selected, setSelected] = useState<AcademyProgram | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleClick(program: AcademyProgram) {
    setSelected(program);
    setModalOpen(true);
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-[14px]">
        {programs.map((program) => (
          <button
            key={program.id}
            type="button"
            onClick={() => handleClick(program)}
            className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
          >
            {/* Program name */}
            <p className="font-serif text-sm text-text-bright leading-snug line-clamp-2">
              {program.programName}
            </p>

            {/* Client + Badge */}
            <div className="mt-2 flex items-center gap-2">
              <span className="font-mono text-[14px] text-text-secondary font-medium">
                {program.client}
              </span>
              <ProgramTypeBadge type={program.type} />
            </div>

            {/* Dates + Participants */}
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="font-mono text-[12px] text-text-muted">
                {program.dates}
              </span>
              <span className="font-mono text-[14px] text-text-bright font-bold">
                {program.participants} participants
              </span>
            </div>
          </button>
        ))}
      </div>

      <AcademyModal
        program={selected}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
