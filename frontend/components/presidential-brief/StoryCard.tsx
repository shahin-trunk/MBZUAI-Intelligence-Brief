"use client";

import Image from "next/image";
import { useState, useEffect, useRef, type ReactNode } from "react";
import type { BriefItem, FollowUpItem } from "@/lib/types/brief";
import { BRIEF_STORY_CARD_MAX_WIDTH_CLASS } from "@/lib/presidential-brief/briefCardLayout";
import { renderMarkdown } from "@/lib/rendering/markdown";
import { useEntityLogos } from "@/lib/hooks/useEntityLogos";
import { CountryFlag } from "@/components/common/CountryFlag";
import {
  entityLogoLookupNames,
  resolveEntityBadge,
} from "@/lib/entity-badge";
import { formatSectionTagLabel } from "@/lib/utils";
import { sectionTagPaletteClasses } from "@/lib/presidential-brief/sectionTagPalette";
import {
  bulletLinesFromMainBullet,
  heroImageUrlForItem,
} from "@/lib/presidential-brief/storyCardPlaceholders";

const MAX_BULLETS = 3;

function formatBriefDateLabel(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return d.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

interface StoryCardProps {
  item: BriefItem;
  isFlagged: boolean;
  /** Called with the card shell bounds (for expand-from-card transitions). */
  onTap: (originRect: DOMRect) => void;
  /** When set, card is a follow-up update (same layout as a story). */
  followUp?: FollowUpItem;
  /** Optional footer inside the white card (e.g. swipe action rail). */
  actionRail?: ReactNode;
}

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

export default function StoryCard({
  item,
  isFlagged,
  onTap,
  followUp,
  actionRail,
}: StoryCardProps) {
  const heroSrc = heroImageUrlForItem(item);
  const { resolve: resolveEntityLogo } = useEntityLogos();
  const entityLogo =
    entityLogoLookupNames(item).map(resolveEntityLogo).find(Boolean) ?? null;
  const [imgFailed, setImgFailed] = useState(false);
  const [logoImgFailed, setLogoImgFailed] = useState(false);
  const badge = resolveEntityBadge(item, {
    entityLogo: logoImgFailed ? null : entityLogo,
  });
  const bullets = (
    item.key_bullets?.filter((line) => line.trim().length > 0) ??
    bulletLinesFromMainBullet(item.main_bullet, MAX_BULLETS)
  ).slice(0, MAX_BULLETS);

  /* eslint-disable react-hooks/set-state-in-effect -- reset image error when hero URL changes */
  useEffect(() => {
    setImgFailed(false);
  }, [heroSrc]);

  useEffect(() => {
    setLogoImgFailed(false);
  }, [entityLogo?.logoUrl]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const showImage = heroSrc && !imgFailed;
  const cardShellRef = useRef<HTMLDivElement>(null);

  const emitTap = () => {
    const el = cardShellRef.current;
    if (el) onTap(el.getBoundingClientRect());
  };

  return (
    <div className="flex h-full min-h-0 w-full flex-1 flex-col items-stretch py-3 sm:py-4">
      <div
        ref={cardShellRef}
        className={`flex h-full min-h-0 w-full flex-1 cursor-default flex-col overflow-visible rounded-2xl border border-rule bg-bg-surface ${BRIEF_STORY_CARD_MAX_WIDTH_CLASS}`}
      >
        <div
          role="button"
          tabIndex={0}
          onClick={() => emitTap()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              emitTap();
            }
          }}
          className="flex min-h-0 flex-1 cursor-pointer flex-col overflow-visible outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-surface"
        >
          {/* Rounded clip only on hero so deck rotation doesn’t clip the whole card */}
          <div className="relative h-[min(10.5rem,26dvh)] w-full shrink-0 overflow-hidden rounded-t-2xl bg-bg-surface-2 sm:h-[min(11.5rem,28dvh)] md:h-[min(12rem,30dvh)]">
            {showImage ? (
              <Image
                src={heroSrc}
                alt={item.headline}
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
              className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/25 to-black/10"
              aria-hidden="true"
            />

            <div
              className="absolute right-3 top-3 flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-white/90 bg-white/95 shadow-md ring-1 ring-black/5 backdrop-blur-sm dark:border-white/35 dark:bg-bg-surface/95 dark:ring-white/10 sm:h-11 sm:w-11"
              aria-hidden="true"
            >
              {badge.kind === "logo" ? (
                <Image
                  src={badge.logoUrl}
                  alt={badge.label ?? item.source_name ?? ""}
                  width={44}
                  height={44}
                  className="h-[72%] w-[72%] object-contain"
                  unoptimized
                  onError={() => setLogoImgFailed(true)}
                />
              ) : badge.kind === "flag" ? (
                <CountryFlag
                  code={badge.countryCode}
                  className="h-full w-full"
                  ariaLabel={badge.label ?? badge.countryCode.toUpperCase()}
                />
              ) : (
                <badge.Icon
                  size={22}
                  strokeWidth={1.75}
                  className="h-[72%] w-[72%] text-text-muted"
                  aria-hidden="true"
                />
              )}
            </div>

            <div className="absolute bottom-0 left-0 right-0 p-2.5 pt-5 pb-5 text-left sm:p-3 sm:pt-6 sm:pb-5">
              {item.section?.trim() ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex max-w-full items-center rounded-full px-2.5 py-0.5 font-ui text-[12px] font-semibold sm:text-[13px] ${sectionTagPaletteClasses(item.section.trim())}`}
                  >
                    {formatSectionTagLabel(item.section)}
                  </span>
                </div>
              ) : null}
              <h2
                className={`${item.section?.trim() ? "mt-2" : "mt-1"} line-clamp-3 font-display text-[20px] font-normal leading-[1.2] text-white sm:text-[21px] lg:text-[22px]`}
              >
                {item.headline}
                {isFlagged && (
                  <span className="ml-2 text-amber-300" aria-label="Flagged">
                    ⚑
                  </span>
                )}
              </h2>
            </div>
          </div>

          <div
            data-brief-story-scroll
            className={`flex min-h-0 flex-1 touch-pan-y flex-col overflow-y-auto px-4 pt-4 text-left ${actionRail ? "pb-2" : "rounded-b-2xl pb-5"}`}
          >
            {followUp ? (
              <div className="mb-6 pb-1 sm:mb-8 sm:pb-2">
                <p className="mb-1.5 font-ui text-[12px] font-medium uppercase tracking-wider text-text-muted">
                  Research request
                </p>
                {followUp.request_note?.trim() ? (
                  <p className="border-l-2 border-accent pl-3 font-body text-[14px] leading-snug text-text-secondary">
                    {followUp.request_note.trim()}
                  </p>
                ) : (
                  <p className="border-l-2 border-accent pl-3 font-body text-[13px] leading-snug text-text-muted">
                    You requested a follow-up from the{" "}
                    {formatBriefDateLabel(followUp.brief_date)} brief.
                  </p>
                )}
              </div>
            ) : null}
            {bullets.length > 0 ? (
              <ul className="list-inside list-disc space-y-2 font-body text-[16px] font-normal leading-snug text-text-secondary marker:text-accent sm:leading-[1.55]">
                {bullets.map((line, i) => (
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
          </div>
        </div>

        {actionRail ? (
          <div
            className="shrink-0 rounded-b-2xl px-4 pb-4 pt-2 sm:pb-5"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            role="presentation"
          >
            {actionRail}
          </div>
        ) : null}
      </div>
    </div>
  );
}
