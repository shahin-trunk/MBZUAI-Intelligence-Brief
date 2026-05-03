/**
 * Deterministic exhibit formatter for card display.
 *
 * Runs after Claude Vision extracts structured data from a screenshot
 * and before the exhibit is saved to the database. Cleans up labels,
 * headers, and cell values so exhibits render well in narrow card
 * columns regardless of what the LLM produced.
 *
 * TypeScript equivalent of backend/pipeline/exhibit_formatter.py —
 * same logic, same constants, same lookup table.
 */

// ---------------------------------------------------------------------------
// Benchmark name abbreviations
// ---------------------------------------------------------------------------

const BENCHMARK_ABBREVS: Record<string, string> = {
  "humanity's last exam": "HLE",
  "humanitys last exam": "HLE",
  hle: "HLE",
  "arc-agi-2": "ARC-AGI-2",
  "arc agi 2": "ARC-AGI-2",
  "arc-agi": "ARC-AGI",
  "gpqa diamond": "GPQA Diamond",
  gpqa: "GPQA",
  "swe-bench verified": "SWE-bench Verified",
  "swe-bench": "SWE-bench",
  "swe bench": "SWE-bench",
  "terminal-bench 2.0": "Terminal-Bench 2.0",
  "terminal-bench hard": "Terminal-Bench Hard",
  "terminal bench": "Terminal-Bench",
  mmlu: "MMLU",
  "mmlu-pro": "MMLU-Pro",
  "math-500": "MATH-500",
  "math 500": "MATH-500",
  humaneval: "HumanEval",
  "human eval": "HumanEval",
  "code arena": "Code Arena",
  livecodebench: "LiveCodeBench",
  "live code bench": "LiveCodeBench",
  "artificial analysis intelligence index": "AA Intelligence",
  "artificial analysis intelligence": "AA Intelligence",
  "artificial analysis": "AA Intelligence",
  "aime 2025": "AIME 2025",
  "aime 2024": "AIME 2024",
  pinchbench: "PinchBench",
  simpleqa: "SimpleQA",
  "simple qa": "SimpleQA",
  codeforces: "Codeforces",
  "chatbot arena": "Chatbot Arena",
  "lmsys arena": "LMSYS Arena",
  "arena elo": "Arena Elo",
  "mt-bench": "MT-Bench",
  ifeval: "IFEval",
  hellaswag: "HellaSwag",
  winogrande: "WinoGrande",
  "bigbench hard": "BBH",
  "big bench hard": "BBH",
  drop: "DROP",
  triviaqa: "TriviaQA",
  "natural questions": "NQ",
};

const MAX_BENCHMARK_CHARS = 30;
const MAX_COLUMN_HEADERS = 6;
const MAX_CELL_CHARS = 20;
const MAX_METRIC_LABEL_CHARS = 18;
const MAX_TIMELINE_DESC_CHARS = 80;

// Condition-like keywords that get extracted into parenthetical qualifiers
const CONDITION_KEYWORDS = [
  "no tool",
  "with tool",
  "search",
  "code",
  "verified",
  "hard",
  "lite",
  "harness",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function truncate(text: string, maxChars: number): string {
  if (!text || text.length <= maxChars) return text || "";
  const cut = text.substring(0, maxChars - 1).trimEnd();
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > maxChars / 2 ? cut.substring(0, lastSpace) : cut) + "…";
}

function abbreviateBenchmark(name: string): string {
  if (!name) return name;

  let condition = "";
  let base = name.trim();

  // Split on " - " separators (common in verbose benchmark names)
  if (base.includes(" - ")) {
    const segments = base.split(" - ").map((s) => s.trim());
    base = segments[0];

    // Look for short condition-like segments
    for (const seg of segments.slice(1)) {
      if (seg.length > 30) continue; // too long to be a condition
      const segLower = seg.toLowerCase();
      if (CONDITION_KEYWORDS.some((kw) => segLower.includes(kw))) {
        if (!condition) condition = `(${seg})`;
      }
    }
  }

  // Extract trailing parenthetical condition: "HLE (no tools)"
  const parenMatch = base.match(/\(([^)]+)\)\s*$/);
  if (parenMatch && !condition) {
    condition = parenMatch[0].trim();
    base = base.substring(0, parenMatch.index).trim();
  }

  // Lookup table (case-insensitive)
  const baseLower = base.toLowerCase().replace(/[''`]s?\b/g, "").trim();
  const abbrev = BENCHMARK_ABBREVS[baseLower] || BENCHMARK_ABBREVS[base.toLowerCase()];

  if (abbrev) {
    return condition ? `${abbrev} ${condition}` : abbrev;
  }

  // No match — truncate if needed
  const result = condition ? `${base} ${condition}` : base;
  return result.length > MAX_BENCHMARK_CHARS ? truncate(result, MAX_BENCHMARK_CHARS) : result;
}

function cleanCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  const v = String(value).trim();
  if (!v || v === "null" || v === "None" || v === "N/A" || v === "n/a") return "—";
  // Already clean: number, percentage, dash, fraction
  if (/^[<>~≈]?[\d.,]+%?$|^—$|^[\d.]+\/[\d.]+$/.test(v)) {
    return truncate(v, MAX_CELL_CHARS);
  }
  return truncate(v, MAX_CELL_CHARS);
}

function shortenModelName(name: string): string {
  if (!name || name.length <= 20) return name || "";
  const suffixes = [
    " Thinking (High)", " Thinking (Max)", " Thinking (xhigh)",
    " (High)", " (Max)", " (xhigh)", " Preview",
  ];
  for (const suffix of suffixes) {
    if (name.endsWith(suffix) && name.length - suffix.length >= 4) {
      return truncate(name.substring(0, name.length - suffix.length), 22);
    }
  }
  return truncate(name, 22);
}

// ---------------------------------------------------------------------------
// Per-exhibit-type formatters
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatBenchmarkTable(data: any): void {
  if (!data) return;

  // Shorten model names / column headers
  if (Array.isArray(data.models)) {
    data.models = data.models.map(shortenModelName);
    if (data.models.length > MAX_COLUMN_HEADERS) {
      data.models = data.models.slice(0, MAX_COLUMN_HEADERS);
    }
  }
  if (Array.isArray(data.columns)) {
    data.columns = data.columns.map((c: string) => truncate(c, 22));
    if (data.columns.length > MAX_COLUMN_HEADERS) {
      data.columns = data.columns.slice(0, MAX_COLUMN_HEADERS);
    }
  }

  // Abbreviate benchmark names and clean cells
  if (Array.isArray(data.rows)) {
    const modelCount = data.models?.length || data.columns?.length || 0;
    for (const row of data.rows) {
      // Handle both { benchmark, scores[] } and { benchmark, Model_A, Model_B } shapes
      if (row.benchmark) {
        row.benchmark = abbreviateBenchmark(row.benchmark);
      }
      if (Array.isArray(row.scores)) {
        row.scores = row.scores.map(cleanCell);
        // Pad if needed
        while (modelCount && row.scores.length < modelCount) {
          row.scores.push("—");
        }
        if (modelCount && row.scores.length > modelCount) {
          row.scores = row.scores.slice(0, modelCount);
        }
      }
      // Handle object-key scores: { "Model A": "85%", "Model B": "90%" }
      if (typeof row.scores === "object" && !Array.isArray(row.scores)) {
        for (const key of Object.keys(row.scores)) {
          row.scores[key] = cleanCell(row.scores[key]);
        }
      }
    }
  }

  // Truncate summary
  if (data.summary && data.summary.length > 200) {
    data.summary = truncate(data.summary, 200);
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatComparisonTable(data: any): void {
  if (!data) return;
  if (Array.isArray(data.columns)) {
    data.columns = data.columns.map((c: string) => truncate(c, 20));
  }
  if (Array.isArray(data.rows)) {
    for (const row of data.rows) {
      if (typeof row === "object") {
        for (const key of Object.keys(row)) {
          if (typeof row[key] === "string") {
            row[key] = truncate(row[key], 30);
          }
        }
      }
    }
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatMetricHighlight(data: any): void {
  if (!data?.metrics) return;
  for (const metric of data.metrics) {
    if (metric.label) metric.label = truncate(metric.label, MAX_METRIC_LABEL_CHARS);
    if (metric.value) metric.value = truncate(String(metric.value), 15);
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatTimeline(data: any): void {
  if (!data?.events) return;
  for (const event of data.events) {
    if (event.description) {
      event.description = truncate(event.description, MAX_TIMELINE_DESC_CHARS);
    }
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

const FORMATTERS: Record<string, (data: unknown) => void> = {
  benchmark_table: formatBenchmarkTable,
  comparison_table: formatComparisonTable,
  metric_highlight: formatMetricHighlight,
  timeline: formatTimeline,
};

/**
 * Format an extracted exhibit for card display. Call this after Claude
 * Vision extraction and before saving to the database.
 *
 * Modifies the exhibit in place and returns it.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function formatExhibit(exhibit: any): any {
  if (!exhibit || !exhibit.type) return exhibit;

  const formatter = FORMATTERS[exhibit.type];
  if (formatter) {
    formatter(exhibit.data || exhibit);
  }

  return exhibit;
}
