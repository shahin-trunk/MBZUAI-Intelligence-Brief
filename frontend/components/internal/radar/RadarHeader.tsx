import { formatMonthDisplay } from "@/lib/config/lenses";

interface RadarHeaderProps {
  month: string;
  lastUpdated: string;
  generatedBy: string;
}

export function RadarHeader({ month, lastUpdated, generatedBy }: RadarHeaderProps) {
  const updatedDate = new Date(lastUpdated).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div>
      <p className="font-mono text-[11px] text-text-muted uppercase tracking-[0.1em]">
        {formatMonthDisplay(month)}
      </p>
      <h1 className="mt-1 font-serif text-[28px] text-text-bright">
        Presidential Radar
      </h1>
      <p className="mt-2 font-mono text-[12px] text-text-muted">
        Updated {updatedDate} &middot; {generatedBy}
      </p>
    </div>
  );
}
