interface TimeGroupHeaderProps {
  label: string;
  variant?: "gold" | "muted";
}

export function TimeGroupHeader({
  label,
  variant = "muted",
}: TimeGroupHeaderProps) {
  const color = variant === "gold" ? "var(--sig-high)" : "var(--text-dim)";

  return (
    <div className="flex items-center gap-3 mt-6 mb-4">
      <span
        className="text-[11px] uppercase font-semibold shrink-0"
        style={{ color, letterSpacing: "0.06em" }}
      >
        {label}
      </span>
      <div className="h-px flex-1 bg-border-primary" />
    </div>
  );
}
