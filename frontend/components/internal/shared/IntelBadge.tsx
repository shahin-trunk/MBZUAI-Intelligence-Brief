import { cn } from "@/lib/utils";

type BadgeVariant =
  | "urgent"
  | "watch"
  | "info"
  | "blue"
  | "strategic"
  | "neutral";

const variantStyles: Record<
  BadgeVariant,
  { background: string; color: string }
> = {
  urgent: {
    background: "var(--badge-urgent-bg)",
    color: "var(--badge-urgent-text)",
  },
  watch: {
    background: "var(--badge-watch-bg)",
    color: "var(--badge-watch-text)",
  },
  info: {
    background: "var(--badge-info-bg)",
    color: "var(--badge-info-text)",
  },
  blue: {
    background: "var(--badge-blue-bg)",
    color: "var(--badge-blue-text)",
  },
  strategic: {
    background: "var(--badge-strategic-bg)",
    color: "var(--badge-strategic-text)",
  },
  neutral: {
    background: "var(--border-primary)",
    color: "var(--text-secondary)",
  },
};

interface IntelBadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function IntelBadge({ variant, children, className }: IntelBadgeProps) {
  const styles = variantStyles[variant];
  return (
    <span
      className={cn("intel-badge", className)}
      style={{ background: styles.background, color: styles.color }}
    >
      {children}
    </span>
  );
}
