"use client";

import { useState } from "react";
import type { ExhibitData } from "@/lib/types/brief";

interface ExhibitEditorProps {
  exhibit: ExhibitData;
  onSave: (updated: ExhibitData) => void;
  onCancel: () => void;
}

const EXHIBIT_TYPES = [
  { value: "benchmark_table", label: "Benchmark Table" },
  { value: "comparison_table", label: "Comparison Table" },
  { value: "metric_highlight", label: "Metric Highlight" },
  { value: "timeline", label: "Timeline" },
  { value: "raw_image", label: "Raw Image" },
] as const;

function TableEditor({
  data,
  onChange,
}: {
  data: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
}) {
  const title = (data.title as string) ?? "";
  const columns = (data.columns ?? []) as string[];
  const rows = (data.rows ?? []) as Record<string, unknown>[];

  function updateTitle(val: string) {
    onChange({ ...data, title: val });
  }

  function updateColumn(idx: number, val: string) {
    const next = [...columns];
    next[idx] = val;
    onChange({ ...data, columns: next });
  }

  function updateCell(rowIdx: number, key: string, val: string) {
    const nextRows = [...rows];
    const row = { ...(nextRows[rowIdx] as Record<string, unknown>) };

    // Handle benchmark_table rows with nested scores
    if (row.scores && typeof row.scores === "object") {
      row.scores = { ...(row.scores as Record<string, string>), [key]: val };
    } else {
      row[key] = val;
    }
    nextRows[rowIdx] = row;
    onChange({ ...data, rows: nextRows });
  }

  function updateRowLabel(rowIdx: number, val: string) {
    const nextRows = [...rows];
    const row = { ...(nextRows[rowIdx] as Record<string, unknown>) };
    // Try benchmark and model keys
    if ("benchmark" in row) row.benchmark = val;
    else if ("model" in row) row.model = val;
    else {
      const firstKey = Object.keys(row).find((k) => k !== "scores");
      if (firstKey) row[firstKey] = val;
    }
    nextRows[rowIdx] = row;
    onChange({ ...data, rows: nextRows });
  }

  function addRow() {
    const newRow: Record<string, string> = {};
    if (rows[0] && typeof rows[0] === "object") {
      for (const key of Object.keys(rows[0] as Record<string, unknown>)) {
        if (key === "scores") {
          (newRow as Record<string, unknown>).scores = {};
        } else {
          newRow[key] = "";
        }
      }
    }
    onChange({ ...data, rows: [...rows, newRow] });
  }

  function removeRow(idx: number) {
    onChange({ ...data, rows: rows.filter((_, i) => i !== idx) });
  }

  // Get row label (first non-scores field)
  function getRowLabel(row: Record<string, unknown>): string {
    return String(row.benchmark ?? row.model ?? row[Object.keys(row).find((k) => k !== "scores") ?? ""] ?? "");
  }

  // Get cell values for a row
  function getCellValue(row: Record<string, unknown>, col: string): string {
    if (row.scores && typeof row.scores === "object") {
      return String((row.scores as Record<string, string>)[col] ?? "");
    }
    return String(row[col] ?? "");
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="text-[10px] uppercase tracking-wider text-text-muted">Title</label>
        <input
          value={title}
          onChange={(e) => updateTitle(e.target.value)}
          className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-2 py-1 text-xs text-text-primary"
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left py-1 pr-2 text-text-muted font-medium w-8" />
              <th className="text-left py-1 pr-2 text-text-muted font-medium">Label</th>
              {columns.map((col, i) => (
                <th key={i} className="py-1 px-1">
                  <input
                    value={col}
                    onChange={(e) => updateColumn(i, e.target.value)}
                    className="w-full rounded bg-surface-primary border border-border-secondary px-1.5 py-0.5 text-xs text-text-primary text-center"
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="border-t border-border-secondary/50">
                <td className="py-1 pr-1">
                  <button
                    onClick={() => removeRow(rowIdx)}
                    className="text-red-400/50 hover:text-red-400 text-[10px]"
                    title="Remove row"
                  >
                    ✕
                  </button>
                </td>
                <td className="py-1 pr-2">
                  <input
                    value={getRowLabel(row as Record<string, unknown>)}
                    onChange={(e) => updateRowLabel(rowIdx, e.target.value)}
                    className="w-full rounded bg-surface-primary border border-border-secondary px-1.5 py-0.5 text-xs text-text-primary"
                  />
                </td>
                {columns.map((col) => (
                  <td key={col} className="py-1 px-1">
                    <input
                      value={getCellValue(row as Record<string, unknown>, col)}
                      onChange={(e) => updateCell(rowIdx, col, e.target.value)}
                      className="w-full rounded bg-surface-primary border border-border-secondary px-1.5 py-0.5 text-xs text-text-primary text-center tabular-nums"
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        onClick={addRow}
        className="text-[10px] text-accent-primary hover:underline"
      >
        + Add Row
      </button>
    </div>
  );
}

function MetricEditor({
  data,
  onChange,
}: {
  data: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
}) {
  const metrics = (data.metrics ?? []) as { label: string; value: string; change?: string }[];

  function updateMetric(idx: number, field: string, val: string) {
    const next = [...metrics];
    next[idx] = { ...next[idx], [field]: val };
    onChange({ ...data, metrics: next });
  }

  return (
    <div className="space-y-2">
      {metrics.map((m, i) => (
        <div key={i} className="grid grid-cols-3 gap-2">
          <input
            value={m.label}
            onChange={(e) => updateMetric(i, "label", e.target.value)}
            placeholder="Label"
            className="rounded bg-surface-primary border border-border-secondary px-2 py-1 text-xs text-text-primary"
          />
          <input
            value={m.value}
            onChange={(e) => updateMetric(i, "value", e.target.value)}
            placeholder="Value"
            className="rounded bg-surface-primary border border-border-secondary px-2 py-1 text-xs text-text-primary"
          />
          <input
            value={m.change ?? ""}
            onChange={(e) => updateMetric(i, "change", e.target.value)}
            placeholder="Change (optional)"
            className="rounded bg-surface-primary border border-border-secondary px-2 py-1 text-xs text-text-primary"
          />
        </div>
      ))}
    </div>
  );
}

export function ExhibitEditor({ exhibit, onSave, onCancel }: ExhibitEditorProps) {
  const [type, setType] = useState(exhibit.type);
  const [data, setData] = useState(exhibit.data);

  function handleSave() {
    onSave({
      type: type as ExhibitData["type"],
      data,
      source_image_url: exhibit.source_image_url,
    });
  }

  const isTable = type === "benchmark_table" || type === "comparison_table";
  const isMetric = type === "metric_highlight";

  return (
    <div className="space-y-3">
      <div>
        <label className="text-[10px] uppercase tracking-wider text-text-muted">Exhibit Type</label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value as ExhibitData["type"])}
          className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-2 py-1 text-xs text-text-primary"
        >
          {EXHIBIT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {isTable && <TableEditor data={data} onChange={setData} />}
      {isMetric && <MetricEditor data={data} onChange={setData} />}

      {!isTable && !isMetric && (
        <div>
          <label className="text-[10px] uppercase tracking-wider text-text-muted">Raw JSON</label>
          <textarea
            value={JSON.stringify(data, null, 2)}
            onChange={(e) => {
              try { setData(JSON.parse(e.target.value)); } catch { /* ignore invalid JSON while typing */ }
            }}
            rows={8}
            className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-2 py-1.5 text-xs text-text-primary font-mono resize-y"
          />
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          className="text-xs px-3 py-1.5 rounded bg-green-600 text-white hover:bg-green-500"
        >
          Save Changes
        </button>
        <button
          onClick={onCancel}
          className="text-xs px-3 py-1.5 rounded bg-surface-primary text-text-muted hover:text-text-primary"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
