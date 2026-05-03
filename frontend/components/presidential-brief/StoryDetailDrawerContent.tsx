"use client";

import Image from "next/image";
import { NotebookPen, SquareArrowOutUpRight, X } from "lucide-react";
import { useState, useEffect, useCallback, useRef } from "react";
import type { BriefItem } from "@/lib/types/brief";
import { renderAnalysisBlock, renderMarkdown } from "@/lib/rendering/markdown";
import { ExhibitRenderer } from "@/components/card-reader/ExhibitRenderer";
import { cn, formatSectionTagLabel } from "@/lib/utils";
import { sectionTagPaletteClasses } from "@/lib/presidential-brief/sectionTagPalette";
import {
  bulletLinesFromMainBullet,
  heroImageUrlForItem,
  sourceLogoUrlForItem,
} from "@/lib/presidential-brief/storyCardPlaceholders";
import AnnotationInput from "./AnnotationInput";
import BriefComposerSheet, {
  BRIEF_COMPOSER_SHEET_CONTENT_NOTE,
} from "./BriefComposerSheet";

function HeroImagePlaceholder() {
  return (
    <Image
      src="/placeholders/hero-fallback.png"
      alt=""
      fill
      className="object-cover"
      sizes="100vw"
      aria-hidden
    />
  );
}

function detailArticleParagraphs(item: BriefItem, lines: string[]): string[] {
  // Prefer v2 analysis field (single reportorial lede-extension paragraph).
  // Mirrors CardExpanded.tsx:15-16. Falls back to legacy context + implication
  // for older briefs written before the v2 schema.
  const analysis = item.analysis?.trim();
  if (analysis) return [analysis];

  const out: string[] = [];
  const ctx = item.context?.trim();
  const impl = item.implication?.trim();
  if (ctx) out.push(ctx);
  if (impl) out.push(impl);
  if (out.length > 0) return out;

  const lead =
    lines[0] ||
    item.main_bullet.split(/[.\n]/)[0]?.trim() ||
    item.headline;
  const sentence = lead.endsWith(".") ? lead : `${lead}.`;
  return [sentence];
}

export interface StoryDetailDrawerContentProps {
  item: BriefItem;
  isFlagged: boolean;
  onClose: () => void;
  getStorySheetNoteText: () => string;
  /** Return a rejected promise if persistence fails; success toast runs only after this settles. */
  onSaveStorySheetNote: (text: string) => void | Promise<void>;
}

/** Pinned drawer chrome — min 44×44px touch targets (mobile). */
const DRAWER_CHROME_BTN =
  "relative z-10 flex h-11 w-11 min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-full bg-bg-surface/78 text-text-primary shadow-sm backdrop-blur-xl transition-colors hover:bg-bg-surface/92 active:opacity-90 dark:bg-bg-surface/55 dark:hover:bg-bg-surface/72";

/** Horizontal inset: chrome, hero title, and body share the same edge alignment */
const DETAIL_INSET_X = "px-6 lg:px-8";

/** Note FAB — fixed 48×48px hit target (explicit px so it never drifts with spacing scale). */
const NOTE_FAB_BTN =
  "absolute z-40 box-border flex h-[48px] w-[48px] min-h-[48px] min-w-[48px] shrink-0 transform-gpu items-center justify-center rounded-full bg-accent text-white shadow-md shadow-accent/25 transition-[opacity,transform,colors] duration-[450ms] ease-[cubic-bezier(0.33,1,0.32,1)] motion-reduce:transition-none hover:bg-accent-hover active:opacity-90";

export default function StoryDetailDrawerContent({
  item,
  isFlagged,
  onClose,
  getStorySheetNoteText,
  onSaveStorySheetNote,
}: StoryDetailDrawerContentProps) {
  const heroSrc = heroImageUrlForItem(item);
  const resolvedSourceLogoSrc = sourceLogoUrlForItem(item);
  const logoCandidates = [
    resolvedSourceLogoSrc,
    "/placeholders/source-logo.svg",
  ].filter((value): value is string => Boolean(value));
  const [imgFailed, setImgFailed] = useState(false);
  const [logoIndex, setLogoIndex] = useState(0);
  const sourceLogoSrc = logoCandidates[Math.min(logoIndex, logoCandidates.length - 1)];

  /* eslint-disable react-hooks/set-state-in-effect -- reset when item / URLs change */
  useEffect(() => {
    setImgFailed(false);
  }, [heroSrc]);

  useEffect(() => {
    setLogoIndex(0);
  }, [resolvedSourceLogoSrc]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const showImage = heroSrc && !imgFailed;
  const lines = (
    item.key_bullets?.filter((line) => line.trim().length > 0) ??
    bulletLinesFromMainBullet(item.main_bullet, 8)
  ).slice(0, 8);

  const [noteSheetOpen, setNoteSheetOpen] = useState(false);
  const [sheetDraft, setSheetDraft] = useState("");
  const [noteFabVisible, setNoteFabVisible] = useState(true);
  const [noteSaveToast, setNoteSaveToast] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);
  const [noteSaveBusy, setNoteSaveBusy] = useState(false);
  const getStorySheetNoteTextRef = useRef(getStorySheetNoteText);
  getStorySheetNoteTextRef.current = getStorySheetNoteText;

  useEffect(() => {
    if (!noteSheetOpen) return;
    setSheetDraft(getStorySheetNoteTextRef.current());
  }, [noteSheetOpen, item.id]);
  const [readProgressPercent, setReadProgressPercent] = useState(0);
  const lastScrollTopRef = useRef(0);

  const onDetailScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const top = el.scrollTop;
    const delta = top - lastScrollTopRef.current;
    lastScrollTopRef.current = top;

    const maxScroll = el.scrollHeight - el.clientHeight;
    const pct =
      maxScroll <= 0 ? 100 : Math.min(100, (top / maxScroll) * 100);
    setReadProgressPercent(pct);

    if (top > 100 && delta > 0) setNoteFabVisible(false);
    if (delta < 0 || top < 60) setNoteFabVisible(true);
  }, []);

  const hasStoredNote = getStorySheetNoteText().trim().length > 0;
  const canSaveNote =
    sheetDraft.trim().length > 0 || hasStoredNote;

  useEffect(() => {
    if (!noteSaveToast) return;
    const id = window.setTimeout(() => setNoteSaveToast(null), 3200);
    return () => window.clearTimeout(id);
  }, [noteSaveToast]);

  const saveNoteFromSheet = () => {
    if (!canSaveNote || noteSaveBusy) return;
    const trimmedDraft = sheetDraft.trim();
    const clearingNote = trimmedDraft.length === 0 && hasStoredNote;
    void (async () => {
      setNoteSaveBusy(true);
      try {
        await Promise.resolve(onSaveStorySheetNote(sheetDraft));
        setNoteSheetOpen(false);
        setSheetDraft("");
        setNoteSaveToast({
          tone: "success",
          text: clearingNote ? "removed" : "saved",
        });
      } catch {
        setNoteSaveToast({
          tone: "error",
          text: "Couldn’t save note. Try again.",
        });
      } finally {
        setNoteSaveBusy(false);
      }
    })();
  };

  const openOrShareSource = useCallback(async () => {
    const url = item.source_url?.trim();
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    try {
      if (typeof navigator !== "undefined" && navigator.share) {
        await navigator.share({
          title: item.headline,
          text: item.main_bullet.slice(0, 280),
        });
      }
    } catch {
      /* dismissed */
    }
  }, [item]);

  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-1 flex-col">
      {/* Pinned above scroll — progress + chrome; safe-area matches CardTopChrome (CardHeader.tsx) */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 z-30"
        style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
      >
        <div className="pointer-events-none px-0 pb-1 pt-0">
          <div
            className="relative h-0.5 w-full overflow-hidden bg-text-muted/15"
            role="progressbar"
            aria-valuenow={Math.round(readProgressPercent)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Article scroll progress"
          >
            <div
              className="h-full bg-accent transition-[width] duration-100 ease-out"
              style={{ width: `${readProgressPercent}%` }}
            />
          </div>
        </div>
        <div
          className={cn(
            "pointer-events-auto flex min-h-11 items-center justify-between py-2",
            DETAIL_INSET_X
          )}
        >
          <button
            type="button"
            onClick={onClose}
            className={DRAWER_CHROME_BTN}
            aria-label="Close"
          >
            <X className="h-5 w-5" strokeWidth={2} aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => void openOrShareSource()}
            className={DRAWER_CHROME_BTN}
            aria-label={
              item.source_url?.trim() ? "Open source article" : "Share"
            }
          >
            <SquareArrowOutUpRight className="h-5 w-5" strokeWidth={2} aria-hidden />
          </button>
        </div>
      </div>

      <div
        className="story-detail-scroll-region min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        onScroll={onDetailScroll}
      >
        <div className="relative isolate min-h-[min(calc(15rem+6px),calc(40dvh+6px))] w-full overflow-hidden bg-black">
          {showImage ? (
            <Image
              src={heroSrc}
              alt=""
              fill
              className="object-cover"
              sizes="100vw"
              priority={false}
              onError={() => setImgFailed(true)}
            />
          ) : (
            <HeroImagePlaceholder />
          )}
          <div
            className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/28 to-black/12"
            aria-hidden
          />

          {/* Sit above the sheet overlap (-mt-5 on body) so headline isn’t covered */}
          <div
            className={cn(
              // ~20px lower than earlier anchor (12px + 8px) — layout shift reads more reliably than translate inside overflow-hidden hero
              "absolute bottom-[max(calc(3.25rem-1.25rem),calc(9dvh-1.25rem))] right-0 w-full text-left sm:bottom-[max(calc(3.5rem-1.25rem),calc(10dvh-1.25rem))]",
              DETAIL_INSET_X
            )}
          >
            {item.section?.trim() ? (
              <span
                className={`inline-flex max-w-full items-center rounded-full px-2.5 py-0.5 font-ui text-[12px] font-semibold sm:text-[13px] ${sectionTagPaletteClasses(item.section.trim())}`}
              >
                {formatSectionTagLabel(item.section)}
              </span>
            ) : null}
            <h2
              className={cn(
                "font-display text-[22px] font-normal leading-[1.2] text-white sm:text-[24px]",
                item.section?.trim() ? "mt-2" : "mt-0"
              )}
            >
              {item.headline}
              {isFlagged ? (
                <span className="ml-2 text-amber-300" aria-label="Flagged">
                  ⚑
                </span>
              ) : null}
            </h2>
          </div>
        </div>

        <div
          className={cn(
            "relative z-[1] -mt-5 rounded-t-[20px] bg-bg-surface pb-8 pt-6",
            DETAIL_INSET_X
          )}
        >
          {lines.length > 0 ? (
            <ul className="list-inside list-disc space-y-2 font-body text-[16px] font-normal leading-snug text-text-secondary marker:text-accent sm:leading-[1.55]">
              {lines.map((line, i) => (
                <li key={i} className="pl-0.5">
                  {renderMarkdown(line)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="font-body text-[14px] leading-relaxed text-text-muted">
              No key points for this item.
            </p>
          )}

          <div className="mt-8 space-y-4 font-body text-[16px] leading-[1.65] text-text-secondary">
            {item.analysis?.trim() ? (
              renderAnalysisBlock(item.analysis)
            ) : (
              detailArticleParagraphs(item, lines).map((para, i) => (
                <p key={i}>{renderMarkdown(para)}</p>
              ))
            )}
          </div>

          {item.is_model_release && item.model_release_data ? (
            <div className="mt-10">
              <p className="font-mono text-[14px] uppercase tracking-[0.1em] text-text-muted">
                Model release
              </p>
              <p className="mt-2 font-display text-[17px] font-normal text-text-primary">
                {item.model_release_data.model_name}
              </p>
              {item.model_release_data.summary_pitch ? (
                <p className="mt-2 font-body text-[16px] leading-[1.65] text-text-secondary">
                  {item.model_release_data.summary_pitch}
                </p>
              ) : null}
              {item.model_release_data.availability ? (
                <p className="mt-2 font-mono text-[14px] text-text-muted">
                  {item.model_release_data.availability}
                </p>
              ) : null}
            </div>
          ) : null}

          {item.exhibits?.length ? (
            <div className="mt-8 space-y-4">
              {item.exhibits.map((exhibit, i) => (
                <ExhibitRenderer key={`exhibit-${i}`} exhibit={exhibit} />
              ))}
            </div>
          ) : null}

          <div className="mt-10">
            {item.source_url ? (
              <a
                href={item.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex min-h-[40px] max-w-full items-center gap-2 rounded-xl py-1 transition-opacity hover:opacity-90"
              >
                <span className="relative flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full border border-rule-light bg-bg-surface-2">
                  <Image
                    src={sourceLogoSrc}
                    alt=""
                    width={32}
                    height={32}
                    className="h-[70%] w-[70%] object-contain"
                    unoptimized
                    onError={() => {
                      setLogoIndex((current) =>
                        current < logoCandidates.length - 1 ? current + 1 : current
                      );
                    }}
                  />
                </span>
                <span className="min-w-0 truncate font-ui text-[15px] font-medium text-text-primary">
                  {item.source_name}
                </span>
              </a>
            ) : (
              <div className="flex min-h-[40px] items-center gap-2">
                <span className="relative flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full border border-rule-light bg-bg-surface-2">
                  <Image
                    src={sourceLogoSrc}
                    alt=""
                    width={32}
                    height={32}
                    className="h-[70%] w-[70%] object-contain"
                    unoptimized
                    onError={() => {
                      setLogoIndex((current) =>
                        current < logoCandidates.length - 1 ? current + 1 : current
                      );
                    }}
                  />
                </span>
                <span className="truncate font-ui text-[15px] font-medium text-text-primary">
                  {item.source_name}
                </span>
              </div>
            )}
          </div>

          {item.additional_sources.length > 0 ? (
            <div className="mt-6 flex flex-wrap gap-x-4 gap-y-2">
              {item.additional_sources.map((s) => (
                <a
                  key={s.url}
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-[14px] text-text-muted underline-offset-2 hover:text-accent hover:underline"
                >
                  {s.name}
                </a>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <button
        type="button"
        className={cn(
          NOTE_FAB_BTN,
          "bottom-[max(16px,env(safe-area-inset-bottom,0px))] right-6 lg:right-8",
          noteFabVisible
            ? "pointer-events-auto scale-100 opacity-100"
            : "pointer-events-none scale-[0.92] opacity-0"
        )}
        data-visible={noteFabVisible ? "true" : "false"}
        onClick={() => setNoteSheetOpen(true)}
        aria-label={hasStoredNote ? "Article notes" : "Add note"}
      >
        <NotebookPen className="h-5 w-5" strokeWidth={2} aria-hidden />
      </button>

      <BriefComposerSheet
        open={noteSheetOpen}
        onOpenChange={setNoteSheetOpen}
        overlayClassName="fixed inset-0 z-[60] bg-black/30"
        contentClassName={BRIEF_COMPOSER_SHEET_CONTENT_NOTE}
        title="Note"
        headerTrailing={
          <button
            type="button"
            onClick={saveNoteFromSheet}
            disabled={!canSaveNote || noteSaveBusy}
            className="shrink-0 rounded-[10px] px-3 py-1 font-ui text-[14px] font-semibold leading-snug text-accent transition-colors hover:bg-accent/8 disabled:pointer-events-none disabled:opacity-35"
          >
            Save
          </button>
        }
      >
        <AnnotationInput
          variant="noteSheet"
          value={sheetDraft}
          onChange={setSheetDraft}
        />
      </BriefComposerSheet>

      {noteSaveToast ? (
        <div
          role="status"
          aria-live="polite"
          className={cn(
            "pointer-events-none fixed left-1/2 z-[70] max-w-[min(420px,calc(100vw-32px))] -translate-x-1/2 rounded-[12px] border px-4 py-3 font-ui text-[14px] leading-snug shadow-lg",
            noteSaveToast.tone === "success"
              ? "border-rule-light bg-bg-surface text-text-primary"
              : "border-accent/35 bg-bg-surface text-accent"
          )}
          style={{
            top: "max(16px, calc(env(safe-area-inset-top, 0px) + 12px))",
          }}
        >
          {noteSaveToast.text}
        </div>
      ) : null}
    </div>
  );
}
