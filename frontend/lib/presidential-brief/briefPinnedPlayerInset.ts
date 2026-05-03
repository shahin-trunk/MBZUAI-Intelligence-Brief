/**
 * Bottom padding for brief routes when `BriefingPinnedPlayer` is mounted (fixed, z-50).
 * Matches bar height: border-t (1px) + pt-3 + min row (~44px) + pb-3 (no outer safe-area padding on shell).
 * No intentional gap above the bar — deck sits flush to the player.
 */
export const BRIEF_PINNED_PLAYER_RESERVE_BOTTOM_CLASS = "pb-[69px]";
