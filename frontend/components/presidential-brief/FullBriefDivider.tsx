export default function FullBriefDivider() {
  return (
    <div className="my-8 flex items-center gap-4">
      <div className="h-px flex-1 bg-rule" />
      <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
        Full Brief
      </span>
      <div className="h-px flex-1 bg-rule" />
    </div>
  );
}
