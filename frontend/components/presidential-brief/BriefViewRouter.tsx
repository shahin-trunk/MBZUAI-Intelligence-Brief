"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import type { Brief } from "@/lib/types/brief";
import { useAudioPlayer } from "@/lib/presidential-brief/hooks/useAudioPlayer";
import { buildFeed } from "@/lib/presidential-brief/buildFeed";
import { useBriefAnnotations } from "@/lib/presidential-brief/hooks/useBriefAnnotations";
import { useBriefFlags } from "@/lib/presidential-brief/hooks/useBriefFlags";
import { useResearchRequests } from "@/lib/hooks/useResearchRequests";
import AudioFullScreen from "./AudioFullScreen";
import BriefingPinnedPlayer from "./BriefingPinnedPlayer";
import CardSwipeView from "./CardSwipeView";

interface BriefViewRouterProps {
  brief: Brief;
  prevDate: string | null;
  nextDate: string | null;
  availableDates: string[];
  /** Initial slide index from URL (restores position when returning from learning page). */
  slideIndex?: number;
}

export default function BriefViewRouter({
  brief,
  prevDate,
  nextDate,
  availableDates,
  slideIndex,
}: BriefViewRouterProps) {
  const router = useRouter();
  const [audioExpanded, setAudioExpanded] = useState(false);
  const [openStoryDetailFromAudioId, setOpenStoryDetailFromAudioId] = useState<
    string | null
  >(null);
  const [audioBehindStoryDetail, setAudioBehindStoryDetail] = useState(false);
  const { flaggedItems, toggleFlag } = useBriefFlags(brief.brief_date);
  const annotationState = useBriefAnnotations(brief.brief_date);
  const researchRequestState = useResearchRequests(brief.brief_date);

  const clearOpenStoryDetailFromAudio = useCallback((didOpenDrawer: boolean) => {
    setOpenStoryDetailFromAudioId(null);
    if (!didOpenDrawer) {
      setAudioBehindStoryDetail(false);
    }
  }, []);

  const resumeAudioAfterStoryDetail = useCallback(() => {
    setAudioBehindStoryDetail(false);
  }, []);

  const hasAudio = Boolean(
    brief.audio_url ||
    brief.audio_url_fr ||
    brief.items.some((item) => item.audio_url)
  );
  const player = useAudioPlayer(brief.audio_url, brief.audio_url_fr);

  // Build per-item audio URL map from brief items
  const itemUrlMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const item of brief.items) {
      if (item.audio_url) {
        map[item.id] = item.audio_url;
      }
    }
    return map;
  }, [brief.items]);

  // Register per-item audio URLs with the player
  useEffect(() => {
    player.setItemAudioUrls(itemUrlMap);
  }, [player, itemUrlMap]);

  const feed = useMemo(() => {
    return buildFeed(brief, null, []);
  }, [brief]);

  // Navigate to language learning page for a specific slide item
  const handleNavigateToLearn = useCallback(
    (itemId: string, activeIndex: number) => {
      router.push(
        `/brief/${brief.brief_date}/learn/${itemId}?slideIndex=${activeIndex}`
      );
    },
    [router, brief.brief_date]
  );

  return (
    <>
      <CardSwipeView
        brief={brief}
        feed={feed}
        flaggedItems={flaggedItems}
        toggleFlag={(itemId) => {
          void toggleFlag(itemId);
        }}
        annotationState={annotationState}
        researchRequestState={researchRequestState}
        player={player}
        prevDate={prevDate}
        nextDate={nextDate}
        availableDates={availableDates}
        hasPinnedAudioBar={hasAudio}
        openStoryDetailItemId={openStoryDetailFromAudioId}
        onOpenStoryDetailRequestHandled={clearOpenStoryDetailFromAudio}
        onStoryDetailDismissResumeAudio={resumeAudioAfterStoryDetail}
        onNavigateToLearn={handleNavigateToLearn}
        initialSlideIndex={slideIndex}
      />

      {hasAudio && (
        <BriefingPinnedPlayer
          player={player}
          briefDate={brief.brief_date}
          onOpenFullScreen={() => setAudioExpanded(true)}
        />
      )}

      {audioExpanded && (
        <AudioFullScreen
          player={player}
          briefDate={brief.brief_date}
          transcript={brief.audio_script}
          transcriptFr={brief.audio_script_fr}
          onClose={() => {
            setAudioExpanded(false);
            setAudioBehindStoryDetail(false);
          }}
          linkedStoryIds={brief.sections.flatMap((s) => s.items).map((item) => item.id)}
          behindStoryDetail={audioBehindStoryDetail}
          onOpenStoryDetail={(itemId) => {
            setOpenStoryDetailFromAudioId(itemId);
            setAudioBehindStoryDetail(true);
          }}
        />
      )}
    </>
  );
}