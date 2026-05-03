import {
  getAuthenticatedClient,
  handleRouteError,
  jsonOk,
  jsonError,
} from "@/lib/api/helpers";

/**
 * GET /api/flags/all
 * Returns all flags for the current user across ALL brief dates,
 * joined with brief_items to get item content for display.
 */
export async function GET() {
  try {
    const { supabase, user } = await getAuthenticatedClient();

    // 1. Fetch all flags for this user
    const { data: flags, error: flagsError } = await supabase
      .from("flags")
      .select("*")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false });

    if (flagsError) {
      return jsonError(flagsError.message, 500);
    }

    if (!flags || flags.length === 0) {
      return jsonOk({ flaggedItems: [] });
    }

    // 2. Collect unique item_ids to batch-fetch from brief_items
    const itemIds = [...new Set(flags.map((f) => f.item_id))];

    const { data: items, error: itemsError } = await supabase
      .from("brief_items")
      .select("item_id, brief_date, headline, main_bullet, section, significance, source_name")
      .in("item_id", itemIds);

    if (itemsError) {
      return jsonError(itemsError.message, 500);
    }

    // 3. Build a lookup: `${item_id}::${brief_date}` → item data
    const itemLookup = new Map<string, typeof items[number]>();
    for (const item of items ?? []) {
      itemLookup.set(`${item.item_id}::${item.brief_date}`, item);
    }

    // 4. Merge flags with item data
    const flaggedItems = flags.map((flag) => {
      const item = itemLookup.get(`${flag.item_id}::${flag.brief_date}`);
      return {
        ...flag,
        headline: item?.headline ?? null,
        main_bullet: item?.main_bullet ?? null,
        section: item?.section ?? null,
        significance: item?.significance ?? null,
        source_name: item?.source_name ?? null,
      };
    });

    return jsonOk({ flaggedItems });
  } catch (err) {
    return handleRouteError(err, "flags/all GET");
  }
}
