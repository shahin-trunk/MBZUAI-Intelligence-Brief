"use client";

import { useBriefInteraction } from "@/lib/contexts/BriefInteractionContext";
import { CheckCircle2 } from "lucide-react";

export default function BriefCompletionBar() {
  const { totalRead, totalItems } = useBriefInteraction();

  const isComplete = totalItems > 0 && totalRead >= totalItems;

  return (
    <div className="mt-12 mb-4 text-center">
      {isComplete ? (
        <div className="flex items-center justify-center gap-2 text-accent-success">
          <CheckCircle2 className="h-4 w-4" />
          <span className="font-mono text-[14px] uppercase tracking-[0.1em]">
            Brief reviewed
          </span>
        </div>
      ) : (
        <span className="font-mono text-[14px] text-text-muted">
          {totalRead} of {totalItems} items reviewed
        </span>
      )}
    </div>
  );
}
