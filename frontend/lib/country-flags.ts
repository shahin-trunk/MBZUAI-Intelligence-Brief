/**
 * Maps country labels and aliases to ISO 3166-1 alpha-2 codes, used by
 * the `flag-icons` stylesheet (CSS class `fi fi-{code}`).
 *
 * Keys are normalized (lowercased, punctuation stripped, whitespace
 * collapsed). Mirrors `COUNTRY_ALIASES` in
 * `backend/pipeline/entity_identity.py` so frontend and backend agree on
 * what counts as a country label.
 */

const RAW_COUNTRY_ALIASES: Record<string, string[]> = {
  ae: [
    "united arab emirates",
    "uae",
    "emirates",
    "abu dhabi",
    "dubai",
    "sharjah",
    "ajman",
    "fujairah",
    "ras al khaimah",
    "umm al quwain",
    "al ain",
  ],
  us: [
    "united states",
    "united states of america",
    "us",
    "usa",
    "america",
  ],
  gb: [
    "united kingdom",
    "uk",
    "britain",
    "great britain",
  ],
  sa: [
    "saudi arabia",
    "ksa",
    "kingdom of saudi arabia",
  ],
  qa: ["qatar"],
  om: ["oman"],
  bh: ["bahrain"],
  kw: ["kuwait"],
  ir: ["iran"],
  iq: ["iraq"],
  il: ["israel"],
  lb: ["lebanon"],
  sy: ["syria"],
  jo: ["jordan"],
  eg: ["egypt"],
  tr: ["turkey", "turkiye"],
  cn: ["china"],
  fr: ["france"],
  de: ["germany"],
  it: ["italy"],
  es: ["spain"],
  in: ["india"],
  jp: ["japan"],
  sg: ["singapore"],
  kr: ["south korea", "korea"],
  ru: ["russia"],
  pk: ["pakistan"],
  ye: ["yemen"],
  af: ["afghanistan"],
  ca: ["canada"],
  au: ["australia"],
  br: ["brazil"],
  mx: ["mexico"],
  nl: ["netherlands"],
  be: ["belgium"],
  ch: ["switzerland"],
  se: ["sweden"],
  no: ["norway"],
  dk: ["denmark"],
  fi: ["finland"],
  pl: ["poland"],
  ua: ["ukraine"],
  tw: ["taiwan"],
  hk: ["hong kong"],
};

function normalize(value: string): string {
  return value
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}\s]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const ALIAS_TO_CODE: Map<string, string> = (() => {
  const m = new Map<string, string>();
  for (const [code, aliases] of Object.entries(RAW_COUNTRY_ALIASES)) {
    for (const alias of aliases) {
      m.set(normalize(alias), code);
    }
  }
  return m;
})();

export function countryCodeFor(label: string | null | undefined): string | null {
  if (!label) return null;
  const key = normalize(label);
  if (!key) return null;
  return ALIAS_TO_CODE.get(key) ?? null;
}
