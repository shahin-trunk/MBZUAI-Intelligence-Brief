import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

type RevalidateBody = {
  secret?: string;
  path?: string;
  paths?: string[];
};

/**
 * On-demand ISR revalidation endpoint.
 *
 * Called by generate_audio.py (and potentially other backend scripts)
 * after updating brief data so the cached page refreshes immediately
 * instead of waiting for the ISR revalidation window.
 *
 * POST /api/revalidate
 * Headers: x-revalidate-secret: <REVALIDATION_SECRET>
 * Body:   { "path": "/brief/today" }
 *
 * The api/ prefix is excluded from auth middleware, so this route
 * is accessible without a session cookie.
 */
function collectPaths(body: RevalidateBody | null): string[] {
  const rawPaths = [
    body?.path,
    ...(Array.isArray(body?.paths) ? body.paths : []),
  ];

  return [...new Set(rawPaths)]
    .filter((path): path is string => typeof path === "string")
    .map((path) => path.trim())
    .filter(Boolean);
}

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => null)) as RevalidateBody | null;
  const secret = request.headers.get("x-revalidate-secret") ?? body?.secret ?? null;
  const expected = process.env.REVALIDATION_SECRET;

  if (!expected || secret !== expected) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const paths = collectPaths(body);

  if (!paths.length) {
    return NextResponse.json(
      { error: "Missing 'path' or 'paths' in request body" },
      { status: 400 }
    );
  }

  for (const path of paths) {
    revalidatePath(path);
  }

  return NextResponse.json({
    revalidated: true,
    path: paths[0],
    paths,
    count: paths.length,
  });
}
