import { cn } from "@/lib/utils";

interface MetaTagProps {
  children: React.ReactNode;
  className?: string;
}

export function MetaTag({ children, className }: MetaTagProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[4px] px-2 py-0.5 text-[11px] text-text-dim",
        className
      )}
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      {children}
    </span>
  );
}
