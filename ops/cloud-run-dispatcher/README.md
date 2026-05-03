# Cloud Run GitHub Workflow Dispatcher

This tiny service lets Google Cloud Scheduler trigger the `Daily Intelligence Brief`
workflow in GitHub Actions without storing the GitHub token in the Scheduler job.

It exposes:

- `GET /` for health checks
- `POST /dispatch` to trigger `workflow_dispatch` on the configured workflow

By default it also prevents duplicate same-day dispatches on the same branch.

## Required environment variables

- `GITHUB_TOKEN`
- `GITHUB_OWNER`
- `GITHUB_REPO`
- `GITHUB_WORKFLOW_FILE`

Optional:

- `GITHUB_REF` (default: `main`)
- `PREVENT_DUPLICATE_SAME_DAY` (default: `1`)

## Recommended values for this repo

- `GITHUB_OWNER=bvahdat38`
- `GITHUB_REPO=MBZUAI-Intelligence-Brief`
- `GITHUB_WORKFLOW_FILE=daily-brief.yml`
- `GITHUB_REF=main`
- `PREVENT_DUPLICATE_SAME_DAY=1`

## One-time GCP setup

Enable services:

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com
```

Create a secret for the GitHub token:

```bash
printf '%s' 'YOUR_GITHUB_TOKEN' | gcloud secrets create github-dispatch-token --data-file=-
```

If the secret already exists:

```bash
printf '%s' 'YOUR_GITHUB_TOKEN' | gcloud secrets versions add github-dispatch-token --data-file=-
```

Create a service account for Cloud Scheduler:

```bash
gcloud iam service-accounts create scheduler-dispatcher \
  --display-name="Scheduler dispatcher"
```

## Deploy Cloud Run

From this directory:

```bash
PROJECT_ID="mbzuai-intelligence-briefing"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding github-dispatch-token \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor"

gcloud run deploy intelligence-brief-dispatcher \
  --source . \
  --region me-central1 \
  --no-allow-unauthenticated \
  --service-account "${RUNTIME_SA}" \
  --set-env-vars GITHUB_OWNER=bvahdat38,GITHUB_REPO=MBZUAI-Intelligence-Brief,GITHUB_WORKFLOW_FILE=daily-brief.yml,GITHUB_REF=main,PREVENT_DUPLICATE_SAME_DAY=1 \
  --set-secrets GITHUB_TOKEN=github-dispatch-token:latest
```

Grant Cloud Scheduler permission to invoke the service:

```bash
gcloud run services add-iam-policy-binding intelligence-brief-dispatcher \
  --region me-central1 \
  --member="serviceAccount:scheduler-dispatcher@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

## Create the Scheduler job

Get the Cloud Run URL first:

```bash
gcloud run services describe intelligence-brief-dispatcher \
  --region me-central1 \
  --format='value(status.url)'
```

Then create the Scheduler job:

```bash
gcloud scheduler jobs create http intelligence-brief-daily \
  --location europe-west1 \
  --schedule "0 7 * * 1-5" \
  --time-zone "Asia/Dubai" \
  --uri "YOUR_CLOUD_RUN_URL/dispatch" \
  --http-method POST \
  --oidc-service-account-email "scheduler-dispatcher@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

Notes:

- In this project, Cloud Scheduler could not be created in `me-central1`, and `me-central2` was blocked by project location policy. `europe-west1` worked and is the currently deployed scheduler region.
- Scheduler region does not need to match the Cloud Run region. The dispatcher service itself is deployed in `me-central1`.

## Test manually

Trigger the Scheduler job once:

```bash
gcloud scheduler jobs run intelligence-brief-daily --location europe-west1
```

Or call Cloud Run directly with an authenticated request from Cloud Shell:

```bash
curl -X POST "$(gcloud run services describe intelligence-brief-dispatcher --region me-central1 --format='value(status.url)')/dispatch" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

Expected success response:

```json
{
  "ok": true,
  "dispatched": true,
  "ref": "main",
  "prevent_duplicate_same_day": true
}
```

If a run for today already exists, the service returns:

```json
{
  "ok": true,
  "dispatched": false,
  "reason": "run_already_exists_today",
  "existing_run": { ... }
}
```
