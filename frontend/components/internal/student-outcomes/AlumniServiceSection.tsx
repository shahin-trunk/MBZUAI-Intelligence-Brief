"use client";

import { cn } from "@/lib/utils";
import type {
  AlumniServiceActivity,
  AlumniServiceAward,
} from "@/lib/types/internal-intelligence";

interface AlumniServiceSectionProps {
  activities: AlumniServiceActivity[];
  awards: AlumniServiceAward[];
}

const TYPE_STYLES: Record<AlumniServiceActivity["type"], string> = {
  milestone: "bg-sig-high/15 text-sig-high border-sig-high/30",
  event: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  program: "bg-green-500/15 text-green-400 border-green-500/30",
};

const TYPE_LABELS: Record<AlumniServiceActivity["type"], string> = {
  milestone: "Milestone",
  event: "Event",
  program: "Program",
};

export function AlumniServiceSection({
  activities,
  awards,
}: AlumniServiceSectionProps) {
  return (
    <div className="space-y-6">
      {/* Activities */}
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
          Recent Activities
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
          {activities.map((activity) => (
            <div
              key={activity.id}
              className="bg-bg-secondary rounded-sm border border-border-primary px-7 py-[22px]"
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="font-serif text-base text-text-bright leading-snug">
                  {activity.title}
                </p>
                <span
                  className={cn(
                    "shrink-0 inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[12px] font-medium",
                    TYPE_STYLES[activity.type]
                  )}
                >
                  {TYPE_LABELS[activity.type]}
                </span>
              </div>
              <p className="font-sans text-sm text-text-secondary leading-relaxed">
                {activity.description}
              </p>
              <p className="mt-2 font-mono text-[12px] text-text-muted">
                {new Date(activity.date + "T00:00:00").toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Awards */}
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted mb-3">
          Alumni Awards
        </p>
        <div className="bg-bg-tertiary rounded-sm border border-border-primary p-4">
          <ul className="space-y-3">
            {awards.map((award) => (
              <li key={award.id} className="flex items-start gap-3">
                <svg
                  className="w-4 h-4 mt-0.5 shrink-0 text-sig-high"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                  />
                </svg>
                <div>
                  <p className="font-mono text-[14px] text-text-secondary font-medium">
                    {award.title}
                  </p>
                  <p className="font-mono text-[13px] text-text-muted mt-0.5">
                    {award.description}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
