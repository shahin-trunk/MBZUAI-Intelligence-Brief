"use client";

import { ArrowUp, Loader2, Mic } from "lucide-react";
import { useState, useRef, useEffect, useCallback } from "react";
import { useSpeechToText } from "@/lib/presidential-brief/hooks/useSpeechToText";
import { cn } from "@/lib/utils";

export type AnnotationInputVariant = "notes" | "followup" | "noteSheet";

interface AnnotationInputProps {
  onSubmit?: (text: string) => void;
  /** `notes`: inline notes panel (Save + mic). `followup`: bottom-sheet composer (Send + mock voice flow). `noteSheet`: same chrome as followup, mic only (Save lives in sheet header). */
  variant?: AnnotationInputVariant;
  /** Controlled text (required for `noteSheet`). */
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
}

const FOLLOWUP_PLACEHOLDER =
  "What should we research for you? Add questions, topics, angles, or anything you want explored…";

/** Mock transcript after “Transcribing…” (no backend yet). */
const MOCK_FOLLOWUP_TRANSCRIPT =
  "Please dig deeper on how the fund will allocate capital across seed vs growth stages, and whether non-UAE founders can apply.";

type FollowupRecordPhase = "idle" | "listening" | "transcribing";

const TRANSCRIBE_MS = 1500;

function FollowupStatusText({ label }: { label: string }) {
  return (
    <span
      className="followup-status-text inline-flex min-w-0 max-w-full items-baseline font-ui text-[13px] leading-snug"
      aria-live="polite"
      aria-label={`${label}...`}
    >
      <span className="followup-status-label truncate">{label}</span>
      <span className="followup-status-ellipsis" aria-hidden>
        <span className="followup-status-dot">.</span>
        <span className="followup-status-dot">.</span>
        <span className="followup-status-dot">.</span>
      </span>
    </span>
  );
}

const NOTE_SHEET_DEFAULT_PLACEHOLDER =
  "Add observations, questions, or follow-up items for this article.";

export default function AnnotationInput({
  onSubmit,
  variant = "notes",
  value: controlledValue,
  onChange: controlledOnChange,
  placeholder: placeholderProp,
}: AnnotationInputProps) {
  const [uncontrolledText, setUncontrolledText] = useState("");
  const isNoteSheet = variant === "noteSheet";
  const text = isNoteSheet ? (controlledValue ?? "") : uncontrolledText;
  const setText = useCallback(
    (v: string) => {
      if (isNoteSheet) {
        controlledOnChange?.(v);
      } else {
        setUncontrolledText(v);
      }
    },
    [isNoteSheet, controlledOnChange]
  );
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const speech = useSpeechToText();
  const { resetTranscript } = speech;
  const [followupPhase, setFollowupPhase] =
    useState<FollowupRecordPhase>("idle");
  /** After real STT stop, mirror follow-up sheet “Transcribing…” chrome briefly. */
  const [noteSheetVoicePhase, setNoteSheetVoicePhase] = useState<
    "idle" | "transcribing"
  >("idle");
  const transcribeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  const clearTranscribeTimer = useCallback(() => {
    if (transcribeTimerRef.current) {
      clearTimeout(transcribeTimerRef.current);
      transcribeTimerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearTranscribeTimer(), [clearTranscribeTimer]);

  // Sync speech transcript into textarea (notes + note sheet — follow-up uses mock flow)
  /* eslint-disable react-hooks/set-state-in-effect -- mirror browser STT into composer */
  useEffect(() => {
    if (variant === "followup") return;
    if (speech.transcript) {
      setText(speech.transcript);
    }
  }, [speech.transcript, variant, setText]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (!isNoteSheet || controlledValue !== "") return;
    clearTranscribeTimer();
    setNoteSheetVoicePhase("idle");
    resetTranscript();
  }, [controlledValue, isNoteSheet, resetTranscript, clearTranscribeTimer]);

  const maxTextareaPx =
    variant === "followup" || variant === "noteSheet" ? 200 : 120;

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, maxTextareaPx) + "px";
    }
  }, [text, maxTextareaPx]);

  const handleSubmit = () => {
    const trimmed = text.replace(/\s*\[.*\]$/, "").trim();
    if (!trimmed) return;
    clearTranscribeTimer();
    if (variant === "followup") {
      setFollowupPhase("idle");
    }
    onSubmit?.(trimmed);
    if (!isNoteSheet) {
      setText("");
      resetTranscript();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (variant === "noteSheet") return;
    if (variant === "followup" && followupPhase === "transcribing") {
      if (e.key === "Enter" && !e.shiftKey) e.preventDefault();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const trimmed = text.replace(/\s*\[.*\]$/, "").trim();
  const canSubmit = !!trimmed;

  const startFollowupListen = () => {
    if (followupPhase === "transcribing") return;
    clearTranscribeTimer();
    setFollowupPhase("listening");
  };

  const stopFollowupListen = () => {
    if (followupPhase !== "listening") return;
    clearTranscribeTimer();
    setFollowupPhase("transcribing");
    transcribeTimerRef.current = setTimeout(() => {
      setText(MOCK_FOLLOWUP_TRANSCRIPT);
      setFollowupPhase("idle");
      transcribeTimerRef.current = null;
    }, TRANSCRIBE_MS);
  };

  const startNoteSheetListen = () => {
    if (noteSheetVoicePhase === "transcribing") return;
    clearTranscribeTimer();
    setNoteSheetVoicePhase("idle");
    speech.startListening();
  };

  const stopNoteSheetListen = () => {
    if (!speech.isListening) return;
    clearTranscribeTimer();
    speech.stopListening();
    setNoteSheetVoicePhase("transcribing");
    transcribeTimerRef.current = setTimeout(() => {
      setNoteSheetVoicePhase("idle");
      transcribeTimerRef.current = null;
    }, TRANSCRIBE_MS);
  };

  const micButton = speech.isSupported ? (
    <button
      type="button"
      onClick={() =>
        speech.isListening ? speech.stopListening() : speech.startListening()
      }
      className={cn(
        "flex min-h-[44px] min-w-[44px] items-center justify-center rounded-[10px] transition-colors",
        speech.isListening
          ? "bg-text-primary/8 text-text-primary dark:bg-text-primary/15"
          : "text-text-muted hover:bg-bg-surface-2 hover:text-text-primary"
      )}
      aria-label={speech.isListening ? "Stop voice input" : "Start voice input"}
    >
      {speech.isListening ? (
        <span className="relative flex h-5 w-5 items-center justify-center">
          <span className="absolute h-5 w-5 animate-ping rounded-full bg-text-primary/12 dark:bg-text-primary/20" />
          <Mic className="relative h-5 w-5" strokeWidth={2} aria-hidden />
        </span>
      ) : (
        <Mic className="h-5 w-5" strokeWidth={2} aria-hidden />
      )}
    </button>
  ) : null;

  const followupActionBtn =
    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors";

  if (variant === "followup" || variant === "noteSheet") {
    const isNoteSheetTranscribing =
      variant === "noteSheet" && noteSheetVoicePhase === "transcribing";
    const isTranscribing =
      (variant === "followup" && followupPhase === "transcribing") ||
      isNoteSheetTranscribing;
    const isListening =
      variant === "followup"
        ? followupPhase === "listening"
        : speech.isListening && !isNoteSheetTranscribing;
    const composerPlaceholder = isTranscribing
      ? "Transcribing…"
      : variant === "noteSheet"
        ? (placeholderProp ?? NOTE_SHEET_DEFAULT_PLACEHOLDER)
        : FOLLOWUP_PLACEHOLDER;

    return (
      <div>
        <div
          className={cn(
            "relative rounded-[12px] border border-rule bg-bg-surface-2",
            /* Avoid accent (reads as red) while voice status is active — same chrome as idle border. */
            isListening || isTranscribing
              ? "focus-within:border-rule"
              : "focus-within:border-accent"
          )}
        >
          <textarea
            ref={textareaRef}
            id={variant === "noteSheet" ? "story-detail-note-sheet" : undefined}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              if (variant === "followup" && followupPhase === "listening") {
                setFollowupPhase("idle");
                clearTranscribeTimer();
              }
            }}
            onKeyDown={handleKeyDown}
            placeholder={composerPlaceholder}
            rows={2}
            readOnly={isTranscribing}
            aria-busy={isTranscribing}
            aria-label={variant === "noteSheet" ? "Note text" : undefined}
            className="min-h-[72px] w-full resize-none rounded-[12px] border-0 bg-transparent pl-4 pr-4 pt-3 pb-12 font-body text-[15px] leading-relaxed text-text-primary placeholder:text-text-muted focus:outline-none disabled:opacity-60"
          />
          <div className="absolute bottom-2 right-2 flex max-w-[calc(100%-1.5rem)] items-center justify-end gap-2">
            {variant === "noteSheet" ? (
              <>
                {isNoteSheetTranscribing ? (
                  <>
                    <FollowupStatusText label="Transcribing" />
                    <div
                      className={cn(
                        followupActionBtn,
                        "bg-bg-primary text-text-secondary ring-1 ring-rule"
                      )}
                      role="status"
                      aria-label="Transcribing"
                    >
                      <Loader2
                        className="h-4 w-4 animate-spin"
                        strokeWidth={2.25}
                        aria-hidden
                      />
                    </div>
                  </>
                ) : isListening ? (
                  <>
                    <FollowupStatusText label="Listening" />
                    <button
                      type="button"
                      onClick={stopNoteSheetListen}
                      className={cn(
                        followupActionBtn,
                        "bg-surface-control text-bg-surface hover:opacity-90 active:opacity-80 dark:text-text-primary"
                      )}
                      aria-label="Stop voice input"
                    >
                      <span
                        className="block h-2 w-2 shrink-0 rounded-[1px] bg-bg-surface dark:bg-bg-primary"
                        aria-hidden
                      />
                    </button>
                  </>
                ) : speech.isSupported ? (
                  <button
                    type="button"
                    onClick={startNoteSheetListen}
                    className={cn(
                      followupActionBtn,
                      "text-text-secondary ring-1 ring-transparent hover:bg-bg-primary hover:text-text-primary"
                    )}
                    aria-label="Start voice input"
                  >
                    <Mic
                      className="h-[17px] w-[17px]"
                      strokeWidth={2}
                      aria-hidden
                    />
                  </button>
                ) : null}
              </>
            ) : canSubmit ? (
              <button
                type="button"
                onClick={handleSubmit}
                className={cn(
                  followupActionBtn,
                  "bg-accent text-white hover:opacity-90 active:opacity-80"
                )}
                aria-label="Send follow-up request"
              >
                <ArrowUp className="h-4 w-4" strokeWidth={2.25} aria-hidden />
              </button>
            ) : isTranscribing ? (
              <>
                <FollowupStatusText label="Transcribing" />
                <div
                  className={cn(
                    followupActionBtn,
                    "bg-bg-primary text-text-secondary ring-1 ring-rule"
                  )}
                  role="status"
                  aria-label="Transcribing"
                >
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    strokeWidth={2.25}
                    aria-hidden
                  />
                </div>
              </>
            ) : isListening ? (
              <>
                <FollowupStatusText label="Listening" />
                <button
                  type="button"
                  onClick={stopFollowupListen}
                  className={cn(
                    followupActionBtn,
                    "bg-surface-control text-bg-surface hover:opacity-90 active:opacity-80 dark:text-text-primary"
                  )}
                  aria-label="Stop recording"
                >
                  <span
                    className="block h-2 w-2 shrink-0 rounded-[1px] bg-bg-surface dark:bg-bg-primary"
                    aria-hidden
                  />
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={startFollowupListen}
                className={cn(
                  followupActionBtn,
                  "text-text-secondary ring-1 ring-transparent hover:bg-bg-primary hover:text-text-primary"
                )}
                aria-label="Start voice input"
              >
                <Mic className="h-[17px] w-[17px]" strokeWidth={2} aria-hidden />
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-3">
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Add a note..."
        rows={1}
        className={cn(
          "w-full resize-none rounded-[4px] border border-rule bg-bg-surface-2 px-3 py-2.5 font-body text-[14px] leading-[1.5] text-text-primary placeholder:text-text-muted focus:outline-none",
          speech.isListening ? "focus:border-rule" : "focus:border-accent"
        )}
      />
      <div className="mt-2 flex items-center justify-between">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {micButton}
          {speech.isListening && (
            <FollowupStatusText label="Listening" />
          )}
        </div>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-[4px] bg-accent px-4 py-1.5 font-ui text-[12px] font-semibold text-white transition-opacity disabled:opacity-30"
        >
          Save
        </button>
      </div>
    </div>
  );
}
