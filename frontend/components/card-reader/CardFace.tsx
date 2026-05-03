"use client";

import { useEffect, useState } from "react";
import type { BriefItem } from "@/lib/types/brief";
import { resolveEntityBadge } from "@/lib/entity-badge";
import { renderMarkdown } from "@/lib/rendering/markdown";
import { CountryFlag } from "@/components/common/CountryFlag";
import { ItemAudioButton } from "./ItemAudioButton";

interface CardFaceProps {
  item: BriefItem;
  entityLogo?: { logoUrl: string | null; category: string } | null;
}

export function CardFace({ item, entityLogo }: CardFaceProps) {
  const bullets = item.key_bullets?.length
    ? item.key_bullets
    : item.main_bullet
      ? [item.main_bullet.slice(0, 120)]
      : [];

  // Many entity_logos rows currently point to PNGs that were never
  // uploaded to storage. Start by rendering the logo; if the <img>
  // onError fires, fall through to the section-based fallback.
  const [logoImgFailed, setLogoImgFailed] = useState(false);
  useEffect(() => {
    setLogoImgFailed(false);
  }, [entityLogo?.logoUrl]);

  const badge = resolveEntityBadge(item, {
    entityLogo: logoImgFailed ? null : entityLogo,
  });

  return (
    <div className="flex flex-col items-center text-center px-8 py-6 h-full">
      <div className="mb-6 mt-4">
        {badge.kind === "logo" ? (
          <img
            src={badge.logoUrl}
            alt={
              badge.label
              ?? item.badge_subject
              ?? item.primary_subject
              ?? item.primary_entity
              ?? ""
            }
            className="w-16 h-16 object-contain rounded-lg"
            onError={() => setLogoImgFailed(true)}
          />
        ) : badge.kind === "flag" ? (
          <CountryFlag
            code={badge.countryCode}
            className="w-16 h-16 rounded-lg"
            ariaLabel={badge.label ?? badge.countryCode.toUpperCase()}
          />
        ) : (
          <div
            className="flex w-16 h-16 items-center justify-center rounded-lg text-text-muted"
            aria-label={badge.label ?? `${badge.category} entity`}
          >
            <badge.Icon size={56} strokeWidth={1.75} aria-hidden="true" />
          </div>
        )}
        {badge.label && (
          <p className="text-[10px] text-text-muted mt-1.5 uppercase tracking-wider">
            {badge.label}
          </p>
        )}
      </div>

      <h2
        className="text-xl leading-tight font-semibold text-text-primary mb-6"
        style={{ fontFamily: "var(--font-heading, 'Playfair Display', serif)" }}
      >
        {item.headline}
      </h2>

      <div className="space-y-2.5 text-left w-full max-w-sm mb-6">
        {bullets.map((bullet, i) => (
          <div key={i} className="flex gap-2.5 items-start">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-primary shrink-0 mt-1.5" />
            <p className="text-sm text-text-muted leading-relaxed">
              {renderMarkdown(bullet)}
            </p>
          </div>
        ))}
      </div>

      <ItemAudioButton audioUrl={item.audio_url} />

      <p className="text-[10px] text-text-muted mt-auto pt-4">
        {item.source_name}
      </p>
    </div>
  );
}
