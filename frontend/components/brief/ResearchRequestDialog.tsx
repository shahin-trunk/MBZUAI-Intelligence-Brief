"use client";

import { useState, useEffect } from "react";
import { useBriefInteraction } from "@/lib/contexts/BriefInteractionContext";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { CheckCircle2 } from "lucide-react";

export default function ResearchRequestDialog() {
  const {
    researchDialogItemId,
    setResearchDialogItemId,
    findItem,
    submitRequest,
    hasPendingRequest,
    getRequestForItem,
  } = useBriefInteraction();

  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const isOpen = researchDialogItemId !== null;
  const item = researchDialogItemId ? findItem(researchDialogItemId) : null;
  const existingRequest = researchDialogItemId
    ? getRequestForItem(researchDialogItemId)
    : null;
  const alreadyRequested = researchDialogItemId
    ? hasPendingRequest(researchDialogItemId)
    : false;

  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen) {
      setNote("");
      setIsSubmitting(false);
      setShowSuccess(false);
    }
  }, [isOpen]);

  function handleClose() {
    setResearchDialogItemId(null);
  }

  async function handleSubmit() {
    if (!researchDialogItemId || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await submitRequest(researchDialogItemId, note || undefined);
      setShowSuccess(true);

      // Auto-close after 1.5s
      setTimeout(() => {
        handleClose();
      }, 1500);
    } catch {
      // Error toast is handled by the hook.
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="max-h-[calc(100vh-2rem)] max-w-md overflow-y-auto bg-bg-secondary p-4 sm:p-6 border-border-accent">
        <DialogHeader>
          <DialogTitle className="font-mono text-[14px] uppercase tracking-[0.12em] text-text-bright">
            Request Deeper Research
          </DialogTitle>
        </DialogHeader>

        {showSuccess ? (
          /* Success state */
          <div className="flex flex-col items-center gap-3 py-8">
            <CheckCircle2 className="h-8 w-8 text-accent-success" />
            <span className="font-mono text-[14px] text-accent-success">
              Request submitted
            </span>
          </div>
        ) : alreadyRequested && existingRequest ? (
          /* Already requested state */
          <div className="space-y-4 py-4">
            <p className="font-sans text-[14px] text-text-secondary">
              You&apos;ve already requested research on this item.
            </p>
            <div className="rounded-sm border border-border-primary bg-bg-tertiary p-3 space-y-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-text-muted">
                  Status
                </span>
                <span className="font-mono text-[13px] text-continuity capitalize">
                  {existingRequest.status.replace("_", " ")}
                </span>
              </div>
              {existingRequest.request_note && (
                <p className="font-sans text-[14px] text-text-muted italic">
                  &ldquo;{existingRequest.request_note}&rdquo;
                </p>
              )}
            </div>
          </div>
        ) : (
          /* Form state */
          <div className="space-y-4">
            {/* Item context */}
            {item && (
              <div className="space-y-1">
                <p className="font-serif text-[15px] text-text-primary leading-snug">
                  Re: {item.headline}
                </p>
                <p className="font-mono text-[13px] text-text-muted">
                  Section: {item.section}
                </p>
              </div>
            )}

            {/* Note input */}
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="What specifically would you like to know?"
              className="min-h-[80px] bg-bg-tertiary border-border-primary text-text-primary text-[14px] placeholder:text-text-muted/60 resize-none"
            />

            {/* Example text */}
            <p className="font-sans text-[14px] text-text-muted italic">
              Example: &ldquo;Historical context on this entity&rdquo;,
              &ldquo;Competitive implications for MBZUAI&rdquo;, &ldquo;Full
              policy analysis&rdquo;
            </p>
          </div>
        )}

        {!showSuccess && !alreadyRequested && (
          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={handleClose}
              className="text-text-muted text-[14px] font-mono"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="bg-accent-primary hover:bg-accent-primary/80 text-[14px] font-mono"
            >
              {isSubmitting ? "Submitting..." : "Submit Request"}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
