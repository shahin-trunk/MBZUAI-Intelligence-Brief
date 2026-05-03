import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";
import Anthropic from "@anthropic-ai/sdk";
import {
  getCurationClient,
  requireClaimedBriefAccess,
} from "@/lib/api/curation-helpers";
import {
  buildLegacyTextFields,
  mapManualItem,
  mergeRawItem,
  normalizeExhibits,
  normalizeKeyBullets,
} from "@/lib/curation/items";
import { extractExhibitsFromManualEntryNotes as extractManualEntryExhibits } from "@/lib/curation/manual-entry-metadata";
import {
  MANUAL_GHOSTWRITER_SYSTEM_PROMPT,
  buildManualGhostwriterUserPrompt,
} from "@/lib/curation/manual-ghostwriter-prompt";

/**
 * POST /api/curation/import-entry
 *
 * Imports a queued admin manual_entries row into the curation workflow:
 * 1. Fetches the manual_entries row
 * 2. Generates a brief item via Claude (same logic as generate-item)
 * 3. Creates a manual_items row (same logic as manual-item POST)
 * 4. Marks the manual_entries row as ingested
 */
export async function POST(request: NextRequest) {
  const { supabase, user } = await getCurationClient();
  const { manual_entry_id, pending_brief_id } = await request.json();

  if (!manual_entry_id || !pending_brief_id) {
    return NextResponse.json(
      { error: "Missing required fields: manual_entry_id, pending_brief_id" },
      { status: 400 },
    );
  }

  const brief = await requireClaimedBriefAccess(supabase, user.id, pending_brief_id);

  // 1. Fetch the queued entry
  const { data: entry, error: entryError } = await supabase
    .from("manual_entries")
    .select("*")
    .eq("id", manual_entry_id)
    .eq("status", "pending")
    .single();

  if (entryError || !entry) {
    return NextResponse.json(
      { error: entryError?.message ?? "Queued entry not found or already ingested" },
      { status: 404 },
    );
  }

  // Verify the entry targets this brief's date
  if (entry.target_date !== brief.brief_date) {
    return NextResponse.json(
      { error: "Entry target_date does not match brief date" },
      { status: 400 },
    );
  }

  // 2. Generate brief item via Claude
  const sourceText = (entry.summary || "").trim();
  const sourceUrl = (entry.source_url || "").trim() || null;
  const section = (entry.brief_section || "").trim();

  if (!sourceText && !sourceUrl) {
    return NextResponse.json(
      { error: "Entry has no source text or URL to generate from" },
      { status: 400 },
    );
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "ANTHROPIC_API_KEY not configured" },
      { status: 500 },
    );
  }

  let generated: {
    headline: string;
    primary_entity: string | null;
    key_bullets: string[];
    analysis: string;
  };

  try {
    const client = new Anthropic({ apiKey });
    const userPrompt = buildManualGhostwriterUserPrompt({
      section,
      sourceUrl,
      sourceText: sourceText || entry.headline || "",
    });

    const response = await client.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 1000,
      system: MANUAL_GHOSTWRITER_SYSTEM_PROMPT,
      messages: [{ role: "user", content: userPrompt }],
    });

    const text = response.content[0].type === "text" ? response.content[0].text : "";
    const cleaned = text.replace(/```json\s*/g, "").replace(/```\s*/g, "").trim();
    const parsed = JSON.parse(cleaned);

    generated = {
      headline: typeof parsed.headline === "string" ? parsed.headline : entry.headline || "Untitled",
      primary_entity:
        typeof parsed.primary_entity === "string" && parsed.primary_entity.trim().length > 0
          ? parsed.primary_entity.trim()
          : null,
      key_bullets: Array.isArray(parsed.key_bullets)
        ? parsed.key_bullets
            .map((b: unknown) => (typeof b === "string" ? b.trim() : ""))
            .filter(Boolean)
            .slice(0, 3)
        : [],
      analysis: typeof parsed.analysis === "string" ? parsed.analysis.trim() : "",
    };
  } catch (e) {
    const message = e instanceof Error ? e.message : "AI generation failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  // Use admin-provided headline if AI didn't produce one
  if (!generated.headline && entry.headline) {
    generated.headline = entry.headline;
  }

  // 3. Create manual_items row (mirrors manual-item/route.ts logic)
  const manualRowId = randomUUID();
  const itemId = `manual-${randomUUID().slice(0, 8)}`;
  const legacy = buildLegacyTextFields({
    key_bullets: generated.key_bullets,
    analysis: generated.analysis,
  });
  const insertedAt = new Date().toISOString();

  let derivedSourceName = "Manual Entry";
  if (sourceUrl) {
    try {
      derivedSourceName = new URL(sourceUrl).hostname.replace("www.", "");
    } catch {
      derivedSourceName = sourceUrl;
    }
  }

  const row = {
    id: manualRowId,
    pending_brief_id,
    item_id: itemId,
    section: section || "International Business & Technology",
    headline: generated.headline,
    main_bullet: legacy.main_bullet,
    context: legacy.context,
    implication: legacy.implication,
    source_name: derivedSourceName,
    source_url: sourceUrl,
    composite_score: 8,
    significance_level: "medium",
    key_bullets: normalizeKeyBullets(generated.key_bullets),
    analysis: typeof generated.analysis === "string" ? generated.analysis : null,
    primary_entity: generated.primary_entity,
    exhibits: normalizeExhibits(extractManualEntryExhibits(entry.notes)),
    depth: "standard",
    is_model_release: false,
    model_release_data: null,
    selected: false,
    curation_order: null,
    added_by: user.id,
    created_at: insertedAt,
    updated_at: insertedAt,
  };
  const rawItem = mergeRawItem(row, row);

  const { error: insertError } = await supabase
    .from("manual_items")
    .insert({
      ...row,
      primary_entity_category:
        (rawItem.primary_entity_category as string | null | undefined) ?? null,
      raw_item: rawItem,
    });

  if (insertError) {
    return NextResponse.json({ error: insertError.message }, { status: 500 });
  }

  // Auto-select and assign curation order
  const { error: rpcError } = await supabase.rpc(
    "assign_curation_order",
    {
      p_table: "manual_items",
      p_item_id: manualRowId,
      p_brief_id: pending_brief_id,
    },
  );

  if (rpcError) {
    return NextResponse.json({ error: rpcError.message }, { status: 500 });
  }

  // 4. Mark the queued entry as ingested
  await supabase
    .from("manual_entries")
    .update({ status: "ingested", ingested_at: insertedAt })
    .eq("id", manual_entry_id);

  // Reload and return the created item
  const { data: inserted, error: reloadError } = await supabase
    .from("manual_items")
    .select("*")
    .eq("id", manualRowId)
    .single();

  if (reloadError || !inserted) {
    return NextResponse.json(
      { error: reloadError?.message ?? "Item created but could not be reloaded" },
      { status: 500 },
    );
  }

  // Record curation decision
  await supabase.from("curation_decisions").insert({
    pending_brief_id,
    item_id: inserted.item_id,
    decision: "add",
    final_section: row.section,
    analyst_id: user.id,
  });

  return NextResponse.json({ ok: true, item: mapManualItem(inserted) });
}
