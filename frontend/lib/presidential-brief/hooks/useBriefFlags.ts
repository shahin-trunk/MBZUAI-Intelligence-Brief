"use client";

import { useCallback, useMemo } from "react";
import { useFlags } from "@/lib/hooks/useFlags";

interface BriefFlagState {
  flaggedItems: Set<string>;
  toggleFlag: (itemId: string) => Promise<void>;
}

export function useBriefFlags(briefDate: string): BriefFlagState {
  const { flags, toggleFlag } = useFlags(briefDate);

  const flaggedItems = useMemo(
    () => new Set(flags.map((flag) => flag.item_id)),
    [flags]
  );

  const toggle = useCallback(
    async (itemId: string) => {
      await toggleFlag(itemId);
    },
    [toggleFlag]
  );

  return { flaggedItems, toggleFlag: toggle };
}
