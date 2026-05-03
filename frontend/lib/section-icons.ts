import {
  GraduationCap,
  Landmark,
  Newspaper,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

/**
 * Visual mark rendered in the card avatar when no entity logo or country
 * flag is available. One entry per canonical brief section.
 *
 * UAE uses a real country flag (via `flag-icons`). The other four sections
 * use Lucide icons chosen to read unambiguously at 22–56 px:
 *   - Regional Research & Academic Events → GraduationCap
 *   - International Politics & Policy     → Landmark
 *   - International Business & Technology → TrendingUp
 *   - Model Releases & Technical Developments → Sparkles
 */
export type SectionMark =
  | { kind: "flag"; countryCode: string }
  | { kind: "icon"; Icon: LucideIcon };

const SECTION_MARK: Record<string, SectionMark> = {
  "UAE": { kind: "flag", countryCode: "ae" },
  "Regional Research & Academic Events": { kind: "icon", Icon: GraduationCap },
  "International Politics & Policy": { kind: "icon", Icon: Landmark },
  "International Business & Technology": { kind: "icon", Icon: TrendingUp },
  "Model Releases & Technical Developments": { kind: "icon", Icon: Sparkles },
  "Follow up": { kind: "icon", Icon: Newspaper },
};

const DEFAULT_MARK: SectionMark = { kind: "icon", Icon: Newspaper };

export function sectionMarkFor(section: string | null | undefined): SectionMark {
  if (!section) return DEFAULT_MARK;
  return SECTION_MARK[section.trim()] ?? DEFAULT_MARK;
}
