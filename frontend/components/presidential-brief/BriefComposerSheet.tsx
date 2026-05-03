"use client";

import type { ReactNode } from "react";
import { Drawer } from "vaul";
import { cn } from "@/lib/utils";

/** Shared bottom sheet chrome for Follow up + Note composers — handle, insets, title→input gap. */
export const BRIEF_COMPOSER_HANDLE =
  "mx-auto mt-2 mb-2 h-1 w-10 shrink-0 rounded-full bg-text-muted/30";

export const BRIEF_COMPOSER_SCROLL =
  "flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 pb-[max(16px,env(safe-area-inset-bottom,0px))] pt-0";

const TITLE_TEXT =
  "font-display text-lg leading-snug text-text-primary";

/**
 * Shared `Drawer.Content` layout for Follow up + Note — same inset, top offset,
 * max height, handle→title→input rhythm (via `BRIEF_COMPOSER_SCROLL` column `gap-3`).
 * Only z-index differs per surface (stacking).
 */
const BRIEF_COMPOSER_SHEET_CONTENT_BASE =
  "fixed inset-x-0 bottom-0 mt-32 flex min-h-0 max-h-[min(76dvh,560px)] flex-col rounded-t-[16px] border-t border-rule-light bg-bg-surface shadow-[0_-8px_32px_rgba(0,0,0,0.06)]";

/** `Drawer.Content` className — card stack “Request research” sheet. */
export const BRIEF_COMPOSER_SHEET_CONTENT_FOLLOWUP = cn(
  BRIEF_COMPOSER_SHEET_CONTENT_BASE,
  "z-[56]"
);

/** `Drawer.Content` className — story detail Note sheet (same chrome as follow-up). */
export const BRIEF_COMPOSER_SHEET_CONTENT_NOTE = cn(
  BRIEF_COMPOSER_SHEET_CONTENT_BASE,
  "z-[61]"
);

export interface BriefComposerSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  overlayClassName: string;
  contentClassName: string;
  /** Shown as the sheet heading (visible + dialog title). */
  title: string;
  /** e.g. Save on the right for Note sheet; omit for Follow up. */
  headerTrailing?: ReactNode;
  children: ReactNode;
}

export default function BriefComposerSheet({
  open,
  onOpenChange,
  overlayClassName,
  contentClassName,
  title,
  headerTrailing,
  children,
}: BriefComposerSheetProps) {
  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange}>
      <Drawer.Portal>
        <Drawer.Overlay className={overlayClassName} />
        <Drawer.Content className={contentClassName}>
          <Drawer.Description className="sr-only">
            Use the text field below.
          </Drawer.Description>
          <Drawer.Handle className={BRIEF_COMPOSER_HANDLE} />
          <div className={BRIEF_COMPOSER_SCROLL}>
            <div className="flex min-h-0 shrink-0 items-center justify-between gap-3">
              <Drawer.Title className={cn(TITLE_TEXT, "min-w-0 flex-1")}>
                {title}
              </Drawer.Title>
              {headerTrailing}
            </div>
            {children}
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
