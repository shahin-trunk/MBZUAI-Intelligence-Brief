function slugify(text: string | null | undefined): string {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function compactSlug(text: string | null | undefined, fallback: string): string {
  const value = slugify(text);
  return value || fallback;
}

export function buildEngagementId(input: {
  date: string;
  visitorName: string;
  time?: string | null;
  visitorOrganization?: string | null;
  location?: string | null;
}): string {
  const name = compactSlug(input.visitorName, "visitor");
  const time = compactSlug(input.time, "time");
  const organization = compactSlug(input.visitorOrganization, "org");
  const location = compactSlug(input.location, "location");

  return `eng-${input.date}-${name}-${time}-${organization}-${location}`;
}
