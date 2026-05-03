"use client";

import { useEffect } from "react";
import { hapticImpact } from "@/lib/presidential-brief/haptics";

interface ContextMenuProps {
  visible: boolean;
  onClose: () => void;
  onFlag: () => void;
  onOpenSource: () => void;
  onCopyHeadline: () => void;
  isFlagged: boolean;
  headline: string;
  sourceUrl?: string;
}

export default function ContextMenu({
  visible,
  onClose,
  onFlag,
  onOpenSource,
  onCopyHeadline,
  isFlagged,
  headline,
  sourceUrl,
}: ContextMenuProps) {
  // Trigger heavy haptic when menu becomes visible
  useEffect(() => {
    if (visible) {
      hapticImpact("heavy");
    }
  }, [visible]);

  if (!visible) return null;

  const handleFlag = () => {
    onFlag();
    onClose();
  };

  const handleOpenSource = () => {
    onOpenSource();
    onClose();
  };

  const handleCopyHeadline = () => {
    onCopyHeadline();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.30)", backdropFilter: "blur(4px)" }}
      onPointerDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="mx-4 w-full max-w-sm rounded-[4px] bg-bg-surface shadow-lg overflow-hidden">
        {/* Headline preview */}
        <div className="border-b border-rule-light px-4 py-3.5">
          <p className="font-display text-sm font-semibold leading-snug text-text-primary">
            {headline}
          </p>
        </div>

        {/* Actions */}
        <div>
          {/* Flag / Unflag */}
          <button
            className="flex w-full items-center gap-3 border-b border-rule-light px-4 py-3.5 text-left active:bg-bg-surface-2"
            onClick={handleFlag}
          >
            <span className="text-base">{isFlagged ? "✕" : "⚑"}</span>
            <span className="font-ui text-[14px] text-text-primary">
              {isFlagged ? "Unflag" : "Flag for team"}
            </span>
          </button>

          {/* Flag with note */}
          <button
            className="flex w-full items-center gap-3 border-b border-rule-light px-4 py-3.5 text-left active:bg-bg-surface-2"
            onClick={onClose}
          >
            <span className="text-base">💬</span>
            <span className="font-ui text-[14px] text-text-primary">Flag with note…</span>
          </button>

          {/* Open source — only if URL exists */}
          {sourceUrl && (
            <button
              className="flex w-full items-center gap-3 border-b border-rule-light px-4 py-3.5 text-left active:bg-bg-surface-2"
              onClick={handleOpenSource}
            >
              <span className="text-base">🔗</span>
              <span className="font-ui text-[14px] text-text-primary">Open source</span>
            </button>
          )}

          {/* Copy headline */}
          <button
            className="flex w-full items-center gap-3 px-4 py-3.5 text-left active:bg-bg-surface-2"
            onClick={handleCopyHeadline}
          >
            <span className="text-base">📋</span>
            <span className="font-ui text-[14px] text-text-primary">Copy headline</span>
          </button>
        </div>
      </div>
    </div>
  );
}
