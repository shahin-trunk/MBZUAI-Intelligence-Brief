"use client";

import { formatBriefDate } from "@/lib/utils";

interface DividerCardProps {
  label: string;
  kind: "section" | "day";
}

export default function DividerCard({ label, kind }: DividerCardProps) {
  return (
    <div className="flex h-full w-full items-start justify-center px-6 pb-8 pt-6 lg:mx-auto lg:max-w-[640px]">
      <div className="text-center">
        {kind === "section" ? (
          <>
            <div className="mx-auto mb-3 h-px w-16 bg-rule" />
            <p className="font-ui text-[14px] font-semibold uppercase tracking-[0.08em] text-text-muted">
              {label}
            </p>
            <div className="mx-auto mt-3 h-px w-16 bg-rule" />
          </>
        ) : (
          <>
            <div className="mx-auto mb-4 h-px w-24 bg-rule" />
            <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              {label}
            </p>
            <div className="mx-auto mt-4 h-px w-24 bg-rule" />
          </>
        )}
      </div>
    </div>
  );
}
