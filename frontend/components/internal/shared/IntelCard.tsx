import { cn } from "@/lib/utils";

type CardVariant = "action" | "standard" | "compact";

interface IntelCardProps {
  variant?: CardVariant;
  /** Semantic accent color for the left border (CSS color value) */
  accentColor?: string;
  className?: string;
  children: React.ReactNode;
  onClick?: () => void;
}

const variantClasses: Record<CardVariant, string> = {
  action:
    "rounded-r-[10px] rounded-l-[2px] border border-border-card bg-surface-elevated p-[var(--space-xl)]",
  standard:
    "rounded-[10px] border border-border-subtle bg-surface-raised p-[var(--space-xl)]",
  compact:
    "rounded-[8px] border border-border-subtle bg-surface-raised px-5 py-3.5 flex items-center justify-between",
};

export function IntelCard({
  variant = "standard",
  accentColor,
  className,
  children,
  onClick,
}: IntelCardProps) {
  return (
    <div
      className={cn(
        variantClasses[variant],
        "transition-colors hover:border-border-card-hover",
        onClick && "cursor-pointer",
        className
      )}
      style={accentColor ? { borderLeftWidth: 3, borderLeftColor: accentColor } : undefined}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  );
}
