# Push Notification Webhook & Cron Configuration

Dashboard-only config (not checked in to Supabase migrations). Keep this doc in
sync with what's set in the Supabase project.

## Secrets required

Set via `supabase secrets set KEY=value` or the Dashboard:

| Key | Source |
|---|---|
| `APNS_KEY_P8` | Contents of the `.p8` auth key file from Apple Developer (newlines preserved) |
| `APNS_KEY_ID` | 10-char key id, shown next to the key in Apple Developer console |
| `APNS_TEAM_ID` | 10-char team id, from Apple Developer membership page |
| `APNS_BUNDLE_ID` | `com.mbzuai.intel` |

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are auto-provided to Edge
Functions at runtime — do not set them manually.

## Database Webhook — `send-brief-notification`

**Dashboard → Database → Webhooks → New**

- **Name**: `send-brief-notification`
- **Table**: `public.briefs`
- **Events**: `UPDATE`
- **HTTP Method**: `POST`
- **URL**: `https://<project-ref>.supabase.co/functions/v1/send-brief-notification`
- **HTTP Headers**: `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>`
- **Conditions** (filter):
  ```
  OLD.audio_status IS DISTINCT FROM 'ready'
  AND NEW.audio_status = 'ready'
  AND NEW.notified_at IS NULL
  ```

The `notified_at IS NULL` gate + the atomic claim inside the function make
re-approval cycles (curation flipping `audio_status` back to `pending` and then
`ready` again) idempotent — the webhook condition no longer matches once
`notified_at` is set.

## Cron — `retry-brief-notifications`

**Dashboard → Database → Cron Jobs → New** (or run the SQL below directly):

```sql
SELECT cron.schedule(
  'retry-brief-notifications',
  '0 5 * * *',  -- 05:00 UTC = 09:00 GST, daily
  $$
  SELECT net.http_post(
    url := 'https://<project-ref>.supabase.co/functions/v1/retry-brief-notifications',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key', true),
      'Content-Type', 'application/json'
    ),
    body := '{}'::jsonb
  );
  $$
);
```

The cron function queries `briefs` for rows where `audio_status='ready' AND
notified_at IS NULL AND brief_date >= today-1` and calls
`send-brief-notification` for each, letting the claim logic there dedupe.

## Build-time env

| Env var | Where | Value |
|---|---|---|
| `NEXT_PUBLIC_APNS_ENV` | Next.js build env for the Capacitor bundle | `sandbox` for TestFlight / dev builds; omit or `production` for App Store |

Enterprise / ad-hoc provisioning profiles always use **production** APNS — make
sure `NEXT_PUBLIC_APNS_ENV` tracks the provisioning profile type, not the build
configuration.
