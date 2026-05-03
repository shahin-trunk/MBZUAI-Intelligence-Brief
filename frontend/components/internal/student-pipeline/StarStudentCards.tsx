"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { StarStudent } from "@/lib/types/internal-intelligence";
import { StudentDossierModal } from "./StudentDossierModal";

interface StarStudentCardsProps {
  students: StarStudent[];
}

function StudentStatusBadge({ status }: { status: string }) {
  let style: string;
  if (status.startsWith("Accepted")) {
    style = "bg-accent-success/15 text-accent-success border-accent-success/30";
  } else if (status.startsWith("Offer extended")) {
    style = "bg-accent-primary/15 text-accent-primary border-accent-primary/30";
  } else if (status.startsWith("Awaiting")) {
    style = "bg-accent-warning/15 text-accent-warning border-accent-warning/30";
  } else {
    style = "bg-bg-tertiary text-text-muted border-border-primary";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        style
      )}
    >
      {status}
    </span>
  );
}

function ProgramBadge({ program }: { program: "UG" | "Graduate" }) {
  const style =
    program === "UG"
      ? "bg-accent-primary/15 text-accent-primary border-accent-primary/30"
      : "bg-sig-high/15 text-sig-high border-sig-high/30";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
        style
      )}
    >
      {program}
    </span>
  );
}

export function StarStudentCards({ students }: StarStudentCardsProps) {
  const [selectedStudent, setSelectedStudent] = useState<StarStudent | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function handleCardClick(student: StarStudent) {
    setSelectedStudent(student);
    setModalOpen(true);
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
        {students.map((student) => (
          <button
            key={student.id}
            type="button"
            onClick={() => handleCardClick(student)}
            className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
          >
            {/* Name */}
            <p className="font-serif text-base text-text-bright">
              {student.name}
            </p>

            {/* Program badge + Nationality */}
            <div className="mt-1.5 flex items-center gap-2">
              <ProgramBadge program={student.program} />
              <span className="font-mono text-[14px] text-text-muted">
                {student.nationality}
              </span>
            </div>

            {/* Track */}
            <p className="mt-1 font-mono text-[13px] text-text-secondary">
              {student.track}
            </p>

            {/* Previous school */}
            <p className="mt-1 font-mono text-[13px] text-text-muted">
              {student.previousSchool}
            </p>

            {/* Status + competing offers count */}
            <div className="mt-3 flex items-center justify-between gap-2">
              <StudentStatusBadge status={student.status} />
              <span className="font-mono text-[13px] text-text-muted shrink-0">
                {student.competingOffers.length} competing{" "}
                {student.competingOffers.length === 1 ? "offer" : "offers"}
              </span>
            </div>
          </button>
        ))}
      </div>

      <StudentDossierModal
        student={selectedStudent}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
