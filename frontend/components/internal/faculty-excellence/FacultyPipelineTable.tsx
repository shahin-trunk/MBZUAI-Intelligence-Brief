"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { FacultyProfile } from "@/lib/types/internal-intelligence";
import { FacultyDossierModal } from "./FacultyDossierModal";

interface FacultyPipelineTableProps {
  profiles: FacultyProfile[];
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

function ProfileCard({ profile, onClick }: { profile: FacultyProfile; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px] text-left transition-colors duration-150 hover:bg-bg-tertiary hover:border-border-accent cursor-pointer"
    >
      <p className="font-serif text-base text-text-bright">{profile.name}</p>
      <p className="mt-1 font-mono text-[14px] text-text-muted">
        {profile.currentInstitution} — {profile.rank}
      </p>
      <p className="mt-1 font-mono text-[13px] text-text-secondary">{profile.hiringDivision}</p>
      <div className="mt-3 flex items-center justify-between">
        <StatusBadge status={profile.status} statusDate={profile.statusDate} />
        <span className="font-mono text-[13px] text-text-muted">h-index: {profile.hIndex}</span>
      </div>
    </button>
  );
}

export function FacultyPipelineTable({ profiles }: FacultyPipelineTableProps) {
  const [selectedProfile, setSelectedProfile] = useState<FacultyProfile | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const signed = profiles.filter((p) => p.status === "Signed");
  const active = profiles.filter((p) => p.status !== "Signed");

  function handleCardClick(profile: FacultyProfile) {
    setSelectedProfile(profile);
    setModalOpen(true);
  }

  return (
    <>
      {/* Recently Signed */}
      {signed.length > 0 && (
        <div className="mb-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
            Recently Signed
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
            {signed.map((profile) => (
              <ProfileCard key={profile.id} profile={profile} onClick={() => handleCardClick(profile)} />
            ))}
          </div>
        </div>
      )}

      {/* Active Pipeline */}
      {active.length > 0 && (
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
            Active Pipeline
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
            {active.map((profile) => (
              <ProfileCard key={profile.id} profile={profile} onClick={() => handleCardClick(profile)} />
            ))}
          </div>
        </div>
      )}

      <FacultyDossierModal
        profile={selectedProfile}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
