import { createClient } from "@supabase/supabase-js";

Deno.serve(async (_req) => {
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  const since = new Date();
  since.setUTCDate(since.getUTCDate() - 1);
  const sinceDate = since.toISOString().slice(0, 10);

  const { data: pending, error } = await supabase
    .from("briefs")
    .select("brief_date")
    .eq("audio_status", "ready")
    .is("notified_at", null)
    .gte("brief_date", sinceDate);

  if (error) {
    console.error("retry query error", error);
    return new Response(JSON.stringify({ error: error.message }), { status: 500 });
  }

  const rows = pending ?? [];
  if (rows.length === 0) {
    return new Response(JSON.stringify({ ok: true, retried: 0 }));
  }

  const sendFnUrl =
    `${Deno.env.get("SUPABASE_URL")}/functions/v1/send-brief-notification`;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  const results = await Promise.all(
    rows.map(async (row) => {
      const res = await fetch(sendFnUrl, {
        method: "POST",
        headers: {
          authorization: `Bearer ${serviceKey}`,
          "content-type": "application/json",
        },
        body: JSON.stringify({ record: { brief_date: row.brief_date } }),
      });
      return { brief_date: row.brief_date, status: res.status };
    }),
  );

  return new Response(
    JSON.stringify({ ok: true, retried: rows.length, results }),
    { headers: { "content-type": "application/json" } },
  );
});
