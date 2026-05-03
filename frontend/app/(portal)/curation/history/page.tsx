"use client";

import { useEffect, useState } from "react";

interface HistoryBrief {
  id: string;
  brief_date: string;
  status: string;
  approved_at: string | null;
  published_at: string | null;
  pipeline_stats: { total_cost_usd?: number } | null;
}

export default function CurationHistoryPage() {
  const [briefs, setBriefs] = useState<HistoryBrief[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/curation/history")
      .then((r) => r.json())
      .then((data) => setBriefs(data.briefs ?? []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-6 text-text-muted">Loading history...</div>;
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">Curation History</h1>

      {briefs.length === 0 ? (
        <p className="text-text-muted">No published briefs yet.</p>
      ) : (
        <div className="space-y-2">
          {briefs.map((b) => (
            <div
              key={b.id}
              className="flex items-center justify-between rounded-lg border border-border-primary bg-surface-secondary p-4"
            >
              <div>
                <p className="font-medium text-sm">{b.brief_date}</p>
                <p className="text-xs text-text-muted">
                  Published{" "}
                  {b.published_at
                    ? new Date(b.published_at).toLocaleString()
                    : "N/A"}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {b.pipeline_stats?.total_cost_usd != null && (
                  <span className="text-xs text-text-muted tabular-nums">
                    ${Number(b.pipeline_stats.total_cost_usd).toFixed(2)}
                  </span>
                )}
                <span className="px-2 py-0.5 rounded text-[10px] bg-green-500/10 text-green-400">
                  {b.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
