interface DossierSectionProps {
  label: string;
  variant?: "gold" | "muted";
  count?: number;
  collapsible?: boolean;
  expanded?: boolean;
  onToggle?: () => void;
  children: React.ReactNode;
}

export function DossierSection({
  label,
  variant = "muted",
  count,
  collapsible = false,
  expanded = true,
  onToggle,
  children,
}: DossierSectionProps) {
  const color = variant === "gold" ? "var(--sig-high)" : "var(--text-secondary)";

  return (
    <div className="px-6 py-[18px]">
      {/* Gradient fade divider above */}
      <div className="mb-5">
        <div
          className="h-px w-full"
          style={{
            background:
              "linear-gradient(to right, transparent, rgba(212,168,67,0.15), transparent)",
          }}
        />
      </div>

      {/* Label row */}
      <div className="flex items-center gap-2 mb-3">
        {collapsible ? (
          <button
            type="button"
            onClick={onToggle}
            className="flex items-center gap-2 group cursor-pointer"
            aria-expanded={expanded}
          >
            {/* Chevron */}
            <svg
              width="14"
              height="14"
              viewBox="0 0 16 16"
              fill="none"
              stroke="var(--text-dim)"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="transition-transform duration-200"
              style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}
            >
              <path d="M6 4l4 4-4 4" />
            </svg>
            <h4
              className="text-[11px] uppercase font-semibold font-mono group-hover:opacity-80 transition-opacity"
              style={{ color, letterSpacing: "0.06em" }}
            >
              {label}
            </h4>
          </button>
        ) : (
          <h4
            className="text-[11px] uppercase font-semibold font-mono"
            style={{ color, letterSpacing: "0.06em" }}
          >
            {label}
          </h4>
        )}

        {/* Extending line */}
        <div
          className="flex-1 h-px"
          style={{ background: "rgba(255,255,255,0.04)" }}
        />

        {/* Count badge */}
        {count !== undefined && (
          <span
            className="text-[11px] font-mono text-text-dim"
            style={{ letterSpacing: "0.04em" }}
          >
            {count}
          </span>
        )}
      </div>

      {/* Content — animated if collapsible */}
      {collapsible ? (
        <div
          style={{
            maxHeight: expanded ? "2000px" : "0",
            opacity: expanded ? 1 : 0,
            overflow: "hidden",
            transition: "max-height 300ms ease, opacity 200ms ease",
          }}
        >
          {children}
        </div>
      ) : (
        children
      )}
    </div>
  );
}
