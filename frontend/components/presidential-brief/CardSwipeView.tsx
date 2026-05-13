"use client";

import {
  useState,
  useEffect,
  useLayoutEffect,
  useCallback,
  useMemo,
  useRef,
} from "react";
import { useRouter } from "next/navigation";
import type {
  Brief,
  BriefItem,
  FeedCard,
  Annotation,
  ResearchRequest,
} from "@/lib/types/brief";
import type { AudioPlayerState, AudioPlayerActions } from "@/lib/presidential-brief/hooks/useAudioPlayer";
import { useAudioCardSync } from "@/lib/presidential-brief/hooks/useAudioCardSync";
import { CardTopChrome, type BriefChromeViewMode } from "./CardHeader";
import BriefSummaryListView from "./BriefSummaryListView";
import CardVerticalSnapDeck, {
  type CardVerticalSnapDeckHandle,
} from "./CardVerticalSnapDeck";
import AnnotationInput from "./AnnotationInput";
import BriefComposerSheet, {
  BRIEF_COMPOSER_SHEET_CONTENT_FOLLOWUP,
} from "./BriefComposerSheet";
import CardSwipeActionRail from "./CardSwipeActionRail";
import StoryCard from "./StoryCard";
import DividerCard from "./DividerCard";
import CardSwipeToFlag from "./CardSwipeToFlag";
import StoryDetailExpansionOverlay from "./StoryDetailExpansionOverlay";
import ContextMenu from "./ContextMenu";
import CalendarPicker from "./CalendarPicker";
import DaySwipeContainer from "./DaySwipeContainer";
import { hapticImpact } from "@/lib/presidential-brief/haptics";
import { BRIEF_PINNED_PLAYER_RESERVE_BOTTOM_CLASS } from "@/lib/presidential-brief/briefPinnedPlayerInset";
import { cn } from "@/lib/utils";

const CALENDAR_SHEET_EASE = "cubic-bezier(0.22,1,0.36,1)";
const CALENDAR_SHEET_MS = 280;

interface CardSwipeViewProps {
  brief: Brief;
  /** Single deck: briefing stories then follow-up request cards, then end. */
  feed: FeedCard[];
  flaggedItems: Set<string>;
  toggleFlag: (itemId: string) => void;
  annotationState: {
    getForItem: (itemId: string) => Annotation[];
    addAnnotation: (itemId: string, briefDate: string, text: string) => void;
    updateAnnotation: (id: string, text: string) => void;
    deleteAnnotation: (id: string) => void;
    getCount: () => number;
    getStorySheetDraft: (itemId: string) => string;
    saveStorySheetNote: (itemId: string, briefDate: string, text: string) => void;
  };
  researchRequestState: {
    requests: ResearchRequest[];
    isLoading: boolean;
    submitRequest: (itemId: string, requestNote?: string) => Promise<void>;
    getRequestForItem: (itemId: string) => ResearchRequest | undefined;
    hasPendingRequest: (itemId: string) => boolean;
  };
  player: AudioPlayerState & AudioPlayerActions;
  prevDate: string | null;
  nextDate: string | null;
  availableDates: string[];
  /** When true, reserve space for fixed bottom pinned audio bar */
  hasPinnedAudioBar?: boolean;
  /** Open the story detail overlay for this item id (e.g. from full-screen audio transcript). */
  openStoryDetailItemId?: string | null;
  /** Called after the open request is applied so the parent can clear `openStoryDetailItemId`. */
  /** Pass `false` when the story drawer did not open (e.g. missing card). */
  onOpenStoryDetailRequestHandled?: (didOpenDrawer: boolean) => void;
  /** When the detail overlay was opened from full-screen audio, closing it runs this (e.g. reopen audio). */
  onStoryDetailDismissResumeAudio?: () => void;
  /** Navigate to the language learning page for a specific item. Receives (itemId, currentActiveIndex). */
  onNavigateToLearn?: (itemId: string, activeIndex: number) => void;
  /** Initial slide index from URL param (restores position when returning from learning page). */
  initialSlideIndex?: number;
}

export default function CardSwipeView({
  brief,
  feed,
  flaggedItems,
  toggleFlag,
  annotationState,
  researchRequestState,
  player,
  prevDate,
  nextDate,
  availableDates,
  hasPinnedAudioBar = false,
  openStoryDetailItemId = null,
  onOpenStoryDetailRequestHandled,
  onStoryDetailDismissResumeAudio,
  onNavigateToLearn,
  initialSlideIndex,
}: CardSwipeViewProps) {
  const router = useRouter();
  const [briefViewMode, setBriefViewMode] = useState<BriefChromeViewMode>("cards");
  /** List view: story index from scroll (cards view uses `activeStoryProgressIndex`). */
  const [listProgressStoryIndex, setListProgressStoryIndex] = useState(0);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [calendarMounted, setCalendarMounted] = useState(false);
  const [calendarPresent, setCalendarPresent] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const deckRef = useRef<CardVerticalSnapDeckHandle>(null);
  /** Next programmatic deck scroll from audio: "auto" once after List→Cards to avoid slide animation */
  const deckProgrammaticScrollBehaviorRef = useRef<ScrollBehavior>("smooth");
  const pendingListToCardsDeckSnapRef = useRef(false);
  const resumeAudioAfterDetailDismissRef = useRef(false);

  const storyProgressTotal = useMemo(
    () => feed.filter((c) => c.type === "story").length,
    [feed]
  );

  /** Briefing-only stories (excludes follow-up queue cards) — aligns with `audio_segments`. */
  const audioAlignedStoryCount = useMemo(
    () =>
      feed.filter((c) => c.type === "story" && !c.followUp).length,
    [feed]
  );
  /** Per-item audio: item IDs in story-card order for cards that have audio_url. */
  const itemAudioIds = useMemo(
    () =>
      feed
        .filter(
          (c): c is Extract<FeedCard, { type: "story" }> =>
            c.type === "story" && !c.followUp && Boolean(c.item.audio_url),
        )
        .map((c) => c.item.id),
    [feed],
  );
  const [feedbackDrawerOpen, setFeedbackDrawerOpen] = useState(false);
  const [followUpToast, setFollowUpToast] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);
  const [drawerItem, setDrawerItem] = useState<BriefItem | null>(null);
  const [detailOriginRect, setDetailOriginRect] = useState<DOMRect | null>(
    null
  );
  const [contextItem, setContextItem] = useState<BriefItem | null>(null);


  const navigateToBrief = useCallback(
    async (date: string) => {
      await hapticImpact("light");
      router.push(`/brief/${date}`);
    },
    [router]
  );

  const setBriefViewModeWithHaptic = useCallback(
    (mode: BriefChromeViewMode) => {
      void hapticImpact("light");
      if (mode === "cards" && briefViewMode === "list") {
        setActiveIndex(0);
        deckProgrammaticScrollBehaviorRef.current = "auto";
        pendingListToCardsDeckSnapRef.current = true;
      }
      setBriefViewMode(mode);
    },
    [briefViewMode]
  );

  // Build feed index ↔ story index mappings
  const feedToStory = useMemo(() => {
    const f2s = new Map<number, number>();
    let storyIdx = 0;
    for (let i = 0; i < feed.length; i++) {
      if (feed[i].type === "story") {
        f2s.set(i, storyIdx);
        storyIdx++;
      }
    }
    return f2s;
  }, [feed]);

  const activeStoryProgressIndex = useMemo(() => {
    const c = feed[activeIndex];
    if (c?.type === "end") return Math.max(0, storyProgressTotal - 1);
    let idx = 0;
    for (let i = 0; i <= activeIndex; i++) {
      const card = feed[i];
      if (card?.type === "story") {
        if (i === activeIndex) return idx;
        idx++;
      }
    }
    return 0;
  }, [feed, activeIndex, storyProgressTotal]);

  const handleListScrollStoryIndex = useCallback(
    (idx: number) => {
      const max = Math.max(0, storyProgressTotal - 1);
      const next = Math.min(Math.max(0, idx), max);
      setListProgressStoryIndex((prev) => (prev === next ? prev : next));
    },
    [storyProgressTotal]
  );

  const briefViewModePrevRef = useRef<BriefChromeViewMode>(briefViewMode);
  useLayoutEffect(() => {
    if (
      briefViewMode === "list" &&
      briefViewModePrevRef.current !== "list"
    ) {
      const max = Math.max(0, storyProgressTotal - 1);
      setListProgressStoryIndex(
        Math.min(Math.max(0, activeStoryProgressIndex), max)
      );
    }
    briefViewModePrevRef.current = briefViewMode;
  }, [
    briefViewMode,
    activeStoryProgressIndex,
    storyProgressTotal,
  ]);

  const handleActiveIndexChange = useCallback(
    (next: number) => {
      const maxIdx = Math.max(0, feed.length - 1);
      setActiveIndex(Math.min(Math.max(0, next), maxIdx));
    },
    [feed.length]
  );

  const setActiveCardIndexFromAudio = useCallback(
    (next: number) => {
      handleActiveIndexChange(next);
      const behavior = deckProgrammaticScrollBehaviorRef.current;
      if (behavior === "auto") {
        deckProgrammaticScrollBehaviorRef.current = "smooth";
      }
      queueMicrotask(() => {
        deckRef.current?.scrollToSlide(next, behavior);
      });
    },
    [handleActiveIndexChange]
  );

  useLayoutEffect(() => {
    if (briefViewMode !== "cards" || !pendingListToCardsDeckSnapRef.current) {
      return;
    }
    pendingListToCardsDeckSnapRef.current = false;
    deckRef.current?.scrollToSlide(activeIndex, "auto");
    requestAnimationFrame(() => {
      if (deckProgrammaticScrollBehaviorRef.current === "auto") {
        deckProgrammaticScrollBehaviorRef.current = "smooth";
      }
    });
  }, [briefViewMode, activeIndex]);

  const audioFeedIndexToStoryIndex = useCallback(
    (feedIdx: number) => {
      let idx = 0;
      for (let i = 0; i < feed.length; i++) {
        const c = feed[i];
        if (c?.type === "story" && !c.followUp) {
          if (i === feedIdx) return idx;
          idx++;
        }
      }
      return -1;
    },
    [feed]
  );

  const audioStoryIndexToFeedIndex = useCallback(
    (storyIdx: number) => {
      let idx = 0;
      for (let i = 0; i < feed.length; i++) {
        const c = feed[i];
        if (c?.type === "story" && !c.followUp) {
          if (idx === storyIdx) return i;
          idx++;
        }
      }
      return -1;
    },
    [feed]
  );

  useAudioCardSync({
    player,
    segments: brief.audio_segments,
    activeCardIndex: activeIndex,
    setActiveCardIndex: setActiveCardIndexFromAudio,
    feedIndexToStoryIndex: audioFeedIndexToStoryIndex,
    storyIndexToFeedIndex: audioStoryIndexToFeedIndex,
    totalStoryCards: audioAlignedStoryCount,
    itemAudioIds,
  });

  /* eslint-disable react-hooks/set-state-in-effect -- clamp index when feed length changes */
  useEffect(() => {
    setActiveIndex((i) =>
      Math.min(Math.max(0, i), Math.max(0, feed.length - 1))
    );
  }, [feed.length]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Restore slide position when returning from learning page
  /* eslint-disable react-hooks/set-state-in-effect -- intentionally read from URL param once on mount */
  useEffect(() => {
    if (initialSlideIndex !== undefined && initialSlideIndex >= 0) {
      const maxIdx = Math.max(0, feed.length - 1);
      const clamped = Math.min(initialSlideIndex, maxIdx);
      setActiveIndex(clamped);
      queueMicrotask(() => {
        deckRef.current?.scrollToSlide(clamped, "auto");
      });
    }
  }, []); // Only on mount — feed.length may not be ready here, but clamping handles it
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (!followUpToast) return;
    const id = window.setTimeout(() => setFollowUpToast(null), 3200);
    return () => window.clearTimeout(id);
  }, [followUpToast]);

  /* eslint-disable react-hooks/set-state-in-effect -- calendar overlay mount / present for enter-exit transitions */
  useEffect(() => {
    if (calendarOpen) {
      setCalendarMounted(true);
      const id = requestAnimationFrame(() => {
        requestAnimationFrame(() => setCalendarPresent(true));
      });
      return () => cancelAnimationFrame(id);
    }
    setCalendarPresent(false);
  }, [calendarOpen]);

  useEffect(() => {
    if (!calendarOpen && calendarMounted) {
      if (
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        setCalendarMounted(false);
      }
    }
  }, [calendarOpen, calendarMounted]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleCalendarSheetTransitionEnd = (
    e: React.TransitionEvent<HTMLDivElement>
  ) => {
    if (e.target !== e.currentTarget) return;
    if (calendarOpen) return;
    if (
      e.propertyName === "opacity" ||
      e.propertyName === "transform"
    ) {
      setCalendarMounted(false);
    }
  };

  const openDrawer = useCallback(
    (
      item: BriefItem,
      originRect: DOMRect,
      options?: { resumeAudioOnClose?: boolean }
    ) => {
      resumeAudioAfterDetailDismissRef.current = Boolean(
        options?.resumeAudioOnClose
      );
      setDetailOriginRect(
        new DOMRect(originRect.x, originRect.y, originRect.width, originRect.height)
      );
      setDrawerItem(item);
    },
    []
  );
  const closeDrawer = useCallback(() => {
    setDrawerItem(null);
    setDetailOriginRect(null);
    if (resumeAudioAfterDetailDismissRef.current) {
      resumeAudioAfterDetailDismissRef.current = false;
      onStoryDetailDismissResumeAudio?.();
    }
  }, [onStoryDetailDismissResumeAudio]);

  /* Open drawer from audio transcript: parent lifts id; we resolve it to a feed card here. */
  /* eslint-disable react-hooks/set-state-in-effect -- intentional handoff from sibling overlay (audio) into drawer state */
  useEffect(() => {
    if (!openStoryDetailItemId || !onOpenStoryDetailRequestHandled) return;
    const storyCard = feed.find(
      (c): c is Extract<FeedCard, { type: "story" }> =>
        c.type === "story" && c.item.id === openStoryDetailItemId
    );
    let didOpen = false;
    if (storyCard && typeof window !== "undefined") {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const size = 64;
      const originRect = new DOMRect(
        (vw - size) / 2,
        (vh - size) / 2,
        size,
        size
      );
      openDrawer(storyCard.item, originRect, { resumeAudioOnClose: true });
      didOpen = true;
    }
    onOpenStoryDetailRequestHandled(didOpen);
  }, [
    openStoryDetailItemId,
    feed,
    onOpenStoryDetailRequestHandled,
    openDrawer,
  ]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return (
    <DaySwipeContainer prevDate={prevDate} nextDate={nextDate}>
      <div
        className={`flex min-h-0 flex-1 flex-col overflow-visible bg-bg-primary ${hasPinnedAudioBar ? BRIEF_PINNED_PLAYER_RESERVE_BOTTOM_CLASS : ""}`}
      >
        <CardTopChrome
          briefDate={brief.brief_date}
          storyProgressIndex={
            briefViewMode === "list"
              ? listProgressStoryIndex
              : activeStoryProgressIndex
          }
          storyProgressTotal={storyProgressTotal}
          onDateOpenCalendar={() => setCalendarOpen((o) => !o)}
          calendarOpen={calendarOpen}
          viewMode={briefViewMode}
          onViewModeChange={setBriefViewModeWithHaptic}
        />

        {calendarMounted && (
          <>
            <button
              type="button"
              className={cn(
                "fixed inset-0 z-[55] bg-black/25 transition-opacity motion-reduce:transition-none",
                calendarPresent
                  ? "pointer-events-auto opacity-100"
                  : "pointer-events-none opacity-0"
              )}
              style={{
                transitionDuration: `${CALENDAR_SHEET_MS}ms`,
                transitionTimingFunction: CALENDAR_SHEET_EASE,
              }}
              aria-label="Close calendar"
              onClick={() => setCalendarOpen(false)}
            />
            {/* Top = safe area + CardTopChrome progress + date row. Sync with CardHeader.tsx. */}
            <div
              className={cn(
                "fixed left-4 right-4 z-[56] max-h-[min(72dvh,560px)] origin-top overflow-y-auto rounded-2xl border border-rule-light bg-bg-surface px-4 pb-4 pt-3 shadow-lg transition-[opacity,transform] motion-reduce:transition-none top-[calc(env(safe-area-inset-top,0px)+54px)] sm:top-[calc(env(safe-area-inset-top,0px)+62px)]",
                calendarPresent
                  ? "pointer-events-auto translate-y-0 scale-100 opacity-100"
                  : "pointer-events-none -translate-y-2 scale-[0.97] opacity-0"
              )}
              style={{
                transitionDuration: `${CALENDAR_SHEET_MS}ms`,
                transitionTimingFunction: CALENDAR_SHEET_EASE,
              }}
              role="dialog"
              aria-label="Brief calendar"
              onTransitionEnd={handleCalendarSheetTransitionEnd}
            >
              <CalendarPicker
                placement="sheet"
                visible={true}
                currentDate={brief.brief_date}
                availableDates={availableDates}
                onSelectDate={(date) => {
                  void navigateToBrief(date);
                  setCalendarOpen(false);
                }}
                onClose={() => setCalendarOpen(false)}
              />
            </div>
          </>
        )}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col basis-0 overflow-visible">
          <div
            key={briefViewMode}
            data-brief-view={briefViewMode}
            className="brief-view-mode-enter flex min-h-0 min-w-0 flex-1 flex-col overflow-visible"
          >
          {briefViewMode === "list" ? (
            <BriefSummaryListView
              feed={feed}
              flaggedItems={flaggedItems}
              onListScrollStoryIndexChange={handleListScrollStoryIndex}
              onStoryActivate={(card, originRect) => {
                if (card.followUp) {
                  const allItems = brief.sections.flatMap((s) => s.items);
                  const originalItem = allItems.find(
                    (i) => i.id === card.followUp!.original_item_id
                  );
                  openDrawer(originalItem ?? card.item, originRect);
                } else {
                  openDrawer(card.item, originRect);
                }
              }}
            />
          ) : (
          <CardVerticalSnapDeck
            ref={deckRef}
            slideCount={feed.length}
            activeIndex={activeIndex}
            onActiveIndexChange={handleActiveIndexChange}
            renderSlide={(index) => {
              const card = feed[index];
              if (!card) return null;

              if (card.type === "story") {
                const storyIdx = feedToStory.get(index) ?? 0;
                const isActiveStory = index === activeIndex;
                return (
                  <div className="flex h-full min-h-0 w-full flex-1 flex-col bg-transparent">
                    <CardSwipeToFlag
                      isFlagged={flaggedItems.has(card.item.id)}
                      onFlag={() => {
                        toggleFlag(card.item.id);
                      }}
                      onUnflag={() => toggleFlag(card.item.id)}
                      onLongPress={() => {
                        hapticImpact("heavy");
                        setContextItem(card.item);
                      }}
                    >
                      <div className="relative flex h-full min-h-0 flex-1 flex-col overflow-visible">
                        <StoryCard
                          item={card.item}
                          followUp={card.followUp}
                          isFlagged={flaggedItems.has(card.item.id)}
                          onTap={(originRect) => {
                            if (card.followUp) {
                              const allItems = brief.sections.flatMap((s) => s.items);
                              const originalItem = allItems.find(
                                (i) => i.id === card.followUp!.original_item_id
                              );
                              openDrawer(originalItem ?? card.item, originRect);
                            } else {
                              openDrawer(card.item, originRect);
                            }
                          }}
                          actionRail={
                            isActiveStory ? (
                              <CardSwipeActionRail
                                embedded
                                canAct={isActiveStory}
                                onRequestResearch={() =>
                                  setFeedbackDrawerOpen(true)
                                }
                                onOpenLearn={
                                  onNavigateToLearn
                                    ? () => onNavigateToLearn(card.item.id, activeIndex)
                                    : undefined
                                }
                                hasLearningContent={
                                  Boolean(card.item.learning_fr) ||
                                  Boolean(card.item.learning_ar)
                                }
                              />
                            ) : undefined
                          }
                        />
                      </div>
                    </CardSwipeToFlag>
                  </div>
                );
              }

              if (card.type === "divider") {
                return (
                  <div className="flex h-full min-h-0 w-full flex-1 flex-col bg-transparent">
                    <DividerCard label={card.label} kind={card.kind} />
                  </div>
                );
              }

              if (card.type === "end") {
                return (
                  <div className="flex h-full min-h-0 w-full flex-1 flex-col items-center justify-center bg-transparent px-6">
                    <div className="text-center">
                      <p className="font-display text-[22px] text-text-primary">
                        You&apos;re caught up.
                      </p>
                      <p className="mt-3 font-body text-[12px] text-text-muted">
                        {card.itemsReviewed}{" "}
                        {card.itemsReviewed === 1 ? "card" : "cards"} reviewed
                        {flaggedItems.size > 0 && ` · ${flaggedItems.size} flagged`}
                      </p>
                    </div>
                  </div>
                );
              }

              return null;
            }}
          />
          )}
          </div>
        </div>

      {/* Context menu */}
      {contextItem && (
        <ContextMenu
          visible={true}
          onClose={() => setContextItem(null)}
          onFlag={() => {
            toggleFlag(contextItem.id);
            setContextItem(null);
          }}
          onOpenSource={() => {
            if (contextItem.source_url)
              window.open(contextItem.source_url, "_blank", "noopener,noreferrer");
            setContextItem(null);
          }}
          onCopyHeadline={() => {
            navigator.clipboard.writeText(contextItem.headline).catch(() => {});
            setContextItem(null);
          }}
          isFlagged={flaggedItems.has(contextItem.id)}
          headline={contextItem.headline}
          sourceUrl={contextItem.source_url}
        />
      )}

      <BriefComposerSheet
        open={feedbackDrawerOpen}
        onOpenChange={setFeedbackDrawerOpen}
        overlayClassName="fixed inset-0 z-[55] bg-black/30"
        contentClassName={BRIEF_COMPOSER_SHEET_CONTENT_FOLLOWUP}
        title="Request research"
      >
        <AnnotationInput
          variant="followup"
          onSubmit={async (text) => {
            const card = feed[activeIndex];
            try {
              if (card?.type === "story") {
                await researchRequestState.submitRequest(
                  card.item.id,
                  text
                );
                setFeedbackDrawerOpen(false);
                setFollowUpToast({
                  tone: "success",
                  text: "Research request sent.",
                });
              } else {
                setFollowUpToast({
                  tone: "error",
                  text: "Couldn’t send your request. Try again.",
                });
              }
            } catch {
              setFollowUpToast({
                tone: "error",
                text: "Couldn’t send your request. Try again.",
              });
            }
          }}
        />
      </BriefComposerSheet>

      {drawerItem && detailOriginRect ? (
        <StoryDetailExpansionOverlay
          key={drawerItem.id}
          item={drawerItem}
          originRect={detailOriginRect}
          isFlagged={flaggedItems.has(drawerItem.id)}
          onDismiss={closeDrawer}
          getStorySheetNoteText={() =>
            annotationState.getStorySheetDraft(drawerItem.id)
          }
          onSaveStorySheetNote={(text) =>
            annotationState.saveStorySheetNote(
              drawerItem.id,
              brief.brief_date,
              text
            )
          }
        />
      ) : null}

      {followUpToast && (
        <div
          role="status"
          aria-live="polite"
          className={cn(
            "pointer-events-none fixed left-1/2 z-[60] max-w-[min(420px,calc(100vw-32px))] -translate-x-1/2 rounded-[12px] border px-4 py-3 font-ui text-[14px] leading-snug shadow-lg",
            followUpToast.tone === "success"
              ? "border-rule-light bg-bg-surface text-text-primary"
              : "border-accent/35 bg-bg-surface text-accent"
          )}
          style={{
            top: "max(16px, calc(env(safe-area-inset-top, 0px) + 12px))",
          }}
        >
          {followUpToast.text}
        </div>
      )}
      </div>
    </DaySwipeContainer>
  );
}
