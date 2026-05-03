import type { BriefItem } from "@/lib/types/brief";

/**
 * Thematic hero images (Unsplash) keyed by brief section — stable URLs for demo placeholders.
 */
const SECTION_HERO_IMAGES: Record<string, string> = {
  UAE:
    "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=960&h=540&fit=crop&q=80",
  "Regional Research & Academic Events":
    "https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=960&h=540&fit=crop&q=80",
  "International Politics & Policy":
    "https://images.unsplash.com/photo-1529107386315-c1f2a0e8b8c0?w=960&h=540&fit=crop&q=80",
  "International Business & Technology":
    "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=960&h=540&fit=crop&q=80",
  "Model Releases & Technical Developments":
    "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=960&h=540&fit=crop&q=80",
  "Follow up":
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=960&h=540&fit=crop&q=80",
};

const DEFAULT_HERO =
  "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=960&h=540&fit=crop&q=80";

export function heroImageUrlForItem(item: BriefItem): string {
  return SECTION_HERO_IMAGES[item.section] ?? DEFAULT_HERO;
}

/**
 * Curated “big tech / cloud / AI” domains for Clearbit logos when we cannot infer from the item.
 * Order is stable; which logo appears is driven by a hash of `item.id`.
 */
const BRAND_POOL = [
  "google.com",
  "openai.com",
  "microsoft.com",
  "amazon.com",
  "meta.com",
  "apple.com",
  "nvidia.com",
  "anthropic.com",
  "github.com",
  "ibm.com",
  "oracle.com",
  "salesforce.com",
  "adobe.com",
  "intel.com",
  "netflix.com",
  "spotify.com",
  "stripe.com",
  "cloudflare.com",
  "zoom.us",
  "tesla.com",
  "samsung.com",
  "cursor.com",
  "cloud.google.com",
] as const;

/** Section-flavoured defaults when the publisher string does not match a known brand. */
const SECTION_BRAND_HINT: Record<string, string> = {
  "Model Releases & Technical Developments": "openai.com",
  "International Business & Technology": "microsoft.com",
  "International Politics & Policy": "bloomberg.com",
  "Regional Research & Academic Events": "google.com",
  UAE: "amazon.com",
  "Follow up": "google.com",
};

const SOURCE_NAME_BRAND_RULES: { re: RegExp; domain: string }[] = [
  { re: /\bdeepmind\b/i, domain: "deepmind.com" },
  { re: /\bgoogle\b|gemini|alphabet|android|youtube|waymo/i, domain: "google.com" },
  { re: /\bopenai\b|chatgpt|gpt-4|gpt-5|gpt-3/i, domain: "openai.com" },
  { re: /\banthropic\b|\bclaude\b/i, domain: "anthropic.com" },
  { re: /\bmicrosoft\b|\bazure\b|github|linkedin|bing/i, domain: "microsoft.com" },
  { re: /\bmeta\b|facebook|instagram|whatsapp|oculus/i, domain: "meta.com" },
  { re: /\bapple\b|iphone|ipad|macos|icloud/i, domain: "apple.com" },
  { re: /\bamazon\b|\baws\b|amazon web services/i, domain: "amazon.com" },
  { re: /\bnvidia\b|geforce|cuda/i, domain: "nvidia.com" },
  { re: /\bibm\b|watson|red hat|redhat/i, domain: "ibm.com" },
  { re: /\boracle\b|java\b.*oracle|sun micro/i, domain: "oracle.com" },
  { re: /\bsalesforce\b|slack(?!\s+news)/i, domain: "salesforce.com" },
  { re: /\badobe\b|photoshop|illustrator/i, domain: "adobe.com" },
  { re: /\bintel\b|xeon|core i\d/i, domain: "intel.com" },
  { re: /\bnetflix\b/i, domain: "netflix.com" },
  { re: /\bspotify\b/i, domain: "spotify.com" },
  { re: /\bstripe\b/i, domain: "stripe.com" },
  { re: /\bcloudflare\b/i, domain: "cloudflare.com" },
  { re: /\bzoom\b(?!\s+out)/i, domain: "zoom.us" },
  { re: /\btesla\b/i, domain: "tesla.com" },
  { re: /\bsamsung\b|galaxy\b/i, domain: "samsung.com" },
  { re: /\btwitter\b|\bx\.com\b|^x$/i, domain: "x.com" },
  { re: /\buber\b/i, domain: "uber.com" },
  { re: /\bairbnb\b/i, domain: "airbnb.com" },
  { re: /\bpalantir\b/i, domain: "palantir.com" },
  { re: /\bmistral\b/i, domain: "mistral.ai" },
  { re: /\bcohere\b/i, domain: "cohere.com" },
  { re: /\bx\.ai\b|\bgrok\b/i, domain: "x.ai" },
  { re: /\bhuggingface\b|hugging face/i, domain: "huggingface.co" },
  { re: /\bopenrouter\b/i, domain: "openrouter.ai" },
  { re: /\bvercel\b/i, domain: "vercel.com" },
  { re: /\bcursor\b/i, domain: "cursor.com" },
  { re: /\bgemini\b/i, domain: "google.com" },
  { re: /\bgoogle cloud\b|\bgcp\b/i, domain: "cloud.google.com" },
  { re: /\bnotion\b/i, domain: "notion.so" },
  { re: /\bdropbox\b/i, domain: "dropbox.com" },
  { re: /\bshopify\b/i, domain: "shopify.com" },
  { re: /\bbloomberg\b/i, domain: "bloomberg.com" },
  { re: /\breuters\b/i, domain: "reuters.com" },
  { re: /financial times|\bft\.com\b|\bthe ft\b/i, domain: "ft.com" },
  { re: /the economist|\beconomist\b/i, domain: "economist.com" },
  { re: /wall street journal|\bwsj\b/i, domain: "wsj.com" },
  { re: /\bcnbc\b/i, domain: "cnbc.com" },
  { re: /\bbc news\b|\bbbc\b/i, domain: "bbc.co.uk" },
  { re: /the national|thenational/i, domain: "thenationalnews.com" },
];

/** Known hostnames (or suffixes) → Clearbit domain (apex). */
const HOST_BRAND_ALIASES: { match: RegExp; domain: string }[] = [
  { match: /(^|\.)openai\.com$/i, domain: "openai.com" },
  { match: /(^|\.)anthropic\.com$/i, domain: "anthropic.com" },
  { match: /(^|\.)google\.co?m?$/i, domain: "google.com" },
  { match: /(^|\.)deepmind\.(com|google)$/i, domain: "deepmind.com" },
  { match: /(^|\.)microsoft\.com$/i, domain: "microsoft.com" },
  { match: /(^|\.)github\.com$/i, domain: "github.com" },
  { match: /(^|\.)amazon\.(com|aws)$/i, domain: "amazon.com" },
  { match: /(^|\.)aws\.amazon\.com$/i, domain: "amazon.com" },
  { match: /(^|\.)meta\.com$/i, domain: "meta.com" },
  { match: /(^|\.)apple\.com$/i, domain: "apple.com" },
  { match: /(^|\.)nvidia\.com$/i, domain: "nvidia.com" },
  { match: /(^|\.)ibm\.com$/i, domain: "ibm.com" },
  { match: /(^|\.)oracle\.com$/i, domain: "oracle.com" },
  { match: /(^|\.)reuters\.com$/i, domain: "reuters.com" },
  { match: /(^|\.)bloomberg\.com$/i, domain: "bloomberg.com" },
  { match: /(^|\.)ft\.com$/i, domain: "ft.com" },
  { match: /(^|\.)thenationalnews\.com$/i, domain: "thenationalnews.com" },
];

function hostnameFromSourceUrl(url?: string): string | null {
  if (!url?.trim()) return null;
  try {
    const href = url.includes("://") ? url : `https://${url}`;
    const host = new URL(href).hostname.replace(/^www\./, "").toLowerCase();
    return host || null;
  } catch {
    return null;
  }
}

function domainFromHostname(host: string): string | null {
  const h = host.toLowerCase();
  for (const { match, domain } of HOST_BRAND_ALIASES) {
    if (match.test(h)) return domain;
  }
  return h || null;
}

function inferDomainFromText(text: string): string | null {
  const t = text.trim();
  if (!t) return null;
  for (const { re, domain } of SOURCE_NAME_BRAND_RULES) {
    if (re.test(t)) return domain;
  }
  return null;
}

function stablePoolIndex(id: string, size: number): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return h % size;
}

/**
 * High-availability favicon-sized brand marks (PNG) via Google's favicon endpoint.
 * Clearbit often fails in browsers or returns empty; this URL pattern is widely cached and reliable.
 */
function brandIconUrl(domain: string): string {
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=128`;
}

/**
 * Publisher logo for the hero badge: real site icons from the web when we can infer a domain
 * (including keywords in the headline, e.g. DeepMind), otherwise a stable pick from {@link BRAND_POOL}.
 */
export function sourceLogoUrlForItem(item: BriefItem): string {
  const fromField = item.source_domain?.replace(/^www\./i, "").trim();
  if (fromField) {
    return brandIconUrl(fromField);
  }

  const host = hostnameFromSourceUrl(item.source_url);
  if (host) {
    const mapped = domainFromHostname(host);
    if (mapped) return brandIconUrl(mapped);
    return brandIconUrl(host);
  }

  const fromName = inferDomainFromText(item.source_name);
  if (fromName) return brandIconUrl(fromName);

  const fromHeadline = inferDomainFromText(item.headline);
  if (fromHeadline) return brandIconUrl(fromHeadline);

  const sectionHint = SECTION_BRAND_HINT[item.section];
  if (sectionHint) return brandIconUrl(sectionHint);

  const poolDomain = BRAND_POOL[stablePoolIndex(item.id, BRAND_POOL.length)]!;
  return brandIconUrl(poolDomain);
}

/** @deprecated Use source logo image in UI; kept for non-React consumers if any */
export function sourceLogoLabel(sourceName: string): string {
  const t = sourceName.trim();
  if (!t) return "•";
  const parts = t.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0]![0]! + parts[1]![0]!).toUpperCase();
  }
  return t.slice(0, 2).toUpperCase();
}

/** Split body copy into short bullet lines for the card body (capped for fixed-height cards). */
export function bulletLinesFromMainBullet(text: string, maxBullets = 3): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  const protectedText = trimmed
    .replace(/\b([A-Z])\.\s*([A-Z])\./g, "$1__DOT__$2__DOT__")
    .replace(/\b(U|u)\.\s*(S|s)\.\s*(A|a)\./g, "USA")
    .replace(/\b(U|u)\.\s*(S|s)\./g, "US");
  const bySentence = trimmed
    .replace(/\b([A-Z])\.\s*([A-Z])\./g, "$1__DOT__$2__DOT__")
    .replace(/\b(U|u)\.\s*(S|s)\.\s*(A|a)\./g, "USA")
    .replace(/\b(U|u)\.\s*(S|s)\./g, "US")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (bySentence.length >= 2) {
    return bySentence
      .map((sentence) => sentence.replace(/__DOT__/g, "."))
      .slice(0, maxBullets);
  }
  const byComma = protectedText.split(/,\s+/).filter(Boolean);
  if (byComma.length >= 2 && byComma.length <= maxBullets) {
    return byComma.map((s) => {
      const restored = s.replace(/__DOT__/g, ".");
      return restored.endsWith(".") ? restored : `${restored}.`;
    });
  }
  const one =
    trimmed.length > 220 ? `${trimmed.slice(0, 217).trimEnd()}…` : trimmed;
  return [one];
}
