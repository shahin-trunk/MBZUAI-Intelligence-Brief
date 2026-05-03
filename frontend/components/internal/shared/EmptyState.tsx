interface EmptyStateProps {
  /** SVG icon (24×24 stroke icon) */
  icon?: React.ReactNode;
  headline: string;
  description?: string;
  /** Optional CTA button */
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({
  icon,
  headline,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && (
        <div
          className="mb-4 flex h-12 w-12 items-center justify-center rounded-[12px]"
          style={{ background: "rgba(212,168,67,0.08)" }}
        >
          <div className="text-sig-high">{icon}</div>
        </div>
      )}
      <p className="text-[15px] font-medium text-text-primary mb-1">
        {headline}
      </p>
      {description && (
        <p className="text-[13px] text-text-dim mb-5 max-w-sm">{description}</p>
      )}
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="rounded-[8px] px-5 py-2 text-[13px] font-medium text-sig-high transition-colors hover:bg-[rgba(212,168,67,0.08)]"
          style={{ border: "1px solid var(--border-gold)" }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
