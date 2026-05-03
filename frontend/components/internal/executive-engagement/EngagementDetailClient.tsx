"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth/AuthProvider";
import type {
  Engagement,
  EngagementFollowup,
} from "@/lib/types/executive-engagement";
import { FullDossierCard } from "./FullDossierCard";

interface Props {
  engagement: Engagement;
  followups: EngagementFollowup[];
  prevId: string | null;
  nextId: string | null;
  prevName: string | null;
  nextName: string | null;
}

export function EngagementDetailClient({
  engagement,
  followups,
  prevId,
  nextId,
  prevName,
  nextName,
}: Props) {
  const { isAdmin } = useAuth();
  return (
    <div>
      {/* Back link */}
      <Link
        href="/executive-engagement"
        className="inline-flex items-center gap-2 text-[13px] text-text-dim hover:text-text-secondary transition-colors mb-5"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M10 4l-4 4 4 4" />
        </svg>
        All engagements
      </Link>

      {/* Dossier */}
      <FullDossierCard
        engagement={engagement}
        followups={followups}
        isAdmin={isAdmin}
      />

      {/* Prev / Next navigation */}
      {(prevId || nextId) && (
        <div
          className="flex items-center justify-between mt-6 pt-5"
          style={{
            borderTop: "1px solid rgba(255,255,255,0.04)",
          }}
        >
          {prevId ? (
            <Link
              href={`/executive-engagement/${prevId}`}
              className="inline-flex items-center gap-2 text-[13px] text-text-dim hover:text-text-secondary transition-colors"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M10 4l-4 4 4 4" />
              </svg>
              {prevName}
            </Link>
          ) : (
            <div />
          )}
          {nextId ? (
            <Link
              href={`/executive-engagement/${nextId}`}
              className="inline-flex items-center gap-2 text-[13px] text-text-dim hover:text-text-secondary transition-colors"
            >
              {nextName}
              <svg
                width="14"
                height="14"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M6 4l4 4-4 4" />
              </svg>
            </Link>
          ) : (
            <div />
          )}
        </div>
      )}
    </div>
  );
}
