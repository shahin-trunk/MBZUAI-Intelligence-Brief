import { NextRequest, NextResponse } from "next/server";

interface RegenerateBody {
  brief_date: string;
  phrase_count?: number;
  language?: string;
}

/**
 * POST /api/learning/regenerate
 *
 * Proxies a regeneration request to the Cloud Run dispatcher.
 * Dispatches the regenerate-learning.yml GitHub Actions workflow.
 *
 * Environment variables (server-side only):
 *   DISPATCHER_URL     - URL of the cloud-run-dispatcher service
 *   DISPATCH_TOKEN     - X-Dispatch-Token for authentication
 */
export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => null)) as RegenerateBody | null;

  if (!body?.brief_date) {
    return NextResponse.json(
      { error: "Missing 'brief_date' in request body" },
      { status: 400 },
    );
  }

  const dispatcherUrl = process.env.DISPATCHER_URL;
  if (!dispatcherUrl) {
    return NextResponse.json(
      { error: "Dispatcher not configured (DISPATCHER_URL not set)" },
      { status: 500 },
    );
  }

  const dispatchToken = process.env.DISPATCH_TOKEN;

  try {
    const response = await fetch(`${dispatcherUrl}/regenerate-learning`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(dispatchToken ? { "X-Dispatch-Token": dispatchToken } : {}),
      },
      body: JSON.stringify({
        brief_date: body.brief_date,
        phrase_count: body.phrase_count ?? 3,
        language: body.language ?? "fr,ar",
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        { error: "Dispatcher returned an error", details: data },
        { status: response.status },
      );
    }

    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json(
      { error: `Failed to reach dispatcher: ${message}` },
      { status: 502 },
    );
  }
}
