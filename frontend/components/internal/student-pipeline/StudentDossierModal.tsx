"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { StarStudent } from "@/lib/types/internal-intelligence";

interface StudentDossierModalProps {
  student: StarStudent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
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

function OfferStatusColor({ status }: { status: string }) {
  if (status === "Accepted") return "text-accent-success";
  if (status === "Declined") return "text-text-muted";
  if (status.includes("Offer")) return "text-accent-primary";
  return "text-text-secondary";
}

export function StudentDossierModal({
  student,
  open,
  onOpenChange,
}: StudentDossierModalProps) {
  if (!student) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-[28px] text-text-bright">
            {student.name}
          </DialogTitle>
          <DialogDescription className="text-text-secondary text-sm">
            {student.track} — {student.nationality}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-3 mt-1">
          <ProgramBadge program={student.program} />
          <StudentStatusBadge status={student.status} />
        </div>

        {/* Academic Background */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Academic Background
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {student.previousSchool}
          </p>
          <p className="font-mono text-sm text-text-secondary mt-1">
            GPA: {student.gpa}
          </p>
        </div>

        {/* Achievements */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Achievements
          </h3>
          <ul className="list-disc list-inside space-y-1">
            {student.achievements.map((achievement) => (
              <li
                key={achievement}
                className="font-sans text-sm text-text-primary leading-relaxed"
              >
                {achievement}
              </li>
            ))}
          </ul>
        </div>

        {/* Competing Offers */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Competing Offers
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border-primary">
                  <th className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted py-1.5 pr-4">
                    Institution
                  </th>
                  <th className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted py-1.5">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {student.competingOffers.map((offer) => (
                  <tr
                    key={offer.institution}
                    className="border-b border-border-primary/50"
                  >
                    <td className="font-sans text-sm text-text-primary py-1.5 pr-4">
                      {offer.institution}
                    </td>
                    <td
                      className={cn(
                        "font-mono text-[14px] py-1.5",
                        OfferStatusColor({ status: offer.status })
                      )}
                    >
                      {offer.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Scholarship Status */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Scholarship Status
          </h3>
          <p className="font-sans text-sm text-text-primary">
            {student.scholarshipStatus}
          </p>
        </div>

        {/* Notes */}
        <div className="mt-4 border-l-2 border-l-sig-high bg-sig-high/5 px-4 py-3 rounded-sm">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-2">
            Internal Admissions Notes
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary italic">
            {student.notes}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
