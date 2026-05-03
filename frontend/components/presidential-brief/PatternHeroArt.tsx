import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";

const HERO_PATTERN_SVG = encodeURIComponent(`
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 160'>
  <rect width='240' height='160' fill='#09111b'/>
  <defs>
    <g id='star'>
      <path d='M0 -30 L14 -16 L0 -2 L-14 -16 Z' fill='#27426c' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M0 30 L14 16 L0 2 L-14 16 Z' fill='#27426c' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M-30 0 L-16 -14 L-2 0 L-16 14 Z' fill='#27426c' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M30 0 L16 -14 L2 0 L16 14 Z' fill='#27426c' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M-10 -10 L0 -20 L10 -10 L0 0 Z' fill='#355889' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M-10 10 L0 0 L10 10 L0 20 Z' fill='#355889' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
    </g>
    <g id='knot'>
      <path d='M0 0 H30 V14 H14 V30 H0 Z' fill='#1d3151' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M30 0 H60 V14 H46 V30 H30 Z' fill='#243d63' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M14 30 H30 V46 H14 Z' fill='#243d63' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M46 30 H60 V46 H46 Z' fill='#1d3151' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M0 46 H14 V60 H0 Z' fill='#243d63' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M46 46 H60 V60 H46 Z' fill='#243d63' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
      <path d='M14 46 H46 V60 H14 Z' fill='#2c4a74' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
    </g>
  </defs>
  <use href='#knot' x='0' y='0'/>
  <use href='#knot' x='60' y='0'/>
  <use href='#knot' x='120' y='0'/>
  <use href='#knot' x='180' y='0'/>
  <use href='#knot' x='0' y='60'/>
  <use href='#knot' x='180' y='60'/>
  <use href='#star' transform='translate(120 80)'/>
  <use href='#star' transform='translate(40 34) scale(0.8)'/>
  <use href='#star' transform='translate(200 36) scale(0.72)'/>
  <use href='#star' transform='translate(40 126) scale(0.72)'/>
  <use href='#star' transform='translate(200 126) scale(0.8)'/>
  <path d='M60 0 L92 32 L60 64 L28 32 Z' fill='#1d3151' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
  <path d='M180 0 L212 32 L180 64 L148 32 Z' fill='#1d3151' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
  <path d='M60 96 L92 128 L60 160 L28 128 Z' fill='#1d3151' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
  <path d='M180 96 L212 128 L180 160 L148 128 Z' fill='#1d3151' stroke='#040608' stroke-width='6' stroke-linejoin='round'/>
  <path d='M90 24 H150' stroke='#040608' stroke-width='6' stroke-linecap='square'/>
  <path d='M90 136 H150' stroke='#040608' stroke-width='6' stroke-linecap='square'/>
  <path d='M24 80 H72' stroke='#040608' stroke-width='6' stroke-linecap='square'/>
  <path d='M168 80 H216' stroke='#040608' stroke-width='6' stroke-linecap='square'/>
</svg>
`.trim());

const HERO_PATTERN_STYLE: CSSProperties = {
  backgroundColor: "#09111b",
  backgroundImage: `url("data:image/svg+xml,${HERO_PATTERN_SVG}")`,
  backgroundPosition: "center",
  backgroundRepeat: "repeat",
  backgroundSize: "240px 160px",
};

export const STORY_HEADER_BADGE_CLASSES =
  "inline-flex max-w-full items-center rounded-full bg-[#f6e7eb] px-3 py-1 font-ui text-[12px] font-semibold text-[#8a3146] shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] sm:text-[13px]";

interface PatternHeroArtProps {
  className?: string;
  children?: ReactNode;
}

export default function PatternHeroArt({
  className,
  children,
}: PatternHeroArtProps) {
  return (
    <div
      className={cn("relative isolate overflow-hidden bg-[#09111b]", className)}
      style={HERO_PATTERN_STYLE}
    >
      <div
        className="absolute inset-0 bg-[radial-gradient(circle_at_16%_18%,rgba(61,95,149,0.26),transparent_28%),radial-gradient(circle_at_84%_24%,rgba(34,54,89,0.18),transparent_26%),linear-gradient(180deg,rgba(6,9,14,0.1)_0%,rgba(6,9,14,0.2)_42%,rgba(6,9,14,0.76)_100%)]"
        aria-hidden="true"
      />
      <div
        className="absolute inset-0 bg-[linear-gradient(180deg,rgba(2,4,8,0.04)_0%,rgba(2,4,8,0.16)_44%,rgba(2,4,8,0.82)_100%)]"
        aria-hidden="true"
      />
      {children}
    </div>
  );
}
