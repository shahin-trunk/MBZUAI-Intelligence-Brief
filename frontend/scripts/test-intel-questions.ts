#!/usr/bin/env npx tsx
/**
 * Test intel question generation quality without full dossier pipeline.
 *
 * Usage: npx tsx frontend/scripts/test-intel-questions.ts
 *
 * Tests the prompt rules against 3 sample visitors and checks
 * that questions are short (8-15 words), single-concept, and scannable.
 */

import Anthropic from "@anthropic-ai/sdk";
import { config } from "dotenv";
import { resolve } from "path";

// Load .env.local from frontend dir
config({ path: resolve(__dirname, "../.env.local"), override: true });

const QUESTION_RULES = `
You are generating pre-briefing research questions for the President of MBZUAI ahead of a meeting.

Generate 4-6 intel_questions — short, scannable questions the president can glance at.

RULES:
- Each is ONE simple sentence, 8–15 words max.
- NO compound questions. NO dashes, semicolons, or "and what is...". ONE concept per question.
- NO jargon or qualifiers. Write like a chief of staff would speak aloud.
  Bad: "What is the precise structure and LP composition of Thrive's newly closed $10 billion fund — and are any Gulf sovereign wealth funds named as investors?"
  Good: "Who invested in Thrive's latest fund?"
  Bad: "What is Hassabis's current stated position on the relative priority of world models versus continued LLM scaling at Google DeepMind, and has this created internal tension?"
  Good: "Where does Hassabis stand on world models vs LLMs?"
- Topic labels: 1–2 words, uppercase.
- Categories: funding/deals, people/team, research/tech, Gulf connections, competition.
- Order by strategic relevance.

Return ONLY valid JSON:
{
  "intel_questions": [
    { "id": "iq-1", "topic": "FUNDING", "question": "Who invested in World Labs' latest round?" }
  ]
}
`;

const TEST_VISITORS = [
  { name: "Demis Hassabis", title: "CEO", org: "Google DeepMind" },
  { name: "Joshua Kushner", title: "Founder & CEO", org: "Thrive Capital" },
  { name: "Fei-Fei Li", title: "Co-Founder & Chair", org: "World Labs" },
];

async function testVisitor(
  client: Anthropic,
  visitor: { name: string; title: string; org: string }
) {
  const response = await client.messages.create({
    model: "claude-sonnet-4-6",
    max_tokens: 1024,
    system: QUESTION_RULES,
    messages: [
      {
        role: "user",
        content: `Generate intel_questions for a meeting with:\nName: ${visitor.name}\nTitle: ${visitor.title}\nOrganization: ${visitor.org}`,
      },
    ],
  });

  const text =
    response.content.find((b): b is Anthropic.TextBlock => b.type === "text")
      ?.text || "";
  const clean = text.replace(/```json\n?|```\n?/g, "").trim();
  const jsonMatch = clean.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error("No JSON found in response");

  const result = JSON.parse(jsonMatch[0]);
  return result.intel_questions as {
    id: string;
    topic: string;
    question: string;
  }[];
}

async function main() {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    console.error("ANTHROPIC_API_KEY not set in .env.local");
    process.exit(1);
  }
  const client = new Anthropic({ apiKey });

  console.log("Testing intel question generation...\n");
  console.log("═".repeat(70));

  let totalQuestions = 0;
  let totalPass = 0;
  let totalFail = 0;

  for (const visitor of TEST_VISITORS) {
    console.log(
      `\n▸ ${visitor.name} — ${visitor.title}, ${visitor.org}\n`
    );

    try {
      const questions = await testVisitor(client, visitor);

      for (const q of questions) {
        const wordCount = q.question.split(/\s+/).length;
        const pass = wordCount >= 6 && wordCount <= 18; // slight margin
        const hasCompound =
          q.question.includes(" — ") ||
          q.question.includes("; ") ||
          /,\s*and\s+(what|how|is|does|has)/i.test(q.question);

        const status = pass && !hasCompound ? "✅" : "❌";
        if (pass && !hasCompound) totalPass++;
        else totalFail++;
        totalQuestions++;

        console.log(
          `  ${status} [${q.topic.padEnd(14)}] (${String(wordCount).padStart(2)}w) ${q.question}`
        );
        if (hasCompound) console.log(`     ⚠  Compound question detected`);
        if (!pass)
          console.log(
            `     ⚠  Word count ${wordCount} outside 6-18 range`
          );
      }
    } catch (err) {
      console.error(
        `  ❌ Error: ${err instanceof Error ? err.message : err}`
      );
    }
  }

  console.log("\n" + "═".repeat(70));
  console.log(
    `\nResults: ${totalPass}/${totalQuestions} passed, ${totalFail} failed`
  );
  if (totalFail > 0) process.exit(1);
}

main().catch(console.error);
