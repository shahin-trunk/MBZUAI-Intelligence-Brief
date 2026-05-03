import { createClient } from "@supabase/supabase-js";
import { endOfDayGstEpoch, fanOut, sendOne } from "./apns.ts";

type Platform = "ios" | "android";
type Env = "production" | "sandbox";

interface WebhookBody {
  record?: { brief_date?: string; audio_status?: string; notified_at?: string | null };
  old_record?: { audio_status?: string } | null;
  brief_date?: string;
}

interface TokenRow {
  token: string;
  environment: Env;
}

const BUNDLE_ID = Deno.env.get("APNS_BUNDLE_ID") ?? "com.mbzuai.intel";
const CONCURRENCY = 50;

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }

  const body = (await req.json().catch(() => ({}))) as WebhookBody;
  const briefDate = body.record?.brief_date ?? body.brief_date;
  if (!briefDate) {
    return json({ error: "missing brief_date" }, 400);
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  // Atomic claim: set notified_at only if still null. Zero rows → already notified → exit.
  const { data: claimed, error: claimErr } = await supabase
    .from("briefs")
    .update({ notified_at: new Date().toISOString() })
    .eq("brief_date", briefDate)
    .is("notified_at", null)
    .select("brief_date");

  if (claimErr) {
    console.error("claim error", claimErr);
    return json({ error: claimErr.message }, 500);
  }
  if (!claimed || claimed.length === 0) {
    return json({ ok: true, skipped: "already_notified", brief_date: briefDate });
  }

  const { data: tokenRows, error: tokenErr } = await supabase
    .from("push_tokens")
    .select("token, environment")
    .eq("platform", "ios" satisfies Platform);

  if (tokenErr) {
    console.error("token query error", tokenErr);
    await rollbackClaim(supabase, briefDate);
    return json({ error: tokenErr.message }, 500);
  }

  const tokens = (tokenRows ?? []) as TokenRow[];
  if (tokens.length === 0) {
    return json({ ok: true, sent: 0, brief_date: briefDate });
  }

  const payload = {
    aps: {
      alert: {
        title: "Today's brief is ready",
        body: "Tap to open today's intelligence brief.",
      },
      sound: "default",
      badge: 1,
    },
    brief_date: briefDate,
    url: `/brief/${briefDate}`,
    deep_link: `presidential://brief/${briefDate}`,
  };

  const opts = {
    bundleId: BUNDLE_ID,
    expirationEpoch: endOfDayGstEpoch(briefDate),
    collapseId: `brief-${briefDate}`,
  };

  const toDelete: Array<{ token: string; environment: Env }> = [];
  let sent = 0;
  let transient = 0;

  await fanOut(tokens, CONCURRENCY, async (row) => {
    try {
      const result = await sendOne(row.token, row.environment, payload, opts);
      if (result.ok) {
        sent++;
      } else if (result.removable) {
        toDelete.push({ token: row.token, environment: row.environment });
      } else {
        transient++;
        console.warn(`apns non-2xx status=${result.status} reason=${result.reason}`);
      }
    } catch (err) {
      transient++;
      console.error("apns dispatch error", err);
    }
  });

  if (toDelete.length > 0) {
    const tokensForDelete = toDelete.map((r) => r.token);
    const { error: delErr } = await supabase
      .from("push_tokens")
      .delete()
      .in("token", tokensForDelete);
    if (delErr) console.error("token cleanup error", delErr);
  }

  // If every token failed transiently (APNS unreachable etc.), release the claim
  // so the nightly retry cron can re-attempt.
  if (sent === 0 && transient > 0 && toDelete.length === 0) {
    await rollbackClaim(supabase, briefDate);
    return json({ error: "all_transient_failures", brief_date: briefDate, transient }, 502);
  }

  return json({
    ok: true,
    brief_date: briefDate,
    sent,
    removed: toDelete.length,
    transient,
  });
});

async function rollbackClaim(
  // deno-lint-ignore no-explicit-any
  supabase: any,
  briefDate: string,
): Promise<void> {
  const { error } = await supabase
    .from("briefs")
    .update({ notified_at: null })
    .eq("brief_date", briefDate);
  if (error) console.error("rollback claim error", error);
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
