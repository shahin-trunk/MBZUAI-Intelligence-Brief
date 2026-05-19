import { NextRequest, NextResponse } from "next/server";
import { getCurationClient } from "@/lib/api/curation-helpers";
import { handleRouteError } from "@/lib/api/helpers";
import { transformBrief } from "@/lib/transforms/brief";
import type { RawPipelineBrief } from "@/lib/types/brief";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { supabase } = await getCurationClient();
    const { date: briefDate } = await params;

    // `audio_script` + `audio_script_fr` power the full-screen transcript
    // on mobile. Without them the Flutter client falls back to a mock
    // placeholder. Both columns are confirmed to exist — the backend
    // audio pipeline writes them in `backend/generate_audio.py` via
    // `_update_briefs_table`. The Next portal fetches the same columns
    // server-side in `app/(portal)/brief/[date]/page.tsx`.
    //
    // Do NOT add `audio_duration_seconds` / `audio_segments` here — they
    // are not present in the production schema (see commit 60bd5c7 which
    // rolled back the earlier extension of `/api/audio-status` for
    // exactly this reason).
    const { data, error } = await supabase
      .from("briefs")
      .select(
        "raw_json, brief_date, audio_script, audio_script_fr, audio_url_fr, audio_script_ar, audio_url_ar"
      )
      .eq("brief_date", briefDate)
      .maybeSingle();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    if (!data?.raw_json) {
      return NextResponse.json({ error: "Brief not found" }, { status: 404 });
    }

    const transformed = transformBrief(data.raw_json as RawPipelineBrief);

    return NextResponse.json({
      items: transformed.items,
      briefDate: data.brief_date,
      audio_script: data.audio_script ?? null,
      audio_script_fr: data.audio_script_fr ?? null,
      audio_url_fr: data.audio_url_fr ?? null,
      audio_script_ar: data.audio_script_ar ?? null,
      audio_url_ar: data.audio_url_ar ?? null,
    });
  } catch (err) {
    return handleRouteError(err, "briefs/[date]/items GET");
  }
}
