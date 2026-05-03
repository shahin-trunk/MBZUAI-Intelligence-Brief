import { useCallback, useEffect, useState } from "react";

interface EntityLogoEntry {
  logoUrl: string | null;
  category: string;
}

type LogoLookup = Record<string, EntityLogoEntry>;

let cachedLogos: LogoLookup | null = null;
let loadPromise: Promise<LogoLookup> | null = null;

const ENTITY_ALIAS_FALLBACKS: Record<string, string[]> = {
  uae: ["united arab emirates", "uae government"],
  "united arab emirates": ["uae", "uae government"],
  ksa: ["saudi arabia", "kingdom of saudi arabia"],
  "saudi arabia": ["ksa", "kingdom of saudi arabia"],
  us: ["united states", "united states of america"],
  usa: ["united states", "united states of america"],
  uk: ["united kingdom", "great britain"],
};

function normalizeEntityKey(value: string): string {
  return value
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}\s]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function lookupLogo(logos: LogoLookup, entityName: string): EntityLogoEntry | null {
  const direct = logos[entityName];
  if (direct) return direct;

  const normalized = normalizeEntityKey(entityName);
  if (!normalized) return null;

  const normalizedDirect = logos[normalized];
  if (normalizedDirect) return normalizedDirect;

  for (const alias of ENTITY_ALIAS_FALLBACKS[normalized] ?? []) {
    const resolved = logos[alias] ?? logos[normalizeEntityKey(alias)];
    if (resolved) return resolved;
  }

  const acronym = normalized
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("");
  if (acronym && acronym.length >= 2) {
    const acronymMatch = logos[acronym];
    if (acronymMatch) return acronymMatch;
  }

  for (const [key, entry] of Object.entries(logos)) {
    if (!key) continue;
    if (normalizeEntityKey(key) === normalized) return entry;
  }

  return null;
}

async function fetchEntityLogos(): Promise<LogoLookup> {
  if (cachedLogos) {
    return cachedLogos;
  }

  if (!loadPromise) {
    loadPromise = fetch("/api/entity-logos")
      .then(async (res) => {
        if (!res.ok) {
          return {};
        }
        const data = await res.json();
        const logos = (data.logos ?? {}) as LogoLookup;
        cachedLogos = logos;
        return logos;
      })
      .catch(() => ({}))
      .finally(() => {
        loadPromise = null;
      });
  }

  return loadPromise;
}

/**
 * Fetches all entity logos from /api/entity-logos and provides
 * a lookup function. Logos are cached for the session.
 */
export function useEntityLogos() {
  const [logos, setLogos] = useState<LogoLookup>(cachedLogos ?? {});
  const [loaded, setLoaded] = useState(Boolean(cachedLogos));

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const nextLogos = await fetchEntityLogos();
      if (!cancelled) {
        setLogos(nextLogos);
        setLoaded(true);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const resolve = useCallback(
    (entityName: string | undefined | null): EntityLogoEntry | null => {
      if (!entityName || !loaded) return null;
      return lookupLogo(logos, entityName) ?? null;
    },
    [logos, loaded],
  );

  return { resolve, loaded };
}
