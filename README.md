# MBZUAI Intelligence Brief

An AI-powered presidential daily intelligence briefing system for **MBZUAI** (Mohamed bin Zayed University of Artificial Intelligence). The system automatically collects intelligence from 9+ institutional sources, applies a 16-stage AI pipeline for filtering, scoring, and narrative generation, and delivers a curated daily brief through a swipe-based reader experience — with human analyst curation as a mandatory gate before publication.

> **For**: Prof. Eric Xing, President of MBZUAI  
> **Schedule**: Daily (Monday–Friday) by 6:00 AM GST  
> **Target**: 8–25 items across 5 sections  
> **Format**: Card/swipe reader (mobile) + portal sidebar (desktop) + audio briefing

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION FLOW                                │
│                                                                       │
│  Cloud Scheduler      ┌──────────────────┐                            │
│  (7am GST weekdays)──▶│ Cloud Run        │──▶ GitHub Actions          │
│                        │ Dispatcher        │    (workflow_dispatch)    │
│                        └──────────────────┘                            │
│                                                                       │
│  GitHub Actions ───▶ Python Pipeline ───▶ pending_briefs ───▶ Analyst │
│  (daily-brief.yml)   (16 stages)          pending_items     Curation  │
│                                                                       │
│  Analyst ───▶ Approve ───▶ briefs ───▶ Frontend Reader ───▶ Executive │
│  Curation                                (Next.js 16)       Consumer  │
│                                                                       │
│                                      └──▶ Audio Briefing              │
│                                           (ElevenLabs TTS)            │
│                                                                       │
│  Docker Compose ───▶ EC2                     Vercel                   │
│  (Traefik + Frontend                        (Vercel serverless)       │
│   + Dispatcher)                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

### Core Principles

- **Hybrid AI-Human**: Pipeline writes a draft slate — analysts select, edit, and approve. No direct AI publication.
- **Deterministic Collection**: Hard-coded institutional sources, not dynamic feed crawling.
- **Fail-Open Design**: One stage failure doesn't kill the pipeline; downstream reconciliation catches omissions.
- **Resumable Pipeline**: `--from-stage` flag enables checkpoint-based recovery.
- **Audit Trail**: Every pipeline stage, drop decision, and curation action is logged.

---

## Repository Structure

```
├── backend/                          # Python pipeline
│   ├── main.py                        # Entry point (--from-stage support)
│   ├── config.py                      # Runtime config, dates, constants
│   ├── env_loader.py                  # Environment variable multi-source loader
│   ├── ingest_draft.py                # Writes draft slates to pending tables
│   ├── ingest_brief.py                # Legacy direct brief ingestion
│   ├── generate_audio.py              # Audio script generation + TTS upload
│   ├── models/
│   │   └── schemas.py                 # Pydantic data contracts (20+ models)
│   ├── pipeline/                      # 25+ pipeline modules
│   │   ├── orchestrator.py            # Main stage orchestration (async)
│   │   ├── collector.py               # Collection from 9 sources
│   │   ├── content_filter.py          # NEWS/NOT_NEWS classification
│   │   ├── dedup.py                   # 3-stage dedup (URL/fuzzy/semantic)
│   │   ├── synthesis.py               # Event clustering + continuity
│   │   ├── history_dedup.py           # Cross-day repeat detection
│   │   ├── gatekeeper.py              # Selection + scoring (Sonnet)
│   │   ├── ghostwriter.py             # Narrative generation (Sonnet)
│   │   ├── entity_classifier.py       # Entity category tagging (Haiku)
│   │   ├── enricher.py                # URL content enhancement
│   │   ├── date_verify.py             # Publish date from meta tags
│   │   ├── web_search_verify.py       # Fallback date via Serper
│   │   ├── event_tuples.py            # Structured event extraction
│   │   ├── section_classifier.py      # Section assignment (Haiku)
│   │   ├── entity_identity.py         # Entity linking
│   │   ├── entity_category.py         # Entity categorization
│   │   ├── exhibit_formatter.py       # Exhibit formatting
│   │   ├── manual_entries.py          # Analyst queued item injection
│   │   ├── model_release.py           # Model release metadata extraction
│   │   ├── card_batch.py              # Parallel ghostwriter per section
│   │   ├── gk_rekeyer.py              # Gatekeeper output stabilization
│   │   └── seen_cache.py              # URL cache across runs
│   ├── prompts/                       # Podcast script prompt templates
│   ├── evals/                         # Evaluation scripts (content filter, gatekeeper, ghostwriter)
│   ├── tests/                         # 38 test files + fixtures
│   └── output/                        # Generated artifacts + recovery files
│
├── frontend/                          # Next.js 16 web application
│   ├── app/                           # App Router pages + API routes
│   │   ├── (portal)/                  # Auth-gated portal (brief, curation, lenses)
│   │   ├── admin/                     # 11 admin pages (pipeline, drops, logos, users, etc.)
│   │   ├── api/                       # 40+ server API routes
│   │   ├── login/                     # OAuth login page
│   │   └── auth/callback/             # OAuth callback handler
│   ├── components/                    # 100+ React components
│   │   ├── presidential-brief/        # Brief reader card/swipe UI (35+ files)
│   │   ├── card-reader/               # Swipeable card interaction
│   │   ├── curation/                  # Analyst workspace (select, edit, order)
│   │   ├── admin/                     # Dashboard panels (charts, logos, drops)
│   │   ├── brief/                     # Brief display components
│   │   ├── internal/                  # Intelligence lenses components
│   │   └── ui/                        # Shadcn/Radix UI primitives
│   ├── lib/                           # Utilities, hooks, transforms
│   │   ├── api/                       # API helpers + queries + mutations
│   │   ├── auth/                      # Auth provider + session management
│   │   ├── transforms/                # Brief JSON → TypeScript interfaces
│   │   ├── hooks/                     # Custom React hooks
│   │   ├── types/                     # TypeScript type definitions
│   │   ├── supabase/                  # Supabase client initialization
│   │   └── config/                    # App configuration + lens definitions
│   ├── supabase/
│   │   ├── migrations/                # 20 sequential database migrations
│   │   └── functions/                 # Supabase Edge Functions
│   ├── ios/                           # Capacitor iOS native wrapper
│   └── android/                       # Capacitor Android native wrapper
│
├── prompts/                           # 16 LLM system prompt templates
│   ├── gatekeeper_prompt.md            # Selection + scoring (314 lines)
│   ├── ghostwriter_prompt.md           # Narrative generation (424 lines)
│   ├── synthesis_prompt.md             # Event clustering (189 lines)
│   ├── history_dedup_prompt.md         # Cross-day dedup (232 lines)
│   ├── content_filter_prompt.md        # NEWS/NOT_NEWS (166 lines)
│   ├── event_extraction_prompt.md      # Event tuples (207 lines)
│   └── ... (10 more prompt files)
│
├── ops/cloud-run-dispatcher/          # Cloud Run → GitHub Actions bridge
│   └── app.py                          # Flask service (184 lines)
│
├── .github/workflows/                 # 5 CI/CD workflows
│   ├── daily-brief.yml                 # Main pipeline (workflow_dispatch)
│   ├── deploy.yml                      # Auto-deploy to EC2 (push to main)
│   ├── generate-audio.yml              # Audio generation (workflow_dispatch)
│   ├── recover-daily-brief.yml         # Pipeline recovery
│   └── revalidate-brief.yml            # ISR cache revalidation
│
├── .qoder/skills/                     # Qoder AI coding assistant skill
├── scripts/                           # Dev scripts
│   ├── run-pipeline.sh
│   ├── run-frontend.sh
│   └── check-code.sh
│
├── Dockerfile                          # Docker build (Next.js standalone)
├── docker-compose.yml                  # Traefik + Frontend + Dispatcher
├── deploy.sh                           # Deployment management script
├── deploy.env.example                  # Deployment env template
├── requirements.txt                    # Python dependencies
└── .gitignore
```

---

## Backend Pipeline

### Data Flow (16 Stages)

| # | Stage | Model | Time | Purpose |
|---|-------|-------|------|---------|
| 1 | **Scout** | Deterministic | — | Collect from 9 sources (WAM, ADMO, TII, G42, Presight, Khazna, Gmail newsletters, X, regional research) |
| 2 | **Newsletter Splitter** | Haiku 4.5 | 2m | Split multi-story emails into individual articles |
| 3 | **Regional Research Scout** | Sonnet 4.6 + Serper | 5m | Web search for regional academic/research news |
| 4 | **Pre-Triage Enrichment** | — | 2m | Fetch full article bodies for thin sources |
| 5 | **Triage** | Haiku 4.5 | 2m | Drop obviously irrelevant items (inverted-default: editorial wires auto-keep) |
| 6 | **Date Verify** | — | ∥ | Extract publish dates via HTTP meta tags / JSON-LD |
| 7 | **Dedup** (3-stage) | Haiku 4.5 | 2m | URL canonicalization → fuzzy headline → semantic/tuple comparison |
| 8 | **Web Search Date Verify** | Serper | 2m | Check newsletter/no-URL items for stale resurfaced stories |
| 9 | **Content Filter** | Haiku 4.5 | 2m | NEWS/NOT_NEWS binary classification (batch size: 22) |
| 10 | **History Dedup**\* | Sonnet 4.6 | 5m | Drop items matching published briefs + pending slates (14-day window) |
| 11 | **Synthesis**\* | Sonnet 4.6 | 10m | Event clustering + continuity annotation (new/continuation/restatement) |
| 12 | **Section Classifier** | Haiku 4.5 | 2m | Assign to 5 canonical sections |
| 13 | **Gatekeeper** | Sonnet 4.6 | 10m | Score + select top items per section (cluster-aware tier caps) |
| 14 | **Manual-Entry Injection** | — | — | Merge analyst-queued items |
| 15 | **Ghostwriter** | Sonnet 4.6 | 10m | Generate key_bullets, analysis, context, implication (~110 words/card) |
| 16 | **Draft Ingest** | — | — | Write to `pending_briefs` + `pending_items` (analyst review) |

> \* Optional — controlled by feature flags: `HISTORY_DEDUP_ENABLED`, `SYNTHESIS_ENABLED`, `ENTITY_CLASSIFIER_ENABLED`

**Legacy**: Stage **Editor** (final QA + assembly) runs only when `PIPELINE_DRAFT_MODE=false`.

### Collection Sources

| Source | Type | Scout Mapping |
|--------|------|--------------|
| WAM (UAE News Agency) | Sitemap XML | UAE |
| ADMO (Abu Dhabi Media Office) | HTML scraper | UAE |
| TII (Technology Innovation Institute) | HTML scraper | Model releases |
| G42 | HTML scraper | International business |
| Presight AI | HTML scraper | International business |
| Khazna Data Centers | WordPress REST API | International business |
| Gmail Newsletters (22 whitelisted) | Gmail API OAuth | Cross-section |
| X / @hhtbzayed | X API v2 | UAE |
| Regional Research (Serper) | Web search API | Regional academic |

### Model Routing

| Model | Cost | Used For |
|-------|------|----------|
| **Sonnet 4.6** | $3/M input, $15/M output | Gatekeeper, Ghostwriter, Regional Scout, History Dedup, Synthesis, Editor |
| **Haiku 4.5** | $0.80/M input, $4/M output | Content Filter, Newsletter Splitter, Dedup, Section Classifier, Entity Classifier, Triage |

- **Typical run cost**: ~560K tokens → ~$2-3 USD
- **Typical wall time**: 30–45 minutes

### Running the Pipeline

```bash
# Full pipeline
cd backend && python3.11 main.py

# Resume from checkpoint
cd backend && python3.11 main.py --from-stage content_filter
cd backend && python3.11 main.py --from-stage gatekeeper
cd backend && python3.11 main.py --from-stage ghostwriter

# Draft ingest (write pipeline output to pending tables)
cd backend && python3.11 ingest_draft.py
cd backend && python3.11 ingest_draft.py --date 2026-04-11

# Audio generation
cd backend && python3.11 generate_audio.py --date 2026-04-11 --from-db
cd backend && python3.11 generate_audio.py --script-only
```

### Pipeline Design Patterns

- **Deterministic, fail-open stages**: Each collector independently handles failures. If Haiku errors on content filter, all items pass through.
- **Resumability**: Intermediate outputs cached as `{stage}_YYYY-MM-DD.json` in `backend/output/`. Recovery workflows support `content_filter` and `ghostwriter` resume points.
- **Chunked parallelism**: Content filter (batches of 22), Gatekeeper (per-section chunks), Ghostwriter (per-section chunks) all run in parallel.
- **Drop audit trail**: Every dropped item logged with reason + stage. Written to `dropped_items` table + JSON artifact.
- **Token tracking**: Total input/output tokens tracked per stage for cost estimation.

---

## Frontend Application

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 16 (App Router) |
| UI Runtime | React 19 |
| Styling | Tailwind CSS 4 |
| UI Components | Shadcn UI + Radix UI |
| Animation | @react-spring/web + @use-gesture/react |
| Drag & Drop | @dnd-kit |
| Charts | Recharts |
| Icons | lucide-react + flag-icons |
| Database | Supabase PostgreSQL |
| Auth | Supabase Auth (OAuth, cookie-based) |
| State | React Context (Auth, Toast, BriefInteraction) |
| Mobile | Capacitor (iOS + Android) |
| Testing | Vitest + Testing Library + jsdom |

### Page Structure

```
/portal                           # Auth-gated portal shell
  /brief/today                     # Today's published brief (ISR, 1hr revalidation)
  /brief/[date]                    # Archived brief by date
  /curation                        # Analyst curation workspace
  /curation/history                # Curation audit trail
  /curation/calibration            # Model calibration data
  /executive-engagement            # Executive meeting tracking
  /executive-engagement/[id]       # Individual engagement
  /research-requests               # Follow-up research management
  /manual-entry                    # Queue manual pipeline items
  /flagged                         # Reader-flagged items
  /history                         # Brief archive calendar
  /[lens]                          # Internal intelligence lenses

/admin                            # Admin dashboard
  /admin/pipeline                  # Pipeline run history + funnel visualization
  /admin/enrichment                # Content enrichment metrics
  /admin/rationalization           # Gatekeeper score breakdown
  /admin/drops                     # Dropped items analysis
  /admin/research                  # Research request management
  /admin/scout-analytics           # Collection source metrics
  /admin/scout-watchlist           # Entity watchlist
  /admin/logos                     # Entity logo management (upload, categorize)
  /admin/users                     # User roles + permissions
  /admin/manual-entry              # Manual entry queue
```

### Authentication Flow

```
Request → Edge Middleware (middleware.ts)
  → Reads Supabase auth cookie
  → Validates via Supabase REST API (no SDK, edge-compatible)
  → Valid? → Serve page
  → Invalid? → Redirect to /login?redirectTo=<original>

Post-login:
  OAuth callback → Session stored in cookie → Redirect
  Client: AuthProvider fetches /api/me → user profile

API Routes:
  getAuthenticatedClient() validates session manually
  Returns service-role Supabase client (bypasses RLS)
  Routes must scope queries by user.id explicitly
```

### Key Frontend Features

**Brief Reader** — Card/swipe interface with:
- Multiple view modes (card swipe, vertical snap deck, list view)
- Audio briefing (English + French via ElevenLabs)
- Annotations, flags, saves, research requests
- Section navigation with progress tracking
- Responsive: mobile → card swipe, desktop → portal sidebar

**Curation Workspace** — Three-phase analyst workflow:
1. **Select** — Choose items from Gatekeeper candidates (proposed/pool tiers)
2. **Edit** — Modify headline, narrative, section, significance
3. **Order** — Drag-and-drop reorder within sections
- Manual item creation on-the-fly
- Full audit trail in `curation_decisions`

**Internal Intelligence Lenses** — Institutional health dashboards:
- Faculty Excellence, Research Impact, Student Pipeline
- Visibility & Influence, Strategic Accountability
- Executive Engagement tracking with AI dossier generation

### API Routes (40+ endpoints)

```
GET    /api/me                           # Current user profile
GET    /api/briefs                       # List published briefs
GET    /api/briefs/[date]/items          # Brief items by date
PATCH  /api/briefs/[date]/items/[id]     # Update item
POST   /api/curation/pending             # Claim pending brief
GET    /api/curation/items/[id]          # Get curation item
PATCH  /api/curation/items/[id]          # Update curation item
POST   /api/curation/items/reorder       # Reorder items
POST   /api/curation/approve             # Publish brief
POST   /api/curation/manual-item         # Add manual item
GET    /api/admin/pipeline               # Pipeline run data
GET    /api/admin/drops                  # Dropped items analysis
POST   /api/admin/logos                  # Upload entity logo
GET    /api/admin/users                  # User management
POST   /api/revalidate                   # ISR cache purge
POST   /api/internal/generate-dossier    # AI dossier generation
... (40+ total endpoints)
```

---

## Database Schema (Supabase PostgreSQL)

### Published Content

`briefs` — One row per date. `raw_json` is the **source of truth** for the reader experience.

| Column | Type | Purpose |
|--------|------|---------|
| `brief_date` | DATE PK | Brief date (YYYY-MM-DD) |
| `raw_json` | JSONB | Full RawPipelineBrief (source of truth) |
| `audio_url` | TEXT | English audio URL |
| `audio_script` | TEXT | English TTS script |
| `audio_url_fr` | TEXT | French audio URL |
| `audio_script_fr` | TEXT | French TTS script |
| `audio_status` | TEXT | pending/generating/complete/failed |
| `generated_at` | TIMESTAMPTZ | Creation timestamp |
| `metadata` | JSONB | item_count, sources_consulted, pipeline_cost_usd |

`brief_items` — Narrow index for lightweight lookups (NOT source of truth).

### Draft / Curation

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `pending_briefs` | Pipeline run + claim state | brief_date, status (pending/in_review/approved/published), claimed_by, pipeline_stats |
| `pending_items` | Gatekeeper candidates | brief_id, tier (proposed/pool), section, headline, raw_item JSONB |
| `curation_decisions` | Audit trail | decision (keep/remove/promote/demote/edit/reorder/add), edit_fields JSONB |
| `manual_items` | Analyst-created items | headline, section, significance_level, full card shape |

### Reader Interactions

| Table | Purpose |
|-------|---------|
| `annotations` | User notes on brief items |
| `flags` | Item flagging (follow-up, important, share) |
| `saved_items` | Bookmarked items |
| `research_requests` | Follow-up research tasks |
| `reader_interactions` | Page view tracking |
| `push_tokens` | Mobile push notification tokens |

### Admin / Meta

| Table | Purpose |
|-------|---------|
| `user_profiles` | User roles (reader/analyst/editor/admin) |
| `entity_logos` | Entity badge/image resolution |
| `pipeline_runs` | Pipeline execution history |
| `scout_seen_urls` | Cross-run URL dedup |
| `engagements` | Executive meeting tracking |
| `engagement_materials` | Meeting briefings + dossiers |
| `engagement_followups` | Post-meeting Q&A |

---

## CI/CD & Operations

### GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `daily-brief.yml` | workflow_dispatch (Cloud Scheduler → Cloud Run) | Run full pipeline → ingest draft |
| `deploy.yml` | Push to main (paths: frontend/, Dockerfile, docker-compose.yml) | SSH → Docker Compose rebuild on EC2 |
| `generate-audio.yml` | workflow_dispatch (manual or from curation approve) | Generate TTS audio → upload to Supabase Storage |
| `recover-daily-brief.yml` | workflow_dispatch (manual) | Resume failed pipeline from content_filter or ghostwriter |
| `revalidate-brief.yml` | repository_dispatch (from curation approve) | ISR cache purge for published brief |

### Infrastructure

```
Cloud Scheduler (0 7 * * 1-5, Asia/Dubai)
  │  POST /dispatch
  ▼
Cloud Run (ops/cloud-run-dispatcher/app.py)
  │  GitHub API workflow_dispatch
  ▼
GitHub Actions Runner
  │  Python 3.11 + pip + ffmpeg
  ▼
Docker Compose (Ubuntu EC2, brief.audarai.com)
  ├── Traefik v3.7 (reverse proxy, Let's Encrypt TLS)
  ├── Next.js 16 (standalone, port 3000)
  └── Cloud Run Dispatcher (Flask, port 8080)
```

### Deployment Commands

```bash
# Full deploy
./deploy.sh deploy

# Check service status
./deploy.sh status

# View logs
./deploy.sh logs

# Local Docker development
docker compose --env-file deploy.env up -d
```

---

## Environment Variables

### Required

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude API access |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase admin key |

### Backend

| Variable | Purpose |
|----------|---------|
| `SERPER_API_KEY` | Web search API for date verification |
| `VOICE_API_KEY` | ElevenLabs TTS API key |
| `X_BEARER_TOKEN` | X API v2 token |
| `GITHUB_PAT` | GitHub personal access token (audio dispatch) |
| `PIPELINE_DRAFT_MODE` | `true` = draft mode (default), `false` = direct publish |

### Frontend

| Variable | Purpose |
|----------|---------|
| `REVALIDATION_SECRET` | ISR revalidation endpoint auth |
| `RESEND_API_KEY` | Email API (research requests) |
| `SITE_URL` | Deployment URL for auth redirects |
| `NEXT_PUBLIC_SITE_URL` | Public site URL |

### Feature Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `PIPELINE_DRAFT_MODE` | `true` | Write draft vs. publish directly |
| `SYNTHESIS_ENABLED` | `true` | Event clustering + continuity annotation |
| `HISTORY_DEDUP_ENABLED` | `true` | Cross-day repeat detection |
| `ENTITY_CLASSIFIER_ENABLED` | `true` | Entity category tagging for UI badges |
| `ENABLE_AUDIO_BRIEF` | `false` | Audio briefing generation |
| `ENABLE_FRENCH_AUDIO` | `false` | French audio track |

---

## Local Development

### Prerequisites

```bash
# Python 3.11+
python3.11 --version

# Node.js 22+
node --version

# Docker (optional, for local compose)
docker --version
```

### Setup

```bash
# Backend dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend && npm install

# Environment files
cp deploy.env.example deploy.env
cp frontend/.env.local.example frontend/.env.local
# Edit with your keys
```

### Run

```bash
# Frontend dev server (http://localhost:3000)
cd frontend && npm run dev

# Backend pipeline
cd backend && python3.11 main.py

# Partial pipeline (resume from checkpoint)
cd backend && python3.11 main.py --from-stage ghostwriter
```

### Verification

```bash
# TypeScript type check (primary signal)
cd frontend && npx tsc --noEmit

# Build check
cd frontend && npm run build

# Unit tests (Vitest)
cd frontend && npx vitest run

# Python pipeline evals
cd backend && python evals/eval_content_filter.py

# Notes:
# - npm run lint has intermittent ESLint config issues — use tsc + build instead
```

---

## Testing Strategy

### Backend Tests (38 files)

Test framework: Pytest + pytest-asyncio

| Test Area | Key Files |
|-----------|-----------|
| Pipeline E2E | `test_pipeline_e2e.py` |
| Dedup | `test_dedup.py`, `test_history_dedup.py` |
| Gatekeeper | `test_gatekeeper_ab.py`, `test_gk_rekeyer.py` |
| Ghostwriter | `test_ghostwriter_refusal.py` |
| Content Filter | Via eval scripts |
| Entity | `test_entity_classifier.py`, `test_entity_identity.py` |
| Event Extraction | `test_event_tuples.py`, `test_deal_detection.py` |
| Synthesis | `test_synthesis.py` |
| Enrichment | `test_enricher_fetch.py` |
| Rendering | `test_e2e_rendering.py`, `test_exhibits_comprehensive.py` |

Skip markers available: `skip_no_anthropic`, `skip_no_serper` (tests gracefully skip when API keys aren't set locally).

### Frontend Tests

- **Vitest** + **jsdom** environment
- Key test files: `brief.test.ts`, `entity-category.test.ts`, `manual-entry.test.ts`
- Run: `cd frontend && npx vitest run`

---

## Key Design Decisions

1. **Draft mode as default**: Pipeline writes pending slates; analysts must explicitly approve. Prevents hallucinated briefs from reaching the president.

2. **Inverted-default triage**: Editorial wires (Bloomberg, FT, Reuters, etc.) auto-keep unless clearly junk — avoids false-negative drops on hard news.

3. **3-stage dedup**: URL → fuzzy headline → semantic/tuple. Reduces LLM reliance while maintaining precision. Phase 3+ uses mechanical event-tuple comparison (no LLM).

4. **Cluster-aware Gatekeeper**: Synthesis groups related items; Gatekeeper enforces per-cluster tier caps (head_of_state: uncapped, major: ≤3, standard: ≤1).

5. **`briefs.raw_json` as source of truth**: The reader reads from the JSONB blob. `brief_items` is a narrow index for lightweight queries only.

6. **Chunked parallelism**: Content filter, Gatekeeper, and Ghostwriter all run in per-section chunks. Pipeline completes in ~30-45min despite sequential Sonnet calls.

7. **Edge middleware auth**: Supabase cookie validation in Next.js Edge Runtime — no SDK dependency, pure REST API calls.

---

## Entry Points for New Developers

| Area | Start Here |
|------|------------|
| Pipeline logic | `backend/main.py`, `backend/pipeline/orchestrator.py` |
| Pipeline schemas | `backend/models/schemas.py` |
| Config & constants | `backend/config.py` |
| Prompts | `prompts/gatekeeper_prompt.md`, `prompts/ghostwriter_prompt.md` |
| Frontend routes | `frontend/app/(portal)/brief/[date]/page.tsx` |
| Brief reader UI | `frontend/components/presidential-brief/BriefViewRouter.tsx` |
| Curation UI | `frontend/components/curation/CurationWorkspace.tsx` |
| Admin | `frontend/app/admin/page.tsx` |
| Brief transforms | `frontend/lib/transforms/brief.ts` |
| Auth flow | `frontend/middleware.ts`, `frontend/lib/auth/AuthProvider.tsx` |
| API helpers | `frontend/lib/api/helpers.ts` |
| Database | `frontend/supabase/migrations/` |

---

## License

Proprietary — MBZUAI Internal Use
