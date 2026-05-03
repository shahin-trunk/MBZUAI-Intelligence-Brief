## Intelligence Dashboard Frontend

This app renders the MBZUAI intelligence brief, provides reader workflows
such as annotations and flags, provides the analyst curation workspace,
and exposes admin/internal portal views for pipeline monitoring and
executive workflows.

## Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Useful checks:

```bash
npx tsc --noEmit
npm run build
npm run lint
```

Notes:

- `npm run build` and `npx tsc --noEmit` are the most reliable repo-wide
  verification signals.
- `npm run lint` exists, but this repo has had intermittent ESLint config
  serialization issues, so lint is a weaker signal than build/typecheck.

## Environment

Required environment variables include:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `REVALIDATION_SECRET`
- `RESEND_API_KEY`

Optional email settings:

- `RESEND_FROM_EMAIL`
- `RESEND_NOTIFY_EMAIL`
- `NEXT_PUBLIC_SITE_URL`

Commonly needed for the full app, depending on the flow:

- `SITE_URL`
- `GITHUB_PAT`
- `ENABLE_AUDIO_BRIEF`
- `ENABLE_FRENCH_AUDIO`

## Main Routes

- `/brief/today`
- `/brief/[date]`
- `/curation`
- `/history`
- `/flagged`
- `/executive-engagement`
- `/manual-entry`
- `/research-requests`
- `/admin`

## Notes

- Published brief content is read from `briefs.raw_json` in Supabase and
  normalized in `lib/transforms/brief.ts`.
- `brief_items` is now a narrow index table; it is not the source of truth
  for the reader experience.
- The curation publish path lives in `app/api/curation/approve/route.ts`,
  which writes `briefs`/`brief_items`, revalidates the brief routes, and
  optionally dispatches audio generation.
- Production builds currently depend on `next/font` fetching Google Fonts.
- Auth is cookie-based. Non-API routes are gated by `middleware.ts`, while
  API routes typically validate the session manually in `lib/api/helpers.ts`
  and then use a service-role Supabase client.
