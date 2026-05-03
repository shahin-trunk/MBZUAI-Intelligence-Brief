"use client";

import { useToast } from "@/lib/contexts/ToastContext";
import { cn } from "@/lib/utils";
import { CheckCircle2, AlertCircle, Info } from "lucide-react";

const variantStyles = {
  success: {
    icon: CheckCircle2,
    color: "text-accent-success",
  },
  error: {
    icon: AlertCircle,
    color: "text-accent-danger",
  },
  info: {
    icon: Info,
    color: "text-accent-primary",
  },
} as const;

export function ToastContainer() {
  const { toast } = useToast();

  if (!toast) return null;

  const { icon: Icon, color } = variantStyles[toast.variant];

  return (
    <div className="fixed bottom-4 right-4 z-50 max-sm:left-1/2 max-sm:-translate-x-1/2 max-sm:right-auto">
      <div
        key={toast.id}
        className={cn(
          "flex items-center gap-2 rounded-sm border border-border-accent bg-bg-tertiary px-4 py-3 shadow-lg",
          "animate-in slide-in-from-bottom-2 fade-in duration-200"
        )}
      >
        <Icon className={cn("h-4 w-4 shrink-0", color)} />
        <span className="font-mono text-[12px] text-text-primary">
          {toast.message}
        </span>
      </div>
    </div>
  );
}
