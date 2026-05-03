import { NextRequest, NextResponse } from "next/server";
import { getAuthenticatedClient, handleRouteError } from "@/lib/api/helpers";

const DEFAULT_LIMIT = 90;
const MIN_LIMIT = 1;
const MAX_LIMIT = 365;

function parseLimit(raw: string | null): number {
  if (!raw) return DEFAULT_LIMIT;
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed)) return DEFAULT_LIMIT;
  return Math.min(Math.max(parsed, MIN_LIMIT), MAX_LIMIT);
}

/**
 * List brief dates available to the reader, newest first.
 *
 * Powers the mobile client's calendar / date-picker (Flutter
 * `BriefApiClient.fetchCatalog`). The Next.js portal already fetches
 * the same list server-side via `fetchAvailableDates` in
 * `app/(portal)/brief/[date]/page.tsx`; this route is the HTTP
 * equivalent for non-Next consumers that go through
 * `intelligence-brief-backend`.
 *
 * `earliest_brief_date` is the oldest date in the returned window, not
 * the historical minimum — pass a larger `limit` to widen.
 */
export async function GET(request: NextRequest) {
  try {
    const { supabase } = await getAuthenticatedClient();

    const limit = parseLimit(request.nextUrl.searchParams.get("limit"));

    const { data, error } = await supabase
      .from("briefs")
      .select("brief_date")
      .order("brief_date", { ascending: false })
      .limit(limit);

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    const availableDates = (data ?? []).map(
      (row) => row.brief_date as string
    );

    const todayUtc = new Date().toISOString().slice(0, 10);
    const todayResolved = availableDates[0] ?? todayUtc;
    const latestBriefDate = availableDates[0] ?? null;
    const earliestBriefDate =
      availableDates.length > 0
        ? availableDates[availableDates.length - 1]
        : null;

    return NextResponse.json({
      available_dates: availableDates,
      today_resolved: todayResolved,
      latest_brief_date: latestBriefDate,
      earliest_brief_date: earliestBriefDate,
      count: availableDates.length,
    });
  } catch (err) {
    return handleRouteError(err, "briefs GET");
  }
}
