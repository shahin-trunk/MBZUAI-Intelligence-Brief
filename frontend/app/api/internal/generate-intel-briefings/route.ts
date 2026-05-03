import { type NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { getAdminClient } from "@/lib/api/admin-helpers";
import { handleRouteError, jsonOk, jsonError } from "@/lib/api/helpers";
import { INTEL_BRIEFING_ANSWER_PROMPT } from "@/lib/prompts/intel-briefing";
import type { IntelBriefing } from "@/lib/types/executive-engagement";

/**
 * POST /api/internal/generate-intel-briefings
 *
 * Generates answers for all pending intel briefing cards on an engagement.
 * Runs 4-6 parallel Sonnet + web search calls.
 */
export async function POST(request: NextRequest) {
  try {
    const { supabase } = await getAdminClient();

    const body = await request.json();
    const { engagementId } = body;

    if (!engagementId) {
      return jsonError("engagementId is required", 400);
    }

    // Fetch engagement
    const { data: engagement, error: fetchErr } = await supabase
      .from("engagements")
      .select(
        "intel_briefings, visitor_name, visitor_title, visitor_organization, bio"
      )
      .eq("id", engagementId)
      .single();

    if (fetchErr || !engagement) {
      return jsonError("Engagement not found", 404);
    }

    const briefings: IntelBriefing[] = engagement.intel_briefings || [];
    const pending = briefings.filter((b) => b.status === "pending");

    if (pending.length === 0) {
      return jsonOk({ briefings, message: "No pending briefings" });
    }

    const anthropic = new Anthropic();

    // Fire all pending questions in parallel
    const results = await Promise.allSettled(
      pending.map(async (briefing) => {
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
          system: INTEL_BRIEFING_ANSWER_PROMPT,
          messages: [
            {
              role: "user",
              content: `Context: The president of MBZUAI is preparing for a meeting with ${engagement.visitor_name} (${engagement.visitor_title || ""}${engagement.visitor_organization ? `, ${engagement.visitor_organization}` : ""}).

Question: ${briefing.question}`,
            },
          ],
        });

        console.log(
          `[intel-briefing] ${briefing.id} tokens: ${completion.usage.input_tokens} in, ${completion.usage.output_tokens} out`
        );

        // Extract final text block
        const textBlocks = completion.content.filter(
          (b): b is Anthropic.TextBlock => b.type === "text"
        );
        const lastText = textBlocks[textBlocks.length - 1]?.text || "";

        let result: { answer: string; detail: string | null };
        try {
          const clean = lastText.replace(/```json\n?|```\n?/g, "").trim();
          const jsonMatch = clean.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            result = JSON.parse(jsonMatch[0]);
          } else {
            throw new Error("No JSON object found");
          }
        } catch {
          console.warn(
            `[intel-briefing] ${briefing.id} JSON parse failed, using raw text`
          );
          result = {
            answer: lastText.trim() || "No answer available.",
            detail: null,
          };
        }

        return { id: briefing.id, ...result };
      })
    );

    // Merge results back into briefings array
    const updatedBriefings = briefings.map((b) => {
      if (b.status !== "pending") return b;

      const resultEntry = results.find((r, i) => pending[i].id === b.id);
      if (!resultEntry) return b;

      if (resultEntry.status === "fulfilled") {
        return {
          ...b,
          answer: resultEntry.value.answer,
          detail: resultEntry.value.detail,
          status: "ready" as const,
        };
      } else {
        console.error(
          `[intel-briefing] ${b.id} failed:`,
          resultEntry.reason
        );
        return {
          ...b,
          answer: "Could not research this topic.",
          detail: null,
          status: "error" as const,
        };
      }
    });

    // Update DB
    const { error: updateErr } = await supabase
      .from("engagements")
      .update({ intel_briefings: updatedBriefings })
      .eq("id", engagementId);

    if (updateErr) {
      console.error("[intel-briefing] DB update failed:", updateErr);
      return jsonError("Failed to save intel briefings", 500);
    }

    console.log(
      `[intel-briefing] Completed ${results.filter((r) => r.status === "fulfilled").length}/${results.length} briefings for ${engagementId}`
    );

    return jsonOk({ briefings: updatedBriefings });
  } catch (err) {
    return handleRouteError(err, "generate-intel-briefings POST");
  }
}
