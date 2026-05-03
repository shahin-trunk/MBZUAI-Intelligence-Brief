"use client";

import { useEffect, useState } from "react";

interface CalibrationData {
  total_sessions: number;
  overlap_rate: number;
  total_keeps: number;
  total_removes: number;
  total_promotes: number;
  total_edits: number;
  total_manual_adds: number;
  promotion_rate: number;
  edit_rate: number;
}

function MetricCard({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div className="rounded-lg border border-border-primary bg-surface-secondary p-4">
      <p className="text-[10px] uppercase tracking-wider text-text-muted">{label}</p>
      <p className="text-2xl font-bold tabular-nums mt-1">
        {value}
        <span className="text-sm font-normal text-text-muted ml-0.5">{unit}</span>
      </p>
    </div>
  );
}

export default function CalibrationPage() {
  const [data, setData] = useState<CalibrationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/curation/calibration")
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-6 text-text-muted">Loading calibration data...</div>;
  }

  if (!data || data.total_sessions === 0) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <h1 className="text-xl font-semibold mb-4">AI-Human Calibration</h1>
        <p className="text-text-muted">
          No curation sessions recorded yet. Calibration metrics will appear after the first brief is curated and published.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-2">AI-Human Calibration</h1>
      <p className="text-sm text-text-muted mb-6">
        Tracking where the analyst agrees and disagrees with the AI pipeline across {data.total_sessions} curation sessions.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <MetricCard label="AI Overlap Rate" value={data.overlap_rate} unit="%" />
        <MetricCard label="Promotion Rate" value={data.promotion_rate} unit="%" />
        <MetricCard label="Edit Rate" value={data.edit_rate} unit="%" />
        <MetricCard label="Manual Adds" value={data.total_manual_adds} unit="" />
      </div>

      <div className="rounded-lg border border-border-primary bg-surface-secondary p-4">
        <h2 className="text-sm font-medium mb-3">Decision Breakdown</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
          <div>
            <p className="text-lg font-bold text-green-400">{data.total_keeps}</p>
            <p className="text-[10px] text-text-muted uppercase">Kept</p>
          </div>
          <div>
            <p className="text-lg font-bold text-red-400">{data.total_removes}</p>
            <p className="text-[10px] text-text-muted uppercase">Removed</p>
          </div>
          <div>
            <p className="text-lg font-bold text-amber-400">{data.total_promotes}</p>
            <p className="text-[10px] text-text-muted uppercase">Promoted</p>
          </div>
          <div>
            <p className="text-lg font-bold text-accent-primary">{data.total_edits}</p>
            <p className="text-[10px] text-text-muted uppercase">Edited</p>
          </div>
          <div>
            <p className="text-lg font-bold text-text-primary">{data.total_manual_adds}</p>
            <p className="text-[10px] text-text-muted uppercase">Added</p>
          </div>
        </div>
      </div>
    </div>
  );
}
