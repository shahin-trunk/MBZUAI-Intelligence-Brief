import { cn } from "@/lib/utils";

interface CountryFlagProps {
  /** ISO 3166-1 alpha-2 code (lowercase). */
  code: string;
  /** Extra Tailwind classes for the span. */
  className?: string;
  /** Accessible label, defaults to the uppercase code. */
  ariaLabel?: string;
}

/**
 * Renders a squared country flag via the `flag-icons` CSS package.
 * The `fi fis fi-{code}` classes produce a 1:1 aspect-ratio flag; the
 * enclosing container controls the rendered size. Global stylesheet is
 * imported in `app/layout.tsx`.
 */
export function CountryFlag({ code, className, ariaLabel }: CountryFlagProps) {
  const normalized = code.toLowerCase();
  return (
    <span
      className={cn("fi fis", `fi-${normalized}`, className)}
      data-country={normalized}
      aria-label={ariaLabel ?? normalized.toUpperCase()}
      role="img"
    />
  );
}
