import { type NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { getAuthenticatedClient } from "@/lib/api/helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { FOLLOWUP_SEARCH_PROMPT } from "@/lib/prompts/engagement-followup";

/**
 * POST /api/internal/engagement-followup
 *
 * Any authenticated user. Answers a follow-up question about
 * an engagement visitor using Sonnet + web search.
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase, user } = await getAuthenticatedClient();

    const body = await request.json();
    const { engagementId, question } = body;

    if (!engagementId || !question?.trim()) {
      return jsonError("engagementId and question are required", 400);
    }

    if (question.length > 500) {
      return jsonError("Question must be under 500 characters", 400);
    }

    // Fetch engagement for context
    const { data: engagement, error: fetchErr } = await supabase
      .from("engagements")
      .select(
        "visitor_name, visitor_title, visitor_organization, bio, credential_tags, mutual_interests"
      )
      .eq("id", engagementId)
      .single();

    if (fetchErr || !engagement) {
      return jsonError("Engagement not found", 404);
    }

    // Call Sonnet 4.6 with web search
    const anthropic = new Anthropic();

    const completion = await anthropic.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 2048,
      tools: [
        {
          type: "web_search_20250305",
          name: "web_search",
          max_uses: 3,
        },
      ],
      system: FOLLOWUP_SEARCH_PROMPT,
      messages: [
        {
          role: "user",
          content: `Context: The president of MBZUAI is preparing for a meeting with ${engagement.visitor_name} (${engagement.visitor_title}, ${engagement.visitor_organization}).

Bio: ${engagement.bio || "No bio available."}

Question: ${question.trim()}`,
        },
      ],
    });

    console.log(
      `[engagement-followup] tokens: ${completion.usage.input_tokens} in, ${completion.usage.output_tokens} out`
    );

    // Extract the final text block
    const textBlocks = completion.content.filter(
      (b): b is Anthropic.TextBlock => b.type === "text"
    );
    const lastText = textBlocks[textBlocks.length - 1]?.text || "";

    let result: { answer: string; detail: string | null };
    try {
      // Strip markdown fences and try JSON parse
      const clean = lastText.replace(/```json\n?|```\n?/g, "").trim();
      // Try to extract JSON object from anywhere in the text
      const jsonMatch = clean.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        result = JSON.parse(jsonMatch[0]);
      } else {
        throw new Error("No JSON object found");
      }
    } catch {
      // Fallback: use the raw text as the answer if JSON parsing fails
      console.warn(
        "[engagement-followup] JSON parse failed, using raw text. First 300 chars:",
        lastText.slice(0, 300)
      );
      result = {
        answer: lastText.trim() || "No answer available.",
        detail: null,
      };
    }

    // Save to engagement_followups
    const { data, error } = await supabase
      .from("engagement_followups")
      .insert({
        engagement_id: engagementId,
        question: question.trim(),
        answer: result.answer || "No answer available.",
        detail: result.detail || null,
        asked_by: user.id,
      })
      .select()
      .single();

    if (error) {
      console.error("[engagement-followup] DB insert failed:", error);
      return jsonError("Failed to save follow-up", 500);
    }

    return jsonOk({ followup: data }, 201);
  } catch (err) {
    return handleRouteError(err, "engagement-followup POST");
  }
}
