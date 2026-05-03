import React from "react";

const INLINE_SOURCE_PATTERN = /\[(Sources?):\s*([^\]]*)\]/g;

function toDisplaySourceLabel(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";

  try {
    const url = new URL(trimmed);
    return url.hostname.replace(/^www\./, "");
  } catch {
    return trimmed;
  }
}

function formatInlineSourceCitation(rawValue: string): string {
  const labels = rawValue
    .split(",")
    .map((part) => toDisplaySourceLabel(part))
    .filter(Boolean);

  const deduped = [...new Set(labels)];
  if (deduped.length === 0) return "source";
  if (deduped.length <= 3) return deduped.join(", ");
  return `${deduped.slice(0, 2).join(", ")} +${deduped.length - 2}`;
}

export function stripInlineSourceCitations(text: string): string {
  return text.replace(INLINE_SOURCE_PATTERN, "").trim();
}

export function stripMarkdownFormatting(text: string): string {
  return stripInlineSourceCitations(text).replace(/\*\*/g, "").trim();
}

/**
 * Render an analysis block that may be either a bulleted list
 * (v4 shape: "- first sentence.\n- second sentence.") or a single
 * paragraph (legacy shape).
 *
 * Returns JSX that callers should place inside a block-level container
 * (a div, not a p) because the bulleted path emits a <ul>.
 *
 * Bullet detection: the text, after trimming, must start with "- ".
 * Splits on newline-then-"- " so a single "- " inside the sentence
 * (e.g. a dash) does not accidentally start a new bullet.
 */
export function renderAnalysisBlock(text: string): React.ReactNode {
  const trimmed = (text ?? "").trim();
  if (!trimmed) return null;

  if (!trimmed.startsWith("- ")) {
    return renderMarkdown(trimmed);
  }

  const bullets = trimmed
    .split(/\n(?=- )/)
    .map((line) => line.replace(/^- /, "").trim())
    .filter((line) => line.length > 0);

  if (bullets.length === 0) {
    return renderMarkdown(trimmed);
  }

  return (
    <ul className="list-disc space-y-2 pl-5 marker:text-text-muted">
      {bullets.map((bullet, i) => (
        <li key={i}>{renderMarkdown(bullet)}</li>
      ))}
    </ul>
  );
}

/**
 * Render brief text with markdown-style formatting:
 * - **bold** → <strong> with bright text
 * - [Source: ...] / [Sources: ...] → compact inline citation
 * - Preserves plain text segments
 *
 * Does NOT use a full markdown library — simple regex-based parsing
 * tuned for the pipeline's output format.
 */
export function renderMarkdown(text: string): React.ReactNode[] {
  // First pass: split on **bold** and inline source citation patterns
  const tokenPattern = /(\*\*[^*]+\*\*|\[(?:Source|Sources):\s*[^\]]*\])/g;
  const parts = text.split(tokenPattern);

  return parts
    .filter((part) => part !== "")
    .map((part, i) => {
      // Bold text
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={i} className="text-text-bright font-semibold">
            {part.slice(2, -2)}
          </strong>
        );
      }

      // Source citation
      const sourceMatch = part.match(/^\[(?:Source|Sources):\s*([^\]]*)\]$/);
      if (sourceMatch) {
        return (
          <cite
            key={i}
            className="font-mono text-[12px] text-text-muted not-italic ml-1"
          >
            ({formatInlineSourceCitation(sourceMatch[1])})
          </cite>
        );
      }

      // Plain text
      return <span key={i}>{part}</span>;
    });
}
