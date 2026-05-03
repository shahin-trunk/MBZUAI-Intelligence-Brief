"use client";

import { useState, useCallback } from "react";

interface Props {
  engagementId: string;
}

export function TeamRequestSection({ engagementId }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [showToast, setShowToast] = useState(false);

  const handleSend = useCallback(async () => {
    if (!message.trim() || isSending) return;

    setIsSending(true);
    try {
      const res = await fetch("/api/internal/engagement-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engagementId, message: message.trim() }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to send request");
      }

      setMessage("");
      setIsOpen(false);
      setShowToast(true);
      setTimeout(() => setShowToast(false), 4000);
    } catch (err) {
      console.error("Failed to send request:", err);
    } finally {
      setIsSending(false);
    }
  }, [message, isSending, engagementId]);

  return (
    <div
      className="rounded-[10px] px-5 py-3"
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      <div className="flex items-center justify-between">
        <h4
          className="text-[11px] uppercase font-semibold font-mono text-text-secondary"
          style={{ letterSpacing: "0.06em" }}
        >
          Request from Team
        </h4>
        {!isOpen && (
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            className="rounded-[6px] px-3.5 py-1.5 text-[12px] font-medium transition-colors hover:opacity-80"
            style={{
              border: "1px solid rgba(212,168,67,0.25)",
              color: "#D4A843",
              background: "rgba(212,168,67,0.06)",
            }}
          >
            + New request
          </button>
        )}
      </div>

      {/* Request form */}
      {isOpen && (
        <div
          className="mt-3 rounded-[10px] overflow-hidden"
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="e.g. Can you prepare a one-pager comparing our GPU infrastructure with what World Labs would need?"
            className="w-full min-h-[100px] bg-transparent text-[13px] text-text-primary placeholder:text-text-dim outline-none resize-none px-5 pt-4 pb-3"
          />

          <div
            className="flex items-center justify-between px-5 py-3"
            style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}
          >
            <span className="text-[12px] text-text-dim">
              Sent to Strategy team queue
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  setMessage("");
                }}
                className="text-[12px] text-text-dim hover:text-text-secondary transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSend}
                disabled={isSending || !message.trim()}
                className="rounded-[6px] px-3.5 py-1.5 text-[12px] font-semibold transition-colors disabled:opacity-40"
                style={{ background: "var(--sig-high)", color: "var(--surface-primary)" }}
              >
                {isSending ? "Sending..." : "Send request"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Success toast */}
      {showToast && (
        <div
          className="mt-3 flex items-center gap-2 rounded-[8px] px-4 py-3"
          style={{
            background: "rgba(34,197,94,0.06)",
            border: "1px solid rgba(34,197,94,0.15)",
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 16 16"
            fill="none"
            stroke="#22C55E"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M13 4l-7 7-3-3" />
          </svg>
          <span className="text-[13px] text-[#22C55E]">
            Request sent to strategy team
          </span>
        </div>
      )}
    </div>
  );
}
