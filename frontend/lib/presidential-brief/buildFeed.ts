import type { Brief, BriefItem, FeedCard, FollowUpItem } from "@/lib/types/brief";

function appendBriefStories(brief: Brief, feed: FeedCard[]): number {
  let added = 0;
  for (const section of brief.sections) {
    if (section.items.length === 0) continue;
    for (const item of section.items) {
      feed.push({ type: "story", item });
      added++;
    }
  }
  return added;
}

function briefItemFromFollowUp(fu: FollowUpItem): BriefItem {
  const mainBullet =
    fu.response_summary?.trim() ||
    (fu.status === "responded"
      ? "The team has posted an update on this item."
      : "Awaiting team response on this flagged item.");

  const section = fu.original_section.trim() || "UAE";

  return {
    id: `followup-${fu.id}`,
    headline: fu.original_headline,
    main_bullet: mainBullet,
    source_name: fu.original_source_name?.trim() || "Brief",
    source_url: fu.original_source_url,
    significance: "medium",
    composite_score: 0,
    topic_relevance: 0,
    news_significance: 0,
    is_continuity: true,
    continuity_days: 0,
    section,
    rank: 0,
    depth: "brief",
    entities: [],
    additional_sources: [],
    is_model_release: false,
  };
}

export interface TabbedFeeds {
  newsFeed: FeedCard[];
  followUpFeed: FeedCard[];
}

/**
 * Builds two feeds: main briefing (today + optional yesterday) vs follow-up cards only.
 * Each feed ends with its own `end` card and matching `itemsReviewed` count.
 */
export function buildTabbedFeeds(
  todayBrief: Brief,
  yesterdayBrief?: Brief | null,
  followUps?: FollowUpItem[]
): TabbedFeeds {
  const newsFeed: FeedCard[] = [];
  let newsStories = appendBriefStories(todayBrief, newsFeed);

  if (
    yesterdayBrief &&
    yesterdayBrief.sections.some((s) => s.items.length > 0)
  ) {
    newsStories += appendBriefStories(yesterdayBrief, newsFeed);
  }

  newsFeed.push({
    type: "end",
    itemsReviewed: newsStories,
    itemsFlagged: 0,
  });

  const followUpFeed: FeedCard[] = [];
  let fuStories = 0;
  if (followUps && followUps.length > 0) {
    for (const followUp of followUps) {
      followUpFeed.push({
        type: "story",
        item: briefItemFromFollowUp(followUp),
        followUp,
      });
      fuStories++;
    }
  }
  followUpFeed.push({
    type: "end",
    itemsReviewed: fuStories,
    itemsFlagged: 0,
  });

  return { newsFeed, followUpFeed };
}

/**
 * How many briefing stories must appear before follow-up `fuIndex` (0-based).
 * First follow-up lands as the 2nd card (after one pick). Rest are spread through
 * the deck so they are not all clumped at the end.
 */
function scatterFollowUpAfterNewsCounts(
  newsCount: number,
  fuCount: number
): number[] {
  if (fuCount === 0) return [];
  if (newsCount === 0) {
    return Array.from({ length: fuCount }, () => 0);
  }

  const after: number[] = [];
  after.push(1);

  if (fuCount === 1) return after;

  for (let i = 1; i < fuCount; i++) {
    const t = i / (fuCount - 1);
    let pos = Math.round(1 + t * (newsCount - 1));
    pos = Math.max(after[i - 1]!, pos);
    pos = Math.min(newsCount, pos);
    after.push(pos);
  }

  for (let i = 1; i < after.length; i++) {
    if (after[i]! <= after[i - 1]!) {
      after[i] = Math.min(newsCount, after[i - 1]! + 1);
    }
  }

  return after;
}

function mergeNewsAndFollowUpsScattered(
  newsStories: FeedCard[],
  fuStories: FeedCard[]
): FeedCard[] {
  const n = newsStories.length;
  const f = fuStories.length;
  if (f === 0) return [...newsStories];
  if (n === 0) return [...fuStories];

  const afterEachFu = scatterFollowUpAfterNewsCounts(n, f);
  const merged: FeedCard[] = [];
  let ni = 0;
  let fi = 0;

  while (ni < n || fi < f) {
    while (fi < f && afterEachFu[fi] === ni) {
      merged.push(fuStories[fi]!);
      fi++;
    }
    if (ni < n) {
      merged.push(newsStories[ni]!);
      ni++;
    } else {
      while (fi < f) {
        merged.push(fuStories[fi]!);
        fi++;
      }
    }
  }

  return merged;
}

/**
 * Builds the card feed from today's brief, optionally yesterday's, and follow-ups.
 * Follow-up cards are interleaved into the briefing stream (not all at the end).
 */
export function buildFeed(
  todayBrief: Brief,
  yesterdayBrief?: Brief | null,
  followUps?: FollowUpItem[]
): FeedCard[] {
  const { newsFeed, followUpFeed } = buildTabbedFeeds(
    todayBrief,
    yesterdayBrief,
    followUps
  );
  const newsStories = newsFeed.slice(0, -1);
  const fuStories = followUpFeed.slice(0, -1);
  const merged = mergeNewsAndFollowUpsScattered(newsStories, fuStories);
  const totalStories = merged.filter((c) => c.type === "story").length;
  merged.push({
    type: "end",
    itemsReviewed: totalStories,
    itemsFlagged: 0,
  });
  return merged;
}
