import type { DossierGenerationResult } from "@/lib/types/executive-engagement";

/**
 * Extract and parse JSON from model text that may contain markdown fences
 * or surrounding prose. Uses brace-depth counting to find the outermost
 * `{ … }` object reliably.
 */
export function extractDossierJson(raw: string): DossierGenerationResult {
  // Strip markdown fences (case-insensitive, handles trailing spaces)
  const text = raw.replace(/```(?:json)?\s*\n?|```\s*$/gim, "").trim();

  const start = text.indexOf("{");
  if (start === -1) throw new SyntaxError("No JSON object found in response");

  // Walk from the first '{' using brace-depth to find matching '}'
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (escaped) { escaped = false; continue; }
    if (ch === "\\") { escaped = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        return JSON.parse(text.slice(start, i + 1));
      }
    }
  }

  throw new SyntaxError("Unterminated JSON object in response");
}
