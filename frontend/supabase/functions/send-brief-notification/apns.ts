import { importPKCS8, SignJWT } from "jose";

type Env = "production" | "sandbox";

const HOSTS: Record<Env, string> = {
  production: "api.push.apple.com",
  sandbox: "api.sandbox.push.apple.com",
};

const JWT_TTL_SECONDS = 50 * 60;

type CachedJwt = { jwt: string; expiresAt: number };
let cached: CachedJwt | null = null;

export async function getJwt(): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  if (cached && cached.expiresAt - now > 60) return cached.jwt;

  const keyId = requireEnv("APNS_KEY_ID");
  const teamId = requireEnv("APNS_TEAM_ID");
  const p8 = requireEnv("APNS_KEY_P8");

  const key = await importPKCS8(p8, "ES256");
  const jwt = await new SignJWT({ iss: teamId, iat: now })
    .setProtectedHeader({ alg: "ES256", kid: keyId, typ: "JWT" })
    .sign(key);

  cached = { jwt, expiresAt: now + JWT_TTL_SECONDS };
  return jwt;
}

export type SendOutcome =
  | { ok: true; status: 200 }
  | { ok: false; status: number; reason: string; removable: boolean };

export async function sendOne(
  token: string,
  env: Env,
  payload: unknown,
  opts: { bundleId: string; expirationEpoch: number; collapseId: string },
): Promise<SendOutcome> {
  const jwt = await getJwt();
  const url = `https://${HOSTS[env]}/3/device/${token}`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      authorization: `bearer ${jwt}`,
      "apns-topic": opts.bundleId,
      "apns-push-type": "alert",
      "apns-priority": "10",
      "apns-expiration": String(opts.expirationEpoch),
      "apns-collapse-id": opts.collapseId,
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (res.status === 200) {
    await res.body?.cancel();
    return { ok: true, status: 200 };
  }

  const text = await res.text();
  let reason = text;
  try {
    reason = (JSON.parse(text).reason as string) ?? text;
  } catch {
    // APNS returns JSON; fall through on parse failure.
  }

  const removable =
    res.status === 410 || (res.status === 400 && reason === "BadDeviceToken");
  return { ok: false, status: res.status, reason, removable };
}

export async function fanOut<T>(
  items: T[],
  concurrency: number,
  work: (item: T) => Promise<void>,
): Promise<void> {
  let idx = 0;
  const workers: Promise<void>[] = [];
  const n = Math.min(concurrency, items.length);
  for (let i = 0; i < n; i++) {
    workers.push((async () => {
      while (true) {
        const j = idx++;
        if (j >= items.length) return;
        await work(items[j]);
      }
    })());
  }
  await Promise.all(workers);
}

function requireEnv(key: string): string {
  const v = Deno.env.get(key);
  if (!v) throw new Error(`Missing required env var: ${key}`);
  return v;
}

export function endOfDayGstEpoch(briefDate: string): number {
  // briefDate is YYYY-MM-DD in GST. End of day (23:59:59 GST) = 19:59:59 UTC same day.
  const [y, m, d] = briefDate.split("-").map(Number);
  const utcMs = Date.UTC(y, m - 1, d, 19, 59, 59);
  return Math.floor(utcMs / 1000);
}
