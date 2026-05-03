"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Plus, Pencil, Trash2, X, Check } from "lucide-react";

/* ─── Types ──────────────────────────────────────────────────────────── */

interface WatchlistEntity {
  id: string;
  entity_name: string;
  aliases: string[];
  priority: "high" | "standard";
  notes: string | null;
  enabled: boolean;
  last_hit_date: string | null;
  created_at: string;
}

type FilterTab = "all" | "high" | "standard" | "disabled";

/* ─── Component ──────────────────────────────────────────────────────── */

export default function ScoutWatchlistPage() {
  const [entities, setEntities] = useState<WatchlistEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterTab>("all");

  // Add form state
  const [showAdd, setShowAdd] = useState(false);
  const [addName, setAddName] = useState("");
  const [addAliases, setAddAliases] = useState("");
  const [addPriority, setAddPriority] = useState<"high" | "standard">("standard");
  const [addNotes, setAddNotes] = useState("");
  const [saving, setSaving] = useState(false);

  // Edit state
  const [editId, setEditId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editAliases, setEditAliases] = useState("");
  const [editPriority, setEditPriority] = useState<"high" | "standard">("standard");
  const [editNotes, setEditNotes] = useState("");

  const fetchEntities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/scout-watchlist");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setEntities(json.entities ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  const handleAdd = async () => {
    if (!addName.trim()) return;
    setSaving(true);
    try {
      const res = await fetch("/api/admin/scout-watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_name: addName.trim(),
          aliases: addAliases
            .split(",")
            .map((a) => a.trim())
            .filter(Boolean),
          priority: addPriority,
          notes: addNotes.trim() || null,
        }),
      });
      if (!res.ok) {
        const json = await res.json();
        throw new Error(json.error || `HTTP ${res.status}`);
      }
      setShowAdd(false);
      setAddName("");
      setAddAliases("");
      setAddPriority("standard");
      setAddNotes("");
      fetchEntities();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleEnabled = async (entity: WatchlistEntity) => {
    try {
      const res = await fetch(`/api/admin/scout-watchlist?id=${entity.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !entity.enabled }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      fetchEntities();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`/api/admin/scout-watchlist?id=${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      fetchEntities();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const startEdit = (entity: WatchlistEntity) => {
    setEditId(entity.id);
    setEditName(entity.entity_name);
    setEditAliases((entity.aliases ?? []).join(", "));
    setEditPriority(entity.priority);
    setEditNotes(entity.notes ?? "");
  };

  const handleSaveEdit = async () => {
    if (!editId || !editName.trim()) return;
    setSaving(true);
    try {
      const res = await fetch(`/api/admin/scout-watchlist?id=${editId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_name: editName.trim(),
          aliases: editAliases
            .split(",")
            .map((a) => a.trim())
            .filter(Boolean),
          priority: editPriority,
          notes: editNotes.trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setEditId(null);
      fetchEntities();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  // Filter entities
  const filtered = entities.filter((e) => {
    if (filter === "high") return e.priority === "high" && e.enabled;
    if (filter === "standard") return e.priority === "standard" && e.enabled;
    if (filter === "disabled") return !e.enabled;
    return true;
  });

  const counts = {
    all: entities.length,
    high: entities.filter((e) => e.priority === "high" && e.enabled).length,
    standard: entities.filter((e) => e.priority === "standard" && e.enabled).length,
    disabled: entities.filter((e) => !e.enabled).length,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-[28px] text-text-bright">
          Scout Watchlist
        </h1>
        <button
          type="button"
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 rounded-sm border border-accent-primary bg-accent-primary/10 px-3 py-1.5 font-mono text-[13px] text-accent-primary hover:bg-accent-primary/20 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Entity
        </button>
      </div>

      {/* ── Add Form ────────────────────────────────────────────────── */}
      {showAdd && (
        <div className="rounded-sm border border-border-primary bg-bg-secondary p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Entity name *"
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              className="rounded-sm border border-border-primary bg-bg-primary px-3 py-1.5 font-mono text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
            />
            <input
              type="text"
              placeholder="Aliases (comma-separated)"
              value={addAliases}
              onChange={(e) => setAddAliases(e.target.value)}
              className="rounded-sm border border-border-primary bg-bg-primary px-3 py-1.5 font-mono text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
            />
            <select
              value={addPriority}
              onChange={(e) =>
                setAddPriority(e.target.value as "high" | "standard")
              }
              className="rounded-sm border border-border-primary bg-bg-primary px-3 py-1.5 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
            >
              <option value="standard">Standard priority</option>
              <option value="high">High priority</option>
            </select>
            <input
              type="text"
              placeholder="Notes (optional)"
              value={addNotes}
              onChange={(e) => setAddNotes(e.target.value)}
              className="rounded-sm border border-border-primary bg-bg-primary px-3 py-1.5 font-mono text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleAdd}
              disabled={saving || !addName.trim()}
              className="rounded-sm bg-accent-primary px-4 py-1.5 font-mono text-[13px] text-bg-primary hover:bg-accent-primary/90 transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="rounded-sm border border-border-primary px-4 py-1.5 font-mono text-[13px] text-text-muted hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── Filter Tabs ─────────────────────────────────────────────── */}
      <div className="flex gap-1">
        {(["all", "high", "standard", "disabled"] as FilterTab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setFilter(tab)}
            className={cn(
              "rounded-sm px-3 py-1 font-mono text-[12px] transition-colors",
              filter === tab
                ? "bg-bg-tertiary text-text-bright"
                : "text-text-muted hover:text-text-primary hover:bg-bg-tertiary/50"
            )}
          >
            {tab === "all"
              ? `All (${counts.all})`
              : tab === "high"
                ? `High (${counts.high})`
                : tab === "standard"
                  ? `Standard (${counts.standard})`
                  : `Disabled (${counts.disabled})`}
          </button>
        ))}
      </div>

      {/* ── Loading / Error ────────────────────────────────────────── */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="font-mono text-sm text-text-muted">Loading...</p>
        </div>
      )}

      {error && (
        <div className="rounded-sm border border-accent-danger/20 bg-accent-danger/5 p-3">
          <p className="font-mono text-sm text-accent-danger">{error}</p>
        </div>
      )}

      {/* ── Entity Table ───────────────────────────────────────────── */}
      {!loading && !error && (
        <div className="overflow-x-auto rounded-sm border border-border-primary">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-primary bg-bg-secondary">
                <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Entity
                </th>
                <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Aliases
                </th>
                <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Priority
                </th>
                <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Enabled
                </th>
                <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Last Hit
                </th>
                <th className="px-4 py-2.5 text-left font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Notes
                </th>
                <th className="px-4 py-2.5 text-right font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((entity) => (
                <tr
                  key={entity.id}
                  className="border-b border-border-primary last:border-0 hover:bg-bg-tertiary/30 transition-colors"
                >
                  {editId === entity.id ? (
                    /* ── Inline edit row ─── */
                    <>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={editAliases}
                          onChange={(e) => setEditAliases(e.target.value)}
                          className="w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <select
                          value={editPriority}
                          onChange={(e) =>
                            setEditPriority(
                              e.target.value as "high" | "standard"
                            )
                          }
                          className="rounded-sm border border-border-primary bg-bg-primary px-2 py-1 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
                        >
                          <option value="standard">Standard</option>
                          <option value="high">High</option>
                        </select>
                      </td>
                      <td className="px-4 py-2" />
                      <td className="px-4 py-2" />
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          className="w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1 font-mono text-[13px] text-text-primary focus:outline-none focus:border-accent-primary"
                        />
                      </td>
                      <td className="px-4 py-2 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={handleSaveEdit}
                            disabled={saving}
                            className="rounded-sm p-1 text-accent-primary hover:bg-accent-primary/10 transition-colors"
                          >
                            <Check className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditId(null)}
                            className="rounded-sm p-1 text-text-muted hover:text-text-primary transition-colors"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </>
                  ) : (
                    /* ── Display row ─── */
                    <>
                      <td className="px-4 py-2.5 font-mono text-[13px] text-text-primary">
                        {entity.entity_name}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {(entity.aliases ?? []).map((alias) => (
                            <span
                              key={alias}
                              className="rounded-sm bg-bg-tertiary px-1.5 py-0.5 font-mono text-[11px] text-text-muted"
                            >
                              {alias}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={cn(
                            "rounded-sm border px-2 py-0.5 font-mono text-[11px]",
                            entity.priority === "high"
                              ? "bg-sig-high/10 text-sig-high border-sig-high/20"
                              : "bg-bg-tertiary text-text-muted border-border-primary"
                          )}
                        >
                          {entity.priority}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <button
                          type="button"
                          onClick={() => handleToggleEnabled(entity)}
                          className={cn(
                            "h-5 w-9 rounded-full transition-colors relative",
                            entity.enabled
                              ? "bg-accent-primary"
                              : "bg-bg-tertiary"
                          )}
                        >
                          <span
                            className={cn(
                              "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
                              entity.enabled
                                ? "translate-x-4"
                                : "translate-x-0.5"
                            )}
                          />
                        </button>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[13px] text-text-muted">
                        {entity.last_hit_date ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[12px] text-text-secondary max-w-[200px] truncate">
                        {entity.notes ?? ""}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => startEdit(entity)}
                            className="rounded-sm p-1 text-text-muted hover:text-text-primary transition-colors"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(entity.id)}
                            className="rounded-sm p-1 text-text-muted hover:text-accent-danger transition-colors"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-8 text-center font-mono text-sm text-text-muted"
                  >
                    No entities match the current filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
