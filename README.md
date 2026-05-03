# Intelligence Dashboard

This repository powers MBZUAI's current intelligence workflow:

- a Python pipeline that collects, filters, scores, enriches, and writes draft brief items
- a human curation app where analysts select, edit, order, and approve the brief
- a published reader experience built around a swipe/card interface
- an admin surface for pipeline oversight, research queues, logos, drops, users, and manual entry
- a Capacitor mobile shell for native packaging and push notifications

The product is no longer a fully automated AI-published brief. The pipeline now produces a draft slate, and publication happens only after human approval.

## Repository Layout

```text
backend/
  main.py                 Pipeline entry point
  ingest_draft.py         Writes draft slates into pending_* tables
  ingest_brief.py         Legacy/fallback direct brief ingestion
  generate_audio.py       Generates audio scripts and uploads audio assets
  config.py               Runtime config, dates, env loading
  models/                 Pydantic contracts
  pipeline/               Collection, filtering, selection, enrichment, writing
  output/                 Generated artifacts and recovery files

frontend/
  app/                    Next.js App Router pages and API routes
  components/             Reader, curation, admin, and portal UI
  lib/                    Auth, Supabase, transforms, hooks, server helpers
  public/                 Static assets
  supabase/migrations/    Schema migrations
  ios/ android/           Capacitor native wrappers

ops/cloud-run-dispatcher/ Cloud Run service that safely triggers GitHub Actions
.github/workflows/        Daily pipeline, audio, recovery, and revalidation workflows
```

## Current Product Shape

### 1. Hybrid brief workflow

The default production flow is:

1. Run the backend pipeline.
2. Write a draft slate into `pending_briefs` and `pending_items`.
3. Open `/curation`.
4. Claim the brief (the curation client also auto-attempts a claim when a pending brief loads).
5. Select, edit, and order items.
6. Approve and publish.
7. Optionally dispatch audio generation.
8. Serve the published brief from `briefs.raw_json` (source of truth) plus the narrow `brief_items` index table.

Important note:

- `PIPELINE_DRAFT_MODE` now defaults to `true` in the orchestrator.
- In normal production, the pipeline stops after Ghostwriter plus optional entity classification and ingests a draft slate. The `Editor` path only runs when `PIPELINE_DRAFT_MODE=false`.
- Audio dispatch happens from the curation approval route when `GITHUB_PAT` is configured; it is not part of `daily-brief.yml`.

### 2. Reader experience

The live brief is served from `/brief/today` and `/brief/[date]`.

Current reader behavior:

- mobile/tablet: card/swipe-first brief experience
- desktop: portal sidebar plus desktop-capable reading/review experience
- published order comes from human curation
- flags, annotations, saved items, research requests, and audio are wired to live backend data

The portal sidebar is desktop-only. On smaller screens the portal chrome is not rendered.

### 3. Analyst curation

The curation app is served from:

- `/curation`
- `/curation/history`
- `/curation/calibration`

Current curation behavior:

- analysts/admins can claim a pending brief
- items are selected from a flat candidate list
- item edits persist server-side
- ordering is a dedicated step
- manual items can be created and attached to the brief
- approval publishes back into the same `briefs` / `brief_items` tables used by the reader
- if today's brief is already published, `/curation` switches into a published-brief editing view instead of falling back to an older pending brief

### 4. Active portal/admin surfaces

Main portal routes currently in use:

- `/brief/today`
- `/brief/[date]`
- `/curation`
- `/executive-engagement`
- `/executive-engagement/[id]`
- `/manual-entry` (portal alias for the admin manual-entry page)
- `/research-requests` (portal alias for the admin research page)
- `/faculty-excellence`
- `/research-impact`
- `/visibility`
- `/flagged`
- `/history`

Primary admin routes currently in use:

- `/admin`
- `/admin/pipeline`
- `/admin/enrichment`
- `/admin/rationalization`
- `/admin/drops`
- `/admin/research`
- `/admin/scout-watchlist`
- `/admin/scout-analytics`
- `/admin/logos`
- `/admin/users`
- `/admin/manual-entry`

Routes/components still present in code but not currently exposed as standalone portal destinations:

- `/student-pipeline`
- `/student-experience`
- `/student-outcomes`

`/[lens]` currently redirects `/institutional-health` back to `/brief/today` and returns `notFound()` for the student routes above.

## Backend Overview

Primary entry points:

- `backend/main.py`
- `backend/pipeline/orchestrator.py`
- `backend/ingest_draft.py`
- `backend/generate_audio.py`
- `backend/config.py`
- `backend/env_loader.py`

Current pipeline stages (in order, run by `backend/pipeline/orchestrator.py`):

1. **Scout** — deterministic collectors (WAM, ADMO, TII, G42 Cloud, Presight, Khazna, Newsletters via Gmail OAuth, X)
2. **Newsletter splitting** — Haiku splits multi-story emails into individual articles
3. **Regional research scout** — Claude + web search finds regional academic/research candidates
4. **Pre-triage enrichment + triage** — thin WAM bodies are filled, then Haiku drops obviously irrelevant items
5. **Date verify + date filter** — parallel HTTP fetch of meta tags / JSON-LD, source-specific bypasses, and cutoff filtering
6. **Dedup** — fuzzy headline match + Haiku semantic dedup
7. **Web-search date verification** — checks newsletter/no-URL items for stale resurfaced stories
8. **Content filter** — Haiku classifies NEWS / NOT_NEWS, with narrow trusted-source bypasses
9. **History dedup** (optional, behind `HISTORY_DEDUP_ENABLED`) — semantic drop against recent published briefs plus recent pending slates
10. **Synthesis** (optional, behind `SYNTHESIS_ENABLED`) — clustering + continuity annotation
11. **Pre-Gatekeeper enrichment + section classifier** — thin items are enriched and assigned into the 5 canonical brief sections
12. **Gatekeeper** — selection and scoring (significance, novelty, UAE relevance) with per-section caps
13. **Manual-entry injection + selected-item enrichment** — queued manual entries are merged into the selected set and thin selected items are enriched
14. **Ghostwriter** — narrative generation
15. **Entity classifier** (optional, behind `ENTITY_CLASSIFIER_ENABLED`) — assigns `primary_entity_category` for badge/icon lookup
16. **Draft ingest** — writes the Ghostwriter slate into `pending_briefs` / `pending_items`

Legacy direct-publish-only extension:

- **Editor** — final QA and brief assembly, only when `PIPELINE_DRAFT_MODE=false`

`--from-stage` resume points: `scout`, `content_filter`, `gatekeeper`, `ghostwriter`, `editor`. Artifacts are written into `backend/output/` for inspection and same-day recovery. The GitHub recovery workflow exposes only `content_filter` and `ghostwriter`; `gatekeeper` is kept as a local/debug resume path because it skips Synthesis annotations and falls back to legacy overlap handling.

Model assignments (sources of truth: `backend/config.py`, `backend/pipeline/card_batch.py`, individual stage modules):

- **Sonnet 4.6** — default `MODEL` in config, including Gatekeeper, Ghostwriter, Editor, regional scout, and higher-stakes enrichment paths
- **Haiku 4.5** — Content filter, newsletter splitting, dedup, section classifier, entity classifier

## Frontend Overview

Frontend stack:

- Next.js 16 App Router
- React 19
- Tailwind CSS 4
- Supabase
- Capacitor for iOS/Android

Important frontend areas:

- `frontend/app/(portal)/brief/[date]/page.tsx` — published brief route
- `frontend/components/presidential-brief/*` — live reader/card experience
- `frontend/components/card-reader/*` — card reader and review components
- `frontend/components/curation/*` — analyst curation workflow
- `frontend/app/admin/*` — admin pages
- `frontend/app/api/curation/approve/route.ts` — publish path from pending brief to `briefs` + `brief_items`
- `frontend/lib/api/helpers.ts` — manual session validation + service-role client handoff
- `frontend/middleware.ts` — edge auth gate for non-API routes
- `frontend/lib/transforms/brief.ts` — published brief normalization
- `frontend/lib/auth/AuthProvider.tsx` — client auth context
- `frontend/components/internal/PortalSidebar.tsx` — desktop-only portal navigation

## Data Model Notes

Published brief data:

- `briefs`
- `briefs.raw_json` is the source of truth for published reader content and archive/history pages.
- `brief_items`
- `brief_items` is now a narrow cross-date index used for lightweight lookups and compatibility, not the full rendered brief payload.

Draft / curation data:

- `pending_briefs`
- `pending_items`
- `manual_items`
- `curation_decisions`

Other important live data:

- annotations
- flags
- saved items
- research requests
- pipeline runs
- executive engagement records and materials
- admin pipeline run hydration

## Auth Notes

- Non-public pages are protected by `frontend/middleware.ts`, which validates the Supabase auth cookie in the Edge runtime.
- API routes typically call `getAuthenticatedClient()` in `frontend/lib/api/helpers.ts`, which validates the session manually, then uses a service-role Supabase client for DB access.
- Because the service-role client bypasses RLS, route handlers must explicitly scope user-owned queries by `user.id`.

## Environment

The repo uses:

- root `.env` for backend/runtime secrets
- `frontend/.env.local` for frontend and Supabase configuration

Common environment variables:

- `ANTHROPIC_API_KEY`
- `SERPER_API_KEY`
- `VOICE_API_KEY`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `REVALIDATION_SECRET`
- `GITHUB_PAT`
- `RESEND_API_KEY`
- `SITE_URL`
- `NEXT_PUBLIC_SITE_URL`
- `ENABLE_AUDIO_BRIEF`
- `ENABLE_FRENCH_AUDIO`
- `FRENCH_VOICE_ID`
- `PIPELINE_DRAFT_MODE`

Collector credentials sometimes used locally:

- `credentials.json`
- `token.json`

## Local Development

### Install dependencies

Backend:

```bash
pip install -r requirements.txt
```

Frontend:

```bash
cd frontend
npm install
```

### Run the backend pipeline

From `backend/`:

```bash
python3.11 main.py
```

Resume from a later stage:

```bash
python3.11 main.py --from-stage content_filter
python3.11 main.py --from-stage gatekeeper
python3.11 main.py --from-stage ghostwriter
python3.11 main.py --from-stage editor
```

### Write a draft slate

```bash
cd backend
python3.11 ingest_draft.py
python3.11 ingest_draft.py --date 2026-04-11
```

### Legacy direct-ingest path

```bash
cd backend
python3.11 ingest_brief.py
python3.11 ingest_brief.py --date 2026-04-11
python3.11 ingest_brief.py --backfill
```

### Generate audio

```bash
cd backend
python3.11 generate_audio.py
python3.11 generate_audio.py --date 2026-04-11
python3.11 generate_audio.py --date 2026-04-11 --from-db
python3.11 generate_audio.py --script-only
```

### Run the frontend

```bash
cd frontend
npm run dev
```

Useful checks:

```bash
cd frontend
npm run build
npx tsc --noEmit
```

Note:

- `npm run lint` is currently affected by an ESLint config serialization issue in this repo, so build/typecheck are the more reliable verification signals at the moment.

### Native shell

```bash
cd frontend
npm run cap:sync
npm run cap:open:ios
npm run cap:open:android
```

## GitHub Workflows

Current workflow files:

- `.github/workflows/daily-brief.yml`
- `.github/workflows/generate-audio.yml`
- `.github/workflows/recover-daily-brief.yml`
- `.github/workflows/revalidate-brief.yml`

High-level usage:

- `daily-brief.yml` runs the pipeline and ingests a draft slate into curation tables
- `generate-audio.yml` handles audio generation after approval/publication
- `recover-daily-brief.yml` restores artifacts and resumes failed same-day runs back into the draft-ingest flow
- `revalidate-brief.yml` revalidates frontend brief routes

All workflows use `workflow_dispatch` triggers. The daily run is initiated externally by `ops/cloud-run-dispatcher/`, a Flask service deployed to Cloud Run that bridges Cloud Scheduler → GitHub Actions (Cloud Scheduler fires `0 7 * * 1-5` = 7:00 AM GST weekdays). The dispatcher reads its GitHub token from Secret Manager and prevents duplicate same-day runs.

## Good Entry Points

If you are orienting yourself, start here:

- `backend/main.py`
- `backend/pipeline/orchestrator.py`
- `backend/ingest_draft.py`
- `backend/generate_audio.py`
- `frontend/app/(portal)/brief/[date]/page.tsx`
- `frontend/components/presidential-brief/BriefViewRouter.tsx`
- `frontend/components/curation/CurationWorkspace.tsx`
- `frontend/app/admin/page.tsx`
- `frontend/components/internal/PortalSidebar.tsx`
- `frontend/lib/transforms/brief.ts`
- `frontend/supabase/migrations/`

## Related Readmes

- [frontend/README.md](frontend/README.md)
- [ops/cloud-run-dispatcher/README.md](ops/cloud-run-dispatcher/README.md)
