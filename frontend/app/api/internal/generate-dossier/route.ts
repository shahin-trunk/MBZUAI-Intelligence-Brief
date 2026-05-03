import { type NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { jsonOk, jsonError } from "@/lib/api/helpers";
import { DOSSIER_GENERATION_PROMPT } from "@/lib/prompts/engagement-dossier";
import { extractDossierJson } from "@/lib/prompts/extract-dossier-json";
import type { DossierGenerationResult, BioFacts, IntelBriefing } from "@/lib/types/executive-engagement";
import { buildEngagementId } from "@/lib/utils/engagement-id";

/**
 * POST /api/internal/generate-dossier
 *
 * Admin-only. Generates an engagement dossier using Sonnet + web search,
 * then inserts the engagement into Supabase.
 */
export async function POST(request: NextRequest) {
  // Step 1: Auth
  let supabase: Awaited<ReturnType<typeof getAdminClient>>["supabase"];
  let user: Awaited<ReturnType<typeof getAdminClient>>["user"];
  try {
    const auth = await getAdminClient();
    supabase = auth.supabase;
    user = auth.user;
  } catch (err) {
    // getAdminClient throws NextResponse objects for 401/403
    if (err && typeof err === "object" && "status" in err) {
      return err as Response;
    }
    console.error("[generate-dossier] auth failed:", err);
    return jsonError(
      `Auth failed: ${err instanceof Error ? err.message : "unknown error"}`,
      500
    );
  }

  // Step 2: Parse + validate input
  const body = await request.json();
  const {
    visitorName,
    visitorTitle,
    visitorOrganization,
    date,
    time,
    location,
    format,
  } = body;

  if (!visitorName || !date || !time || !format) {
    return jsonError(
      "visitorName, date, time, and format are required",
      400
    );
  }

  const engagementId = buildEngagementId({
    date,
    visitorName,
    time,
    visitorOrganization,
    location,
  });

  // Step 3: Call Anthropic
  let dossier: DossierGenerationResult;
  let lastText = "";

  const anthropic = new Anthropic();
  const userContent = `Generate an engagement dossier for:
Name: ${visitorName}
Title: ${visitorTitle}
Organization: ${visitorOrganization || "Not specified"}

The meeting is at MBZUAI (Mohamed bin Zayed University of Artificial Intelligence) in Abu Dhabi. MBZUAI is an AI-focused research university with strengths in foundation models, computer vision, NLP, machine learning, and robotics. It operates significant GPU compute infrastructure and has strategic pillars in responsible AI and healthcare AI.`;

  try {
    const completion = await anthropic.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 16384,
      tools: [
        {
          type: "web_search_20250305",
          name: "web_search",
          max_uses: 5,
        },
      ],
      system: DOSSIER_GENERATION_PROMPT,
      messages: [{ role: "user", content: userContent }],
    });

    console.log(
      `[generate-dossier] tokens: ${completion.usage.input_tokens} in, ${completion.usage.output_tokens} out, stop: ${completion.stop_reason}`
    );

    if (completion.stop_reason === "max_tokens") {
      return jsonError(
        "Dossier response was truncated (max tokens reached). Please try again.",
        422
      );
    }

    // Extract the final text block (web search may add tool_use/tool_result blocks)
    const textBlocks = completion.content.filter(
      (b): b is Anthropic.TextBlock => b.type === "text"
    );
    lastText = textBlocks[textBlocks.length - 1]?.text || "";

    dossier = extractDossierJson(lastText);

    if (!dossier.bio?.concise?.narrative || !dossier.bio?.extended?.narrative) {
      return jsonError("Dossier response missing required fields (bio.concise.narrative, bio.extended.narrative)", 422);
    }
  } catch (err) {
    console.error("[generate-dossier] Anthropic/parse failed:", err);
    if (err instanceof Anthropic.APIError) {
      return jsonError(`Anthropic API error (${err.status}): ${err.message}`, 502);
    }
    if (err instanceof SyntaxError) {
      console.error("[generate-dossier] Raw text (first 500 chars):", lastText?.slice(0, 500));

      // Retry once: ask the model to return only JSON, no web search
      try {
        console.log("[generate-dossier] Retrying with JSON-only follow-up…");
        const retry = await anthropic.messages.create({
          model: "claude-sonnet-4-6",
          max_tokens: 16384,
          system: DOSSIER_GENERATION_PROMPT,
          messages: [
            { role: "user", content: userContent },
            { role: "assistant", content: lastText },
            {
              role: "user",
              content:
                "Your previous response could not be parsed as JSON. Return ONLY the valid JSON object — no markdown fences, no explanation, no text before or after the JSON.",
            },
          ],
        });

        const retryText =
          retry.content.filter(
            (b): b is Anthropic.TextBlock => b.type === "text"
          ).pop()?.text || "";

        dossier = extractDossierJson(retryText);

        if (!dossier.bio?.concise?.narrative || !dossier.bio?.extended?.narrative) {
          return jsonError("Dossier response missing required fields after retry", 422);
        }
      } catch (retryErr) {
        console.error("[generate-dossier] Retry also failed:", retryErr);
        return jsonError("Failed to parse dossier JSON from model response", 422);
      }
    } else {
      return jsonError(
        `Dossier generation failed: ${err instanceof Error ? err.message : String(err)}`,
        500
      );
    }
  }

  // Step 4: Insert into Supabase
  // Build backward-compat bio_facts from extended CV data
  const bioFacts: BioFacts = {
    current_roles: dossier.bio.extended.cv.current.map((c) => ({ org: c.org, role: c.role })),
    previous_roles: (dossier.bio.extended.cv.previous || []).map((p) => ({
      org: p.org,
      role: p.role,
      years: p.dates || "",
    })),
    recognition: dossier.bio.extended.cv.recognition || [],
  };

  const row = {
    id: engagementId,
    visitor_name: visitorName,
    visitor_title: visitorTitle,
    visitor_organization: visitorOrganization || "",
    date,
    time,
    location: location || "",
    format,
    // Backward compat fields
    bio: dossier.bio.concise.narrative,
    bio_facts: bioFacts,
    credential_tags: [],
    // New dual-bio fields
    bio_concise_cv: dossier.bio.concise.cv,
    bio_concise_narrative: dossier.bio.concise.narrative,
    bio_extended_cv: dossier.bio.extended.cv,
    bio_extended_narrative: dossier.bio.extended.narrative,
    research_chips: dossier.research_chips || [],
    intel_briefings: (dossier.intel_questions || []).map((iq) => ({
      id: iq.id,
      topic: iq.topic,
      question: iq.question,
      answer: "",
      detail: null,
      status: "pending",
    } satisfies IntelBriefing)),
    mutual_interests: dossier.areas_of_mutual_interest || [],
    suggested_questions: [],
    materials: [],
    created_by: user.id,
  };

  const { data, error } = await supabase
    .from("engagements")
    .upsert(row, { onConflict: "id" })
    .select()
    .single();

  if (error) {
    console.error("[generate-dossier] DB insert failed:", error);
    return jsonError(`DB insert failed: ${error.message}`, 500);
  }

  // Fire-and-forget: generate intel briefing answers in background (Phase 2)
  const hasPendingBriefings = (dossier.intel_questions || []).length > 0;
  if (hasPendingBriefings) {
    const baseUrl = request.nextUrl.origin;
    fetch(`${baseUrl}/api/internal/generate-intel-briefings`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Cookie: request.headers.get("cookie") || "",
      },
      body: JSON.stringify({ engagementId }),
    }).catch((err) =>
      console.error("[generate-dossier] Failed to trigger intel briefings:", err)
    );
  }

  return jsonOk({ engagement: data }, 201);
}
