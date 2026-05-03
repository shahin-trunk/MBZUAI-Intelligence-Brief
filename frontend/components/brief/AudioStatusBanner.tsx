"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

const POLL_INTERVAL = 5000; // 5 seconds
const TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

const STAGES = [
  { key: "pending", label: "Queued", step: 0 },
  { key: "generating_script", label: "Writing script", step: 1 },
  { key: "generating_audio", label: "Converting to speech", step: 2 },
  { key: "uploading", label: "Uploading audio", step: 3 },
] as const;

type AudioStatus = string | null;

function getStepIndex(status: AudioStatus): number {
  const match = STAGES.findIndex((s) => s.key === status);
  return match >= 0 ? match : 0;
}

function getLabel(status: AudioStatus): string {
  if (status === "failed") return "Audio generation failed";
  const match = STAGES.find((s) => s.key === status);
  return match?.label ?? "Preparing audio...";
}

interface AudioStatusBannerProps {
  initialStatus: string;
  briefDate: string;
}

export function AudioStatusBanner({
  initialStatus,
  briefDate,
}: AudioStatusBannerProps) {
  const router = useRouter();
  const [status, setStatus] = useState<AudioStatus>(initialStatus);
  const [timedOut, setTimedOut] = useState(false);
  const startedAt = useRef(Date.now());

  const poll = useCallback(async () => {
    try {
      const res = await fetch(`/api/audio-status?date=${briefDate}`);
      if (!res.ok) return;
      const data = await res.json();
      setStatus(data.audio_status);

      if (data.audio_status === "ready") {
        // Refresh the server component to pick up audio_url
        router.refresh();
        return "stop";
      }
      if (data.audio_status === "failed") {
        return "stop";
      }
    } catch {
      // Non-fatal — retry on next interval
    }

    // Check timeout
    if (Date.now() - startedAt.current > TIMEOUT_MS) {
      setTimedOut(true);
      return "stop";
    }

    return "continue";
  }, [briefDate, router]);

  useEffect(() => {
    // Don't poll for terminal states
    if (status === "ready" || status === "failed") return;

    const interval = setInterval(async () => {
      const result = await poll();
      if (result === "stop") clearInterval(interval);
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [poll, status]);

  // Don't render for terminal/null states
  if (!status || status === "ready") return null;

  const currentStep = getStepIndex(status);
  const isFailed = status === "failed";

  return (
    <div
      className={cn(
        "mt-4 rounded-md border px-4 py-3 flex items-center gap-4",
        isFailed
          ? "border-red-500/20 bg-red-500/5"
          : "border-border-primary bg-bg-tertiary",
      )}
    >
      {/* Step indicators */}
      <div className="flex items-center gap-1.5 shrink-0">
        {STAGES.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-1.5">
            <div
              className={cn(
                "w-2 h-2 rounded-full transition-colors",
                isFailed
                  ? "bg-red-500/30"
                  : i < currentStep
                    ? "bg-accent-primary"
                    : i === currentStep
                      ? "bg-accent-primary animate-pulse"
                      : "bg-border-primary",
              )}
            />
            {i < STAGES.length - 1 && (
              <div
                className={cn(
                  "w-3 h-px",
                  i < currentStep ? "bg-accent-primary/50" : "bg-border-primary",
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* Status label */}
      <div className="flex items-center gap-2 min-w-0">
        {!isFailed && !timedOut && (
          <svg
            className="w-3.5 h-3.5 shrink-0 text-accent-primary animate-spin"
            viewBox="0 0 16 16"
            fill="none"
          >
            <circle
              cx="8"
              cy="8"
              r="6"
              stroke="currentColor"
              strokeWidth="2"
              strokeDasharray="28"
              strokeDashoffset="8"
              strokeLinecap="round"
            />
          </svg>
        )}
        <span
          className={cn(
            "font-mono text-[13px]",
            isFailed ? "text-red-400" : "text-text-muted",
          )}
        >
          {timedOut
            ? "Audio generation may have failed. Check back later."
            : getLabel(status)}
        </span>
      </div>
    </div>
  );
}
