"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { FacultyProfile } from "@/lib/types/internal-intelligence";

interface FacultyDossierModalProps {
  profile: FacultyProfile | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function StatusBadge({ status, statusDate }: { status: FacultyProfile["status"]; statusDate?: string }) {
  const styles = {
    "Under negotiation": "bg-accent-warning/15 text-accent-warning border-accent-warning/30",
    "Offer extended": "bg-accent-primary/15 text-accent-primary border-accent-primary/30",
    Signed: "bg-accent-success/15 text-accent-success border-accent-success/30",
  };

  const label =
    status === "Signed" && statusDate
      ? `Signed ${new Date(statusDate + "-01").toLocaleDateString("en-US", { month: "short", year: "numeric" })}`
      : status;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[13px] font-medium",
        styles[status]
      )}
    >
      {label}
    </span>
  );
}

export function FacultyDossierModal({
  profile,
  open,
  onOpenChange,
}: FacultyDossierModalProps) {
  if (!profile) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="font-serif text-[28px] text-text-bright">
            {profile.name}
          </DialogTitle>
          <DialogDescription className="text-text-secondary text-sm">
            {profile.rank} — {profile.currentInstitution}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-3 mt-1">
          <span className="font-mono text-[13px] text-text-muted">
            {profile.hiringDivision}
          </span>
          <StatusBadge status={profile.status} statusDate={profile.statusDate} />
        </div>

        {/* Bio */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Bio
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary">
            {profile.bio}
          </p>
        </div>

        {/* Academic Background */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Academic Background
          </h3>
          <p className="font-sans text-sm text-text-primary">
            PhD — {profile.phdInstitution}{profile.phdAdvisor && ` (Advisor: ${profile.phdAdvisor})`}
          </p>
        </div>

        {/* Research Metrics */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Research Metrics
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-bg-tertiary rounded-sm border border-border-primary px-3 py-2">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
                h-index
              </p>
              <p className="font-mono text-lg font-bold text-text-bright">
                {profile.hIndex}
              </p>
            </div>
            <div className="bg-bg-tertiary rounded-sm border border-border-primary px-3 py-2">
              <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
                Citations
              </p>
              <p className="font-mono text-lg font-bold text-text-bright">
                {profile.citations.toLocaleString()}
              </p>
            </div>
          </div>
        </div>

        {/* Research Focus */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Research Focus
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {profile.researchFocus.map((focus) => (
              <span
                key={focus}
                className="bg-bg-tertiary rounded-sm px-2.5 py-1 font-mono text-[13px] text-text-secondary border border-border-primary"
              >
                {focus}
              </span>
            ))}
          </div>
        </div>

        {/* Top Publications */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Top Publications
          </h3>
          <ol className="list-decimal list-inside space-y-1.5">
            {profile.topPublications.map((pub) => {
              // Split on the last " — " to separate title from venue
              const dashIndex = pub.lastIndexOf(" — ");
              const title = dashIndex >= 0 ? pub.slice(0, dashIndex) : pub;
              const venue = dashIndex >= 0 ? pub.slice(dashIndex + 3) : "";
              return (
                <li key={pub} className="font-sans text-sm text-text-primary leading-relaxed">
                  {title}
                  {venue && (
                    <span className="text-text-secondary font-medium"> — {venue}</span>
                  )}
                </li>
              );
            })}
          </ol>
        </div>

        {/* Awards */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Awards & Accolades
          </h3>
          <ul className="list-disc list-inside space-y-1">
            {profile.awards.map((award) => (
              <li key={award} className="font-sans text-sm text-text-primary">
                {award}
              </li>
            ))}
          </ul>
        </div>

        {/* Fellowships */}
        <div className="mt-4">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-2">
            Fellowships & Memberships
          </h3>
          {profile.fellowships.length > 0 || profile.academyMemberships.length > 0 ? (
            <ul className="list-disc list-inside space-y-1">
              {[...profile.fellowships, ...profile.academyMemberships].map(
                (item) => (
                  <li key={item} className="font-sans text-sm text-text-primary">
                    {item}
                  </li>
                )
              )}
            </ul>
          ) : (
            <p className="font-sans text-sm text-text-muted italic">None</p>
          )}
        </div>

        {/* Hiring Notes */}
        <div className="mt-4 border-l-2 border-l-sig-high bg-sig-high/5 px-4 py-3 rounded-sm">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.1em] text-sig-high mb-2">
            Internal Hiring Notes
          </h3>
          <p className="font-sans text-sm leading-relaxed text-text-primary italic">
            {profile.hiringNotes}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
