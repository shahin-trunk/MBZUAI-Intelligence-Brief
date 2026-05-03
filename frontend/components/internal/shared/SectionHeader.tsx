interface SectionHeaderProps {
  title: string;
  count?: number;
  action?: React.ReactNode;
}

export function SectionHeader({ title, count, action }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="h-px w-4 bg-border-accent" />
      <h2 className="font-mono text-[11px] uppercase tracking-[0.07em] text-text-dim shrink-0">
        {title}
      </h2>
      <div className="h-px flex-1 bg-border-subtle" />
      {count != null && (
        <span className="text-[11px] text-text-dim shrink-0">{count}</span>
      )}
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
