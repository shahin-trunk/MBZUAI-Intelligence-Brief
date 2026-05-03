"use client";

import { useState } from "react";
import { useBriefInteraction } from "@/lib/contexts/BriefInteractionContext";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Copy, Mail, CheckCircle2 } from "lucide-react";
import {
  renderMarkdown,
  stripMarkdownFormatting,
} from "@/lib/rendering/markdown";

export default function ShareDialog() {
  const { shareDialogItemId, setShareDialogItemId, findItem } =
    useBriefInteraction();

  const [copied, setCopied] = useState(false);

  const isOpen = shareDialogItemId !== null;
  const item = shareDialogItemId ? findItem(shareDialogItemId) : null;

  function handleClose() {
    setShareDialogItemId(null);
    setCopied(false);
  }

  function getShareText(): string {
    if (!item) return "";
    const lines = [item.headline, "", stripMarkdownFormatting(item.main_bullet)];
    if (item.source_url) {
      lines.push("", `Source: ${item.source_name} — ${item.source_url}`);
    }
    return lines.join("\n");
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(getShareText());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textArea = document.createElement("textarea");
      textArea.value = getShareText();
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  function handleEmail() {
    if (!item) return;
    const subject = encodeURIComponent(
      `Intelligence Brief: ${item.headline}`
    );
    const body = encodeURIComponent(getShareText());
    window.open(`mailto:?subject=${subject}&body=${body}`, "_self");
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="max-h-[calc(100vh-2rem)] max-w-md overflow-y-auto bg-bg-secondary p-4 sm:p-6 border-border-accent">
        <DialogHeader>
          <DialogTitle className="font-mono text-[14px] uppercase tracking-[0.12em] text-text-bright">
            Share Item
          </DialogTitle>
        </DialogHeader>

        {item && (
          <div className="space-y-4">
            {/* Preview card */}
            <div className="rounded-sm border border-border-primary bg-bg-tertiary p-4 space-y-2">
              <h4 className="font-serif text-[15px] text-text-bright leading-snug">
                {item.headline}
              </h4>
              <p className="font-sans text-[14px] text-text-secondary leading-relaxed line-clamp-3">
                {renderMarkdown(item.main_bullet)}
              </p>
              {item.source_url && (
                <p className="break-all font-mono text-[13px] text-text-muted">
                  Source: {item.source_name} &mdash;{" "}
                  <span className="text-accent-primary">
                    {item.source_url}
                  </span>
                </p>
              )}
            </div>

            {/* Action buttons */}
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                onClick={handleCopy}
                variant="outline"
                className="flex-1 border-border-primary bg-bg-tertiary text-[14px] font-mono text-text-primary hover:bg-bg-accent gap-2"
              >
                {copied ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-accent-success" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy to Clipboard
                  </>
                )}
              </Button>
              <Button
                onClick={handleEmail}
                variant="outline"
                className="flex-1 border-border-primary bg-bg-tertiary text-[14px] font-mono text-text-primary hover:bg-bg-accent gap-2"
              >
                <Mail className="h-4 w-4" />
                Send via Email
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
