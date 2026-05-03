import { NextRequest, NextResponse } from "next/server";
import { revalidatePath } from "next/cache";
import {
  getCurationClient,
  requireClaimedBriefAccess,
} from "@/lib/api/curation-helpers";

const MAX_ITEMS = 15;
type ServiceSupabase = Awaited<ReturnType<typeof getCurationClient>>["supabase"];
type DatabaseRow = Record<string, unknown>;

function compareByOrder(
  a: Record<string, unknown>,
  b: Record<string, unknown>
) {
  const orderA = Number(a.curation_order ?? Number.MAX_SAFE_INTEGER);
  const orderB = Number(b.curation_order ?? Number.MAX_SAFE_INTEGER);
  if (orderA !== orderB) return orderA - orderB;
  return String(a.headline ?? "").localeCompare(String(b.headline ?? ""));
}

async function rollbackPublishedBrief(
  supabase: ServiceSupabase,
  briefDate: string,
  previousBriefRow: DatabaseRow | null,
  previousItemRows: DatabaseRow[]
) {
  const { error: deleteItemsError } = await supabase
    .from("brief_items")
    .delete()
    .eq("brief_date", briefDate);
  if (deleteItemsError) {
    console.error("[curation/approve] rollback brief_items delete failed:", deleteItemsError);
  }

  if (previousItemRows.length > 0) {
    const { error: restoreItemsError } = await supabase
      .from("brief_items")
      .insert(previousItemRows);
    if (restoreItemsError) {
      console.error("[curation/approve] rollback brief_items restore failed:", restoreItemsError);
    }
  }

  if (previousBriefRow) {
    const { error: restoreBriefError } = await supabase
      .from("briefs")
      .upsert(previousBriefRow, { onConflict: "brief_date" });
    if (restoreBriefError) {
      console.error("[curation/approve] rollback brief restore failed:", restoreBriefError);
    }
    return;
  }

  const { error: deleteBriefError } = await supabase
    .from("briefs")
    .delete()
    .eq("brief_date", briefDate);
  if (deleteBriefError) {
    console.error("[curation/approve] rollback brief delete failed:", deleteBriefError);
  }
}

function buildProposedItem(item: Record<string, unknown>, rank: number) {
  const raw = (item.raw_item as Record<string, unknown>) ?? {};
  return {
    ...raw,
    id: item.item_id,
    rank,
    section: item.section,
    headline: item.headline,
    main_bullet: item.main_bullet ?? "",
    context: item.context ?? null,
    implication: item.implication ?? null,
    source_name: item.source_name,
    source_url: item.source_url,
    composite_score: Number(item.composite_score ?? 0),
    significance_level: item.significance_level ?? "medium",
    depth: item.depth ?? "standard",
    is_model_release: Boolean(item.is_model_release),
    model_release_data: item.model_release_data ?? null,
    key_bullets: item.key_bullets ?? raw.key_bullets ?? null,
    analysis: item.analysis ?? raw.analysis ?? null,
    primary_entity: item.primary_entity ?? raw.primary_entity ?? null,
    primary_entity_category: item.primary_entity_category ?? raw.primary_entity_category ?? null,
    exhibits: item.exhibits ?? raw.exhibits ?? null,
  };
}

function buildManualItem(item: Record<string, unknown>, rank: number) {
  const raw = (item.raw_item as Record<string, unknown>) ?? {};
  return {
    ...raw,
    id: item.item_id,
    rank,
    section: item.section,
    headline: item.headline,
    main_bullet: item.main_bullet ?? "",
    context: item.context ?? null,
    implication: item.implication ?? null,
    source_name: item.source_name ?? "Manual Entry",
    source_url: item.source_url ?? null,
    source_domain: raw.source_domain ?? null,
    additional_sources: raw.additional_sources ?? [],
    entities: raw.entities ?? [],
    composite_score: Number(item.composite_score ?? 8),
    significance_level: item.significance_level ?? "medium",
    depth: item.depth ?? "standard",
    is_model_release: Boolean(item.is_model_release),
    model_release_data: item.model_release_data ?? null,
    cluster: raw.cluster ?? null,
    continuity: raw.continuity ?? null,
    key_bullets: item.key_bullets ?? raw.key_bullets ?? null,
    analysis: item.analysis ?? raw.analysis ?? null,
    primary_entity: item.primary_entity ?? raw.primary_entity ?? null,
    primary_entity_category: item.primary_entity_category ?? raw.primary_entity_category ?? null,
    exhibits: item.exhibits ?? raw.exhibits ?? null,
  };
}

export async function POST(request: NextRequest) {
  const { supabase, user } = await getCurationClient();
  const { pending_brief_id } = await request.json();

  if (!pending_brief_id) {
    return NextResponse.json({ error: "Missing pending_brief_id" }, { status: 400 });
  }

  const brief = await requireClaimedBriefAccess(supabase, user.id, pending_brief_id);
  const now = new Date().toISOString();
  const briefDate = brief.brief_date;

  const [
    { data: pendingRows, error: pendingError },
    { data: manualRows, error: manualError },
  ] = await Promise.all([
    supabase
      .from("pending_items")
      .select("*")
      .eq("pending_brief_id", pending_brief_id)
      .eq("selected", true),
    supabase
      .from("manual_items")
      .select("*")
      .eq("pending_brief_id", pending_brief_id)
      .eq("selected", true),
  ]);

  if (pendingError || manualError) {
    return NextResponse.json(
      {
        error:
          pendingError?.message ??
          manualError?.message ??
          "Failed to load selected brief items",
      },
      { status: 500 }
    );
  }

  const orderedPending = ((pendingRows ?? []) as Record<string, unknown>[]).sort(compareByOrder);
  const orderedManual = ((manualRows ?? []) as Record<string, unknown>[]).sort(compareByOrder);
  const orderedItems = [...orderedPending, ...orderedManual].sort(compareByOrder);
  const totalItems = orderedItems.length;

  if (totalItems > MAX_ITEMS) {
    return NextResponse.json(
      { error: `Brief can have at most ${MAX_ITEMS} items (currently ${totalItems})` },
      { status: 400 }
    );
  }

  const finalItems = orderedItems.map((item, index) =>
    "tier" in item ? buildProposedItem(item, index + 1) : buildManualItem(item, index + 1)
  );

  const sectionCounts: Record<string, number> = {};
  for (const item of finalItems) {
    const section = String(item.section ?? "");
    sectionCounts[section] = (sectionCounts[section] ?? 0) + 1;
  }

  const finalBrief = {
    brief_metadata: {
      date: briefDate,
      generated_at: now,
      total_items: finalItems.length,
      section_counts: sectionCounts,
      lead_story_id: String(finalItems[0]?.id ?? ""),
    },
    items: finalItems,
  };

  const stats = (brief.pipeline_stats as Record<string, unknown>) ?? {};
  const briefRow = {
    brief_date: briefDate,
    generated_at: now,
    item_count: finalItems.length,
    sources_consulted: 0,
    items_reviewed: 0,
    pipeline_cost_usd: Number(stats.total_cost_usd ?? 0),
    raw_json: finalBrief,
    executive_summary: null,
    metadata: {
      lead_story_id: finalBrief.brief_metadata.lead_story_id,
      section_counts: sectionCounts,
      curated_by: user.id,
    },
  };

  const [
    { data: previousBrief, error: previousBriefError },
    { data: previousItemRows, error: previousItemsError },
  ] = await Promise.all([
    supabase
      .from("briefs")
      .select("*")
      .eq("brief_date", briefDate)
      .maybeSingle(),
    supabase
      .from("brief_items")
      .select("*")
      .eq("brief_date", briefDate),
  ]);

  if (previousBriefError) {
    return NextResponse.json(
      { error: `Failed to snapshot existing brief: ${previousBriefError.message}` },
      { status: 500 }
    );
  }
  if (previousItemsError) {
    return NextResponse.json(
      { error: `Failed to snapshot existing items: ${previousItemsError.message}` },
      { status: 500 }
    );
  }

  const { error: briefErr } = await supabase
    .from("briefs")
    .upsert(briefRow, { onConflict: "brief_date" });
  if (briefErr) {
    return NextResponse.json({ error: `Failed to write brief: ${briefErr.message}` }, { status: 500 });
  }

  const { error: deleteItemsError } = await supabase
    .from("brief_items")
    .delete()
    .eq("brief_date", briefDate);
  if (deleteItemsError) {
    await rollbackPublishedBrief(
      supabase,
      briefDate,
      (previousBrief as DatabaseRow | null) ?? null,
      ((previousItemRows ?? []) as DatabaseRow[])
    );
    return NextResponse.json(
      { error: `Failed to replace existing items: ${deleteItemsError.message}` },
      { status: 500 }
    );
  }

  const seenItemIds = new Set<string>();
  const itemRows = finalItems
    .filter((item) => item.depth !== "placeholder")
    .filter((item) => {
      const id = String(item.id);
      if (seenItemIds.has(id)) return false;
      seenItemIds.add(id);
      return true;
    })
    .map((item, idx) => {
      const continuity = (item as Record<string, unknown>).continuity;
      // brief_items is a narrow cross-date index. Full item content lives
      // in briefs.raw_json (source of truth for the reader). Columns for
      // key_bullets/analysis/exhibits/primary_entity* and the always-null
      // geo/topic_relevance/news_significance placeholders were dropped
      // in migration 018; raw_content is retained on brief_items for
      // historical audit of pre-v2 briefs but not written by this path.
      return {
        brief_date: briefDate,
        item_id: String(item.id),
        section: String(item.section),
        section_order: idx + 1,
        headline: String(item.headline),
        main_bullet: String(item.main_bullet ?? ""),
        context: (item.context as string | null) ?? null,
        implication: (item.implication as string | null) ?? null,
        source_name: (item.source_name as string | null) ?? null,
        source_url: (item.source_url as string | null) ?? null,
        significance: (item.significance_level as string | null) ?? null,
        composite_score: Number(item.composite_score ?? 0),
        is_continuity: continuity != null,
        continuity_days: continuity != null ? 1 : 0,
      };
    });

  if (itemRows.length > 0) {
    const { error: itemsErr } = await supabase.from("brief_items").insert(itemRows);
    if (itemsErr) {
      await rollbackPublishedBrief(
        supabase,
        briefDate,
        (previousBrief as DatabaseRow | null) ?? null,
        ((previousItemRows ?? []) as DatabaseRow[])
      );
      return NextResponse.json({ error: `Failed to write items: ${itemsErr.message}` }, { status: 500 });
    }
  }

  const { error: publishStateError } = await supabase
    .from("pending_briefs")
    .update({
      status: "published",
      approved_at: now,
      published_at: now,
      updated_at: now,
    })
    .eq("id", pending_brief_id);

  if (publishStateError) {
    await rollbackPublishedBrief(
      supabase,
      briefDate,
      (previousBrief as DatabaseRow | null) ?? null,
      ((previousItemRows ?? []) as DatabaseRow[])
    );
    return NextResponse.json(
      { error: `Failed to finalize publish state: ${publishStateError.message}` },
      { status: 500 }
    );
  }

  revalidatePath("/brief/today");
  revalidatePath(`/brief/${briefDate}`);
  revalidatePath("/brief/[date]");

  let audioDispatched = false;
  const ghToken = process.env.GITHUB_PAT;
  if (ghToken) {
    try {
      const dispatchRes = await fetch(
        "https://api.github.com/repos/bvahdat38/MBZUAI-Intelligence-Brief/actions/workflows/generate-audio.yml/dispatches",
        {
          method: "POST",
          headers: {
            Authorization: `token ${ghToken}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ ref: "main", inputs: { brief_date: briefDate } }),
        }
      );
      audioDispatched = dispatchRes.status === 204;
      if (audioDispatched) {
        await supabase
          .from("briefs")
          .update({ audio_status: "pending" })
          .eq("brief_date", briefDate);
      } else {
        console.error(
          `[curation/approve] Audio dispatch failed: HTTP ${dispatchRes.status}`,
          await dispatchRes.text().catch(() => "")
        );
      }
    } catch (err) {
      console.error("[curation/approve] Audio dispatch error:", err);
    }
  } else {
    console.warn("[curation/approve] GITHUB_PAT not set — audio generation skipped");
  }

  return NextResponse.json({
    ok: true,
    brief_date: briefDate,
    item_count: finalItems.length,
    audio_dispatched: audioDispatched,
  });
}
