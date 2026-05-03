import {
  isEntityLogoCategory,
  type EntityLogoCategory,
} from "@/lib/constants/entity-logo-categories";
import type { BriefItem } from "@/lib/types/brief";

interface InferEntityCategoryOptions {
  authoritativeCategory?: string | null;
}

const COUNTRY_NAMES = new Set([
  "uae",
  "united arab emirates",
  "saudi arabia",
  "ksa",
  "qatar",
  "oman",
  "bahrain",
  "kuwait",
  "iran",
  "iraq",
  "israel",
  "lebanon",
  "syria",
  "jordan",
  "egypt",
  "turkey",
  "turkiye",
  "china",
  "united states",
  "united states of america",
  "us",
  "usa",
  "united kingdom",
  "uk",
  "great britain",
  "france",
  "germany",
  "italy",
  "spain",
  "india",
  "japan",
  "singapore",
  "south korea",
  "korea",
]);

const MODEL_TERMS =
  /\b(model|models|llm|foundation model|frontier model|reasoning model|multimodal|weights|checkpoint|benchmark|inference)\b/i;
const DEFENSE_TERMS =
  /\b(centcom|pentagon|ministry of defense|ministry of defence|department of defense|department of defence|armed forces|military|navy|army|air force|marines|brigade|fleet|command|missile|defense|defence)\b/i;
const GOVERNMENT_TERMS =
  /\b(government|ministry|department|president|prime minister|crown prince|sheikh|emir|royal court|parliament|congress|senate|cabinet|administration|commission|municipality|authority|council|state department|treasury|foreign office|mayor)\b/i;
const UNIVERSITY_TERMS =
  /\b(university|college|school of|academy|polytechnic|campus|institute of technology)\b/i;
const ENERGY_TERMS =
  /\b(energy|oil|gas|lng|petroleum|power|renewable|solar|wind|nuclear|electricity|utility|utilities|adnoc|aramco|opec)\b/i;
const FINANCE_TERMS =
  /\b(bank|capital|finance|financial|fund|funds|investment|investments|investor|investors|asset management|wealth|ventures|venture|private equity|securities|exchange|holdings|mubadala|adia|blackrock|goldman|jpmorgan)\b/i;
const ORG_TERMS =
  /\b(foundation|association|society|alliance|coalition|forum|initiative|network|committee|ngo|nonprofit|non profit|charity|united nations|unesco|oecd|who|world economic forum|brookings)\b/i;
const COMPANY_TERMS =
  /\b(company|corp|corporation|inc|llc|ltd|plc|gmbh|ag|group|technologies|technology|tech|systems|labs|lab|openai|anthropic|google|microsoft|meta|amazon|apple|nvidia|alibaba|tesla)\b/i;

function normalize(value: string | null | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}\s.-]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeDomain(value: string | null | undefined): string {
  return normalize(value).replace(/^www\./, "");
}

function categoryFromDomain(domain: string): EntityLogoCategory | null {
  if (!domain) return null;
  if (domain.endsWith(".mil")) return "defense";
  if (domain.endsWith(".gov")) return "government";
  if (domain.endsWith(".edu") || domain.endsWith(".ac.ae") || domain.includes(".ac.")) {
    return "university";
  }
  if (domain.endsWith(".org")) return "org";
  return null;
}

export function inferEntityCategory(
  item: Pick<
    BriefItem,
    | "headline"
    | "section"
    | "source_name"
    | "source_domain"
    | "primary_subject"
    | "primary_entity"
    | "badge_subject"
    | "primary_entity_category"
    | "is_model_release"
    | "model_release_data"
    | "entities"
  >,
  options: InferEntityCategoryOptions = {}
): EntityLogoCategory {
  if (
    options.authoritativeCategory &&
    isEntityLogoCategory(options.authoritativeCategory) &&
    options.authoritativeCategory !== "other"
  ) {
    return options.authoritativeCategory;
  }

  if (
    item.primary_entity_category &&
    isEntityLogoCategory(item.primary_entity_category) &&
    item.primary_entity_category !== "other"
  ) {
    return item.primary_entity_category;
  }

  if (item.is_model_release || item.model_release_data) {
    return "model";
  }

  const primaryEntity = normalize(
    item.badge_subject ?? item.primary_subject ?? item.primary_entity
  );
  const sourceDomain = normalizeDomain(item.source_domain);
  const combined = [
    normalize(item.badge_subject),
    normalize(item.primary_subject),
    primaryEntity,
    normalize(item.headline),
    normalize(item.source_name),
    sourceDomain,
    normalize(item.section),
    (item.entities ?? []).map(normalize).join(" "),
  ]
    .filter(Boolean)
    .join(" ");

  const domainCategory = categoryFromDomain(sourceDomain);
  if (domainCategory) return domainCategory;

  if (MODEL_TERMS.test(combined)) return "model";
  if (COUNTRY_NAMES.has(primaryEntity)) return "country";
  if (DEFENSE_TERMS.test(combined)) return "defense";
  if (GOVERNMENT_TERMS.test(combined)) return "government";
  if (UNIVERSITY_TERMS.test(combined)) return "university";
  if (ENERGY_TERMS.test(combined)) return "energy";
  if (FINANCE_TERMS.test(combined)) return "finance";
  if (ORG_TERMS.test(combined)) return "org";
  if (COMPANY_TERMS.test(combined)) return "company";

  if (
    combined.includes("model releases") ||
    combined.includes("technical developments")
  ) {
    return "model";
  }

  if (primaryEntity) {
    return "company";
  }

  return categoryFromSection(item.section) ?? "other";
}

function categoryFromSection(
  section: string | null | undefined,
): EntityLogoCategory | null {
  if (!section) return null;
  const s = section.trim();
  if (s === "UAE") return "country";
  if (s === "International Politics & Policy") return "government";
  if (s === "International Business & Technology") return "company";
  if (s === "Model Releases & Technical Developments") return "model";
  if (s === "Regional Research & Academic Events") return "university";
  return null;
}
