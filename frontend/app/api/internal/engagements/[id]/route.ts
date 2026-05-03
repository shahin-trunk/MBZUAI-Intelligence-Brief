import { type NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { DOSSIER_GENERATION_PROMPT } from "@/lib/prompts/engagement-dossier";
import { extractDossierJson } from "@/lib/prompts/extract-dossier-json";

/**
 * PATCH /api/internal/engagements/[id]
 *
 * Admin-only. Partial update of an engagement. If `regenerate: true`
 * is in the body, re-runs Sonnet dossier generation.
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await params;

    const body = await request.json();
    const { regenerate, ...fields } = body;

    // If regenerating, call Sonnet again
    if (regenerate) {
      // Fetch current engagement for context
      const { data: eng, error: fetchErr } = await supabase
        .from("engagements")
        .select("visitor_name, visitor_title, visitor_organization")
        .eq("id", id)
        .single();

      if (fetchErr || !eng) {
        return jsonError("Engagement not found", 404);
      }

      const name = fields.visitor_name || eng.visitor_name;
      const title = fields.visitor_title || eng.visitor_title;
      const org = fields.visitor_organization || eng.visitor_organization;

      const anthropic = new Anthropic();
      const completion = await anthropic.messages.create({
        model: "claude-sonnet-4-6",
        max_tokens: 16384,
        tools: [
          { type: "web_search_20250305", name: "web_search", max_uses: 5 },
        ],
        system: DOSSIER_GENERATION_PROMPT,
        messages: [
          {
            role: "user",
            content: `Generate an engagement dossier for:\nName: ${name}\nTitle: ${title}\nOrganization: ${org || "Not specified"}\n\nThe meeting is at MBZUAI (Mohamed bin Zayed University of Artificial Intelligence) in Abu Dhabi. MBZUAI is an AI-focused research university with strengths in foundation models, computer vision, NLP, machine learning, and robotics. It operates significant GPU compute infrastructure and has strategic pillars in responsible AI and healthcare AI.`,
          },
        ],
      });

      if (completion.stop_reason === "max_tokens") {
        return jsonError("Dossier response was truncated (max tokens reached). Please try again.", 422);
      }

      const textBlocks = completion.content.filter(
        (b): b is Anthropic.TextBlock => b.type === "text"
      );
      const lastText = textBlocks[textBlocks.length - 1]?.text || "";

      try {
        const dossier = extractDossierJson(lastText);

        fields.bio_concise_cv = dossier.bio.concise.cv;
        fields.bio_concise_narrative = dossier.bio.concise.narrative;
        fields.bio_extended_cv = dossier.bio.extended.cv;
        fields.bio_extended_narrative = dossier.bio.extended.narrative;
        fields.research_chips = dossier.research_chips || [];
        // Backward compat
        fields.bio = dossier.bio.concise.narrative;
        fields.bio_facts = {
          current_roles: dossier.bio.extended.cv.current.map((c) => ({ org: c.org, role: c.role })),
          previous_roles: (dossier.bio.extended.cv.previous || []).map((p) => ({
            org: p.org, role: p.role, years: p.dates || "",
          })),
          recognition: dossier.bio.extended.cv.recognition || [],
        };

        fields.credential_tags = [];
        fields.mutual_interests = dossier.areas_of_mutual_interest || [];
        fields.suggested_questions = [];
      } catch {
        return jsonError("Failed to parse regenerated dossier", 422);
      }
    }

    // Remove any fields that shouldn't be directly updatable
    delete fields.id;
    delete fields.created_by;
    delete fields.created_at;

    if (Object.keys(fields).length === 0) {
      return jsonError("No fields to update", 400);
    }

    const { data, error } = await supabase
      .from("engagements")
      .update(fields)
      .eq("id", id)
      .select()
      .maybeSingle();

    if (error) {
      console.error("[engagements PATCH] DB update failed:", error);
      return jsonError(`Failed to update engagement: ${error.message}`, 500);
    }
    if (!data) {
      return jsonError("Engagement not found", 404);
    }

    return jsonOk({ engagement: data });
  } catch (err) {
    return handleRouteError(err, "engagements/[id] PATCH");
  }
}

/**
 * DELETE /api/internal/engagements/[id]
 *
 * Admin-only. Deletes an engagement and cascaded followups/requests.
 */
export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { supabase } = await getAdminClient();
    const { id } = await params;

    const { error } = await supabase
      .from("engagements")
      .delete()
      .eq("id", id);

    if (error) {
      console.error("[engagements DELETE] DB delete failed:", error);
      return jsonError(`Failed to delete engagement: ${error.message}`, 500);
    }

    return jsonOk({ deleted: true });
  } catch (err) {
    return handleRouteError(err, "engagements/[id] DELETE");
  }
}
