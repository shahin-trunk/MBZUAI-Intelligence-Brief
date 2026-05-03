"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth/AuthProvider";
import {
  groupCurationItemsBySection,
  sortSelectedItemsForOrdering,
} from "@/lib/curation/items";
import type { CurationItem, PendingBrief } from "@/lib/types/curation";
import { ItemSlate } from "./ProposedSlate";
import { ManualAddDialog } from "./ManualAddDialog";
import { OrderingScreen } from "./OrderingScreen";
import { FilteredCandidatesPanel } from "./FilteredCandidatesPanel";
import { QueuedEntriesBanner } from "./QueuedEntriesBanner";
import { AudioStatusBanner } from "@/components/brief/AudioStatusBanner";
import { PublishedBriefEditor } from "./PublishedBriefEditor";
import type { BriefItem } from "@/lib/types/brief";

interface CurationWorkspaceProps {
  initialBrief: PendingBrief | null;
  initialItems: CurationItem[];
  todayPublished?: boolean;
  publishedBriefDate?: string | null;
  publishedItems?: BriefItem[];
}

function replaceItem(items: CurationItem[], updated: CurationItem) {
  return items.map((item) =>
    item.kind === updated.kind && item.id === updated.id ? updated : item
  );
}

function nextLocalCurationOrder(items: CurationItem[]) {
  const orders = items
    .filter((item) => item.selected)
    .map((item) => item.curation_order ?? 0)
    .filter((value) => value > 0);
  return (orders.length > 0 ? Math.max(...orders) : 0) + 1;
}

export function CurationWorkspace({
  initialBrief,
  initialItems,
  todayPublished = false,
  publishedBriefDate = null,
  publishedItems: initialPublishedItems = [],
}: CurationWorkspaceProps) {
  const { user } = useAuth();
  const [brief, setBrief] = useState(initialBrief);
  const [items, setItems] = useState<CurationItem[]>(initialItems);
  const [showManualAdd, setShowManualAdd] = useState(false);
  const [approving, setApproving] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [phase, setPhase] = useState<"select" | "order" | "published">("select");
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [publishResult, setPublishResult] = useState<{
    briefDate: string;
    itemCount: number;
    audioDispatched: boolean;
  } | null>(null);
  const autoClaimAttemptedForBrief = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/curation/pending");
    if (!res.ok) return;
    const data = await res.json();
    setBrief(data.brief ?? null);
    setItems(data.items ?? []);
  }, []);

  useEffect(() => {
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [refresh]);

  const groupedItems = groupCurationItemsBySection(items);
  const selectedCount = items.filter((item) => item.selected).length;
  // Default the active tab to the first non-empty section once items load.
  const effectiveActiveSection =
    activeSection ?? groupedItems[0]?.section ?? null;
  const activeGroup =
    groupedItems.find((g) => g.section === effectiveActiveSection) ??
    groupedItems[0] ??
    null;

  const [pubItems, setPubItems] = useState<BriefItem[]>(initialPublishedItems);
  const [pubDate, setPubDate] = useState<string | null>(publishedBriefDate);

  const refreshPublished = useCallback(async () => {
    if (!pubDate) return;
    const res = await fetch(`/api/briefs/${pubDate}/items`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.items) {
      setPubItems(data.items);
    }
  }, [pubDate]);

  useEffect(() => {
    if (!brief || !user?.id || brief.status !== "pending") return;
    if (autoClaimAttemptedForBrief.current === brief.id) return;
    autoClaimAttemptedForBrief.current = brief.id;
    void handleClaim();
  }, [brief, user?.id]);

  if (!brief) {
    if (todayPublished && pubDate && pubItems.length > 0) {
      return (
        <PublishedBriefEditor
          briefDate={pubDate}
          items={pubItems}
          onRefresh={refreshPublished}
        />
      );
    }

    return (
      <div className="flex items-center justify-center min-h-[50vh] text-text-muted">
        <div className="text-center">
          {todayPublished ? (
            <>
              <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-accent-primary/10 flex items-center justify-center">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-primary">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </div>
              <p className="text-lg font-medium text-text-primary">Today&apos;s brief is published</p>
              <p className="text-sm mt-1">No briefs awaiting curation. Check back after the next pipeline run.</p>
            </>
          ) : (
            <>
              <p className="text-lg font-medium">No pending brief</p>
              <p className="text-sm mt-1">The pipeline hasn&apos;t produced a draft yet today.</p>
            </>
          )}
        </div>
      </div>
    );
  }

  const activeBrief = brief;
  const isClaimed = activeBrief.status === "in_review";
  const isMyBrief = activeBrief.claimed_by === user?.id;
  const canEdit = isClaimed && isMyBrief;

  async function handleClaim() {
    setClaiming(true);
    try {
      const res = await fetch("/api/curation/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pending_brief_id: activeBrief.id }),
      });
      if (!res.ok) {
        autoClaimAttemptedForBrief.current = null;
      }
      await refresh();
    } catch (error) {
      console.error(error);
      autoClaimAttemptedForBrief.current = null;
      await refresh();
    } finally {
      setClaiming(false);
    }
  }

  async function handleToggleSelect(item: CurationItem) {
    const nextSelected = !item.selected;
    const optimisticOrder =
      nextSelected && item.curation_order == null ? nextLocalCurationOrder(items) : item.curation_order;

    setItems((current) =>
      current.map((entry) =>
        entry.kind === item.kind && entry.id === item.id
          ? {
              ...entry,
              selected: nextSelected,
              curation_order: nextSelected ? optimisticOrder : null,
            }
          : entry
      )
    );

    try {
      const res = await fetch(`/api/curation/items/${item.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: item.kind,
          selected: nextSelected,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to update selection");
      }
      if (data.item) {
        setItems((current) => replaceItem(current, data.item as CurationItem));
      }
    } catch (error) {
      console.error(error);
      await refresh();
      alert("Failed to update selection. Please try again.");
    }
  }

  async function handleEdit(item: CurationItem, fields: Record<string, unknown>) {
    const res = await fetch(`/api/curation/items/${item.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: item.kind, ...fields }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Failed to save item");
    }
    if (data.item) {
      setItems((current) => replaceItem(current, data.item as CurationItem));
    } else {
      await refresh();
    }
  }

  async function handleReorder(orderedItems: Array<{ id: string; kind: CurationItem["kind"] }>) {
    setItems((current) =>
      current.map((item) => {
        const index = orderedItems.findIndex(
          (ordered) => ordered.id === item.id && ordered.kind === item.kind
        );
        return index === -1 ? item : { ...item, curation_order: index + 1 };
      })
    );

    const res = await fetch("/api/curation/items/reorder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pending_brief_id: activeBrief.id,
          ordered_items: orderedItems,
        }),
      });

    if (!res.ok) {
      await refresh();
      const data = await res.json().catch(() => ({}));
      alert(`Failed to save order: ${data.error ?? "unknown error"}`);
    }
  }

  function handleProceedToOrder() {
    if (selectedCount > 15) {
      alert(`Brief can have at most 15 items (currently ${selectedCount} selected)`);
      return;
    }
    setPhase("order");
  }

  async function handleApprove() {
    setApproving(true);
    try {
      const res = await fetch("/api/curation/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pending_brief_id: activeBrief.id,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setPublishResult({
          briefDate: activeBrief.brief_date,
          itemCount: data.item_count,
          audioDispatched: data.audio_dispatched ?? false,
        });
        setPhase("published");
      } else {
        alert(`Failed to publish: ${data.error}`);
      }
    } finally {
      setApproving(false);
    }
  }

  const briefDate = new Date(`${activeBrief.brief_date}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  if (phase === "order") {
    const selectedItems = sortSelectedItemsForOrdering(items);
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold">Brief Curation</h1>
            <p className="text-sm text-text-muted mt-0.5">{briefDate}</p>
          </div>
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-accent-primary/10 text-accent-primary">
            Ordering
          </span>
        </div>
        <OrderingScreen
          items={selectedItems}
          approving={approving}
          onApprove={handleApprove}
          onReorder={handleReorder}
          onBack={() => setPhase("select")}
        />
      </div>
    );
  }

  if (phase === "published" && publishResult) {
    const formattedDate = new Date(`${publishResult.briefDate}T00:00:00`).toLocaleDateString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    return (
      <div className="max-w-lg mx-auto flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
        <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mb-6">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="#22c55e" strokeWidth="3">
            <path d="M8 16l6 6 10-10" />
          </svg>
        </div>
        <h1 className="text-2xl font-semibold mb-2">Brief Published</h1>
        <p className="text-text-muted mb-1">{formattedDate}</p>
        <p className="text-sm text-text-muted mb-2">
          {publishResult.itemCount} items published.
        </p>
        {publishResult.audioDispatched ? (
          <div className="mb-6 w-full max-w-sm">
            <AudioStatusBanner
              initialStatus="pending"
              briefDate={publishResult.briefDate}
            />
          </div>
        ) : (
          <p className="text-sm text-text-muted mb-6">
            Audio generation was not dispatched.
          </p>
        )}
        <div className="flex gap-3">
          <a
            href={`/brief/${publishResult.briefDate}`}
            className="px-5 py-2.5 rounded-lg bg-accent-primary text-white text-sm font-medium hover:bg-accent-primary/90"
          >
            View Published Brief
          </a>
          <Link
            href="/curation"
            className="px-5 py-2.5 rounded-lg border border-border-secondary text-sm text-text-muted hover:text-text-primary"
          >
            Return to Curation
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Brief Curation</h1>
          <p className="text-sm text-text-muted mt-0.5">{briefDate}</p>
          <p className="text-xs text-text-muted mt-1">
            {items.length} candidates, {selectedCount} selected
            {activeBrief.published_at && (
              <span className="ml-2">
                &middot; Published{" "}
                {new Date(activeBrief.published_at).toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                  hour12: true,
                })}
              </span>
            )}
            {!activeBrief.published_at && activeBrief.created_at && (
              <span className="ml-2">
                &middot; Pipeline ran{" "}
                {new Date(activeBrief.created_at).toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                  hour12: true,
                })}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "px-2 py-0.5 rounded text-xs font-medium",
              activeBrief.status === "pending"
                ? "bg-amber-500/10 text-amber-400"
                : activeBrief.status === "in_review"
                  ? "bg-accent-primary/10 text-accent-primary"
                  : "bg-green-500/10 text-green-400"
            )}
          >
            {activeBrief.status === "pending"
              ? "Pending"
              : activeBrief.status === "in_review"
                ? "In Review"
                : "Published"}
          </span>
        </div>
      </div>

      {canEdit && (
        <QueuedEntriesBanner
          briefDate={activeBrief.brief_date}
          pendingBriefId={activeBrief.id}
          onImported={refresh}
        />
      )}

      {/* Section tabs — only one section visible at a time. Tab shows
          selected/total count so the analyst can eyeball section balance. */}
      {groupedItems.length > 0 && (
        <div className="flex items-center gap-1 mb-4 border-b border-border-secondary">
          {groupedItems.map((group) => {
            const groupSelected = group.items.filter((i) => i.selected).length;
            const isActive = group.section === activeGroup?.section;
            return (
              <button
                key={group.section}
                onClick={() => setActiveSection(group.section)}
                className={cn(
                  "px-3 py-2 text-xs font-medium uppercase tracking-[0.1em] border-b-2 -mb-px transition-colors",
                  isActive
                    ? "border-accent-primary text-text-primary"
                    : "border-transparent text-text-muted hover:text-text-primary"
                )}
              >
                <span>{group.section}</span>
                <span
                  className={cn(
                    "ml-2 tabular-nums text-[11px]",
                    isActive ? "text-accent-primary" : "text-text-muted"
                  )}
                >
                  {groupSelected}/{group.items.length}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {canEdit ? (
        activeGroup ? (
          activeGroup.items.length > 0 ? (
            <ItemSlate
              items={activeGroup.items}
              onToggleSelect={handleToggleSelect}
              onEdit={handleEdit}
            />
          ) : (
            <div className="rounded-lg border border-dashed border-border-secondary p-8 text-center text-text-muted text-sm">
              No relevant items today.
            </div>
          )
        ) : (
          <div className="rounded-lg border border-dashed border-border-secondary p-8 text-center text-text-muted text-sm">
            No candidate items yet.
          </div>
        )
      ) : (
        <div className="space-y-2">
          {claiming && activeBrief.status === "pending" ? (
            <div className="rounded-lg border border-border-secondary bg-surface-secondary p-4 text-sm text-text-muted">
              Opening draft...
            </div>
          ) : null}
          {activeGroup && activeGroup.items.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border-secondary p-8 text-center text-text-muted text-sm">
              No relevant items today.
            </div>
          ) : null}
          {(activeGroup?.items ?? []).map((item) => (
            <div
              key={`${item.kind}-${item.id}`}
              className="rounded-lg border border-border-primary bg-surface-secondary p-4"
            >
              <div className="flex items-center gap-2 mb-1">
                <p className="text-xs text-text-muted">{item.source_name}</p>
                {item.kind === "manual" && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">
                    Manual
                  </span>
                )}
              </div>
              <h3 className="font-medium text-sm">{item.headline}</h3>
              {(item.key_bullets?.length ? item.key_bullets[0] : item.main_bullet) && (
                <p className="text-xs text-text-muted mt-1 line-clamp-2">
                  {item.key_bullets?.length
                    ? item.key_bullets[0]
                    : item.main_bullet?.replace(/\*\*/g, "")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {canEdit && (
        <div className="sticky bottom-0 z-40 bg-surface-primary border-t border-border-secondary py-4 mt-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowManualAdd(true)}
              className="px-3 py-1.5 rounded border border-border-secondary text-sm text-text-muted hover:text-text-primary"
            >
              + Add Item
            </button>
            <span
              className={cn(
                "text-xs tabular-nums",
                selectedCount <= 15
                  ? "text-green-400"
                  : "text-sig-high"
              )}
            >
              {selectedCount} selected (
              {selectedCount > 15
                ? `remove ${selectedCount - 15}`
                : "ready"}
              )
            </span>
          </div>
          <button
            onClick={handleProceedToOrder}
            disabled={selectedCount > 15}
            className="px-6 py-2 rounded bg-accent-primary text-white text-sm font-medium hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next: Review Order
          </button>
        </div>
      )}

      {/* PHASE 1 (drop visibility): surface every dropped candidate to the
          curator. Previously, triage / previous-brief overlap / Gatekeeper
          implicit drops were silently lost. */}
      <FilteredCandidatesPanel briefDate={activeBrief.brief_date} />

      {showManualAdd && (
        <ManualAddDialog
          pendingBriefId={activeBrief.id}
          onClose={() => setShowManualAdd(false)}
          onAdded={refresh}
        />
      )}
    </div>
  );
}
