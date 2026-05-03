# Internal Portal Components

This folder now backs the desktop portal shell used under `frontend/app/(portal)`.
It includes:

- the portal sidebar/chrome
- the currently exposed internal lens pages
- executive-engagement tooling
- several static-data component suites that still exist in code even when
  they are not routed in the current product

There is no active `frontend/app/internal/...` app in this repo anymore.

## Current Route Shape

Portal routes are mounted under `frontend/app/(portal)`:

```text
/(portal)/
  page.tsx                      -> redirects to /brief/today
  brief/[date]/page.tsx         -> published brief
  curation/page.tsx             -> draft selection / ordering / publish UI
  executive-engagement/page.tsx -> engagement list
  executive-engagement/[id]     -> engagement detail
  manual-entry/page.tsx         -> alias to admin manual-entry
  research-requests/page.tsx    -> alias to admin research page
  [lens]/page.tsx               -> dynamic internal lens route
```

The portal shell itself is:

- `PortalChrome.tsx` — desktop-only wrapper around the sidebar
- `PortalSidebar.tsx` — navigation, admin shortcuts, pending-research badge

On mobile, `PortalChrome` skips the sidebar and renders children directly.

## Current Lens Routing

Dynamic lens routing is handled by `frontend/app/(portal)/[lens]/page.tsx`
with config from `frontend/lib/config/lenses.ts`.

Currently exposed as standalone routed lens pages:

- `faculty-excellence`
- `research-impact`
- `visibility`

Still present in code/config but intentionally blocked from routing right now:

- `student-pipeline`
- `student-experience`
- `student-outcomes`

Special case:

- `institutional-health` redirects back to `/brief/today`

## Component Structure

Main lens implementations:

```text
components/internal/
├── faculty-excellence/
├── research-impact/
├── visibility/
├── student-pipeline/
├── student-experience/
├── student-outcomes/
├── executive-engagement/
├── directives/
├── radar/
├── smt-recap/
├── strategic-accountability/
└── shared/
```

Important notes:

- `LensShell.tsx` is the routing handoff from a lens slug to a concrete lens component.
- `executive-engagement/*` is live product UI, backed by API routes and Supabase.
- `directives/`, `radar/`, `smt-recap/`, and `strategic-accountability/` still exist as component/data sets, but they are not mounted as first-class portal routes in the current app.

## Shared Lens Pattern

The lens components generally follow this structure:

1. `LensPageHeader`
2. `AssessmentBlock`
3. evidence sections built from `MetricCard`, charts, and supporting cards
4. lens-specific drilldowns/modals

Shared pieces live in `components/internal/shared/`, including:

- `LensPageHeader`
- `SectionHeader`
- `AssessmentBlock`
- `MetricCard`
- `IntelCard`
- `FilterPills`

## Data Layer

Most of the lens-style portal components still read static JSON from:

```text
frontend/lib/data/internal/
```

Key files currently in use include:

- `faculty-excellence.json`
- `research-impact.json`
- `visibility.json`
- `student-pipeline.json`
- `student-experience.json`
- `student-outcomes.json`
- `strategic-accountability.json`
- `smt-recap.json`

The executive-engagement surface is the main exception: it uses Supabase/API
data in addition to prompt-driven dossier generation routes.

Types live in:

- `frontend/lib/types/internal-intelligence.ts`

## Configuration

`frontend/lib/config/lenses.ts` defines:

- `LENS_CONFIG`
- `getLensConfig`
- `getLensConfigOrThrow`
- `isValidLensSlug`
- month/tag display helpers retained from the older internal-portal model

The config still contains student lens entries even though those routes are
currently blocked in `app/(portal)/[lens]/page.tsx`.

## How To Add Or Re-Expose A Lens

1. Add or update the lens entry in `frontend/lib/config/lenses.ts`.
2. Implement or update the lens component under `components/internal/{slug}/`.
3. Register the component in `components/internal/LensShell.tsx`.
4. If the lens should be reachable, update `frontend/app/(portal)/[lens]/page.tsx`
   so it is not redirected or blocked with `notFound()`.
5. If the lens should appear in navigation, update `PortalSidebar.tsx`.
6. Add or update any static JSON/types under `frontend/lib/data/internal/`
   and `frontend/lib/types/internal-intelligence.ts` as needed.

## Design Notes

The internal portal shares the app-wide token system from `frontend/app/layout.tsx`:

- Literata for headings
- Noto Sans for body/UI
- IBM Plex Mono for labels and metadata

Common card pattern:

```text
rounded-sm border border-border-primary bg-bg-secondary
```
