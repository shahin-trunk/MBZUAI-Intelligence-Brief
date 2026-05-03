import type { EngagementMaterial } from "@/lib/types/executive-engagement";

interface MaterialChipProps {
  material: EngagementMaterial;
}

export function MaterialChip({ material }: MaterialChipProps) {
  if (!material.url) {
    return (
      <span
        aria-disabled="true"
        className="inline-flex items-center gap-1.5 rounded-[6px] px-3.5 py-2 text-[12px] text-text-dim"
        style={{
          background: "rgba(148,163,184,0.06)",
          border: "1px solid var(--border-primary)",
        }}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="shrink-0"
        >
          <path d="M9 1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V5L9 1Z" />
          <path d="M9 1v4h4" />
        </svg>
        {material.name}
      </span>
    );
  }

  return (
    <a
      href={material.url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-[6px] px-3.5 py-2 text-[12px] text-text-secondary transition-colors hover:text-text-secondary cursor-pointer"
      style={{
        background: "rgba(148,163,184,0.06)",
        border: "1px solid var(--border-primary)",
      }}
    >
      {/* Document icon */}
      <svg
        width="14"
        height="14"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="shrink-0"
      >
        <path d="M9 1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V5L9 1Z" />
        <path d="M9 1v4h4" />
      </svg>
      {material.name}
    </a>
  );
}
