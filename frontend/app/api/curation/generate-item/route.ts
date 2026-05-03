import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { getCurationClient } from "@/lib/api/curation-helpers";
import {
  MANUAL_GHOSTWRITER_SYSTEM_PROMPT,
  buildManualGhostwriterUserPrompt,
} from "@/lib/curation/manual-ghostwriter-prompt";

export async function POST(request: NextRequest) {
  await getCurationClient(); // Auth check

  const { source_url, source_text, section } = await request.json();

  if (!source_text?.trim()) {
    return NextResponse.json(
      { error: "Source text is required" },
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

  const client = new Anthropic({ apiKey });

  const userPrompt = buildManualGhostwriterUserPrompt({
    section,
    sourceUrl: source_url,
    sourceText: source_text,
  });

  try {
    const response = await client.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 1000,
      system: MANUAL_GHOSTWRITER_SYSTEM_PROMPT,
      messages: [{ role: "user", content: userPrompt }],
    });

    const text = response.content[0].type === "text" ? response.content[0].text : "";
    const cleaned = text.replace(/```json\s*/g, "").replace(/```\s*/g, "").trim();
    const generated = JSON.parse(cleaned);

    return NextResponse.json({
      generated: {
        headline: generated.headline,
        primary_entity:
          typeof generated.primary_entity === "string" && generated.primary_entity.trim().length > 0
            ? generated.primary_entity.trim()
            : null,
        key_bullets: Array.isArray(generated.key_bullets)
          ? generated.key_bullets
              .map((bullet: unknown) => (typeof bullet === "string" ? bullet.trim() : ""))
              .filter(Boolean)
              .slice(0, 3)
          : [],
        analysis:
          typeof generated.analysis === "string" ? generated.analysis.trim() : "",
      },
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Generation failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
