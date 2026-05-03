"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ActionBarButtonProps {
  icon: LucideIcon;
  label: string;
  active?: boolean;
  activeColor?: string;
  onClick: () => void;
}

export default function ActionBarButton({
  icon: Icon,
  label,
  active = false,
  activeColor = "text-accent-primary",
  onClick,
}: ActionBarButtonProps) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        "inline-flex min-h-9 items-center gap-1.5 rounded-sm px-2.5 py-1.5 transition-colors duration-150 cursor-pointer",
        "font-mono text-[14px]",
        active
          ? activeColor
          : "text-text-muted hover:text-text-secondary hover:bg-bg-tertiary"
      )}
    >
      <Icon className={cn("h-3.5 w-3.5", active && "fill-current")} />
      <span>{label}</span>
    </button>
  );
}
