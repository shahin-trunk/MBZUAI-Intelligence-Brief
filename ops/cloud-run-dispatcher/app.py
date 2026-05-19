import json
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DUBAI_TZ = ZoneInfo("Asia/Dubai")

# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("dispatcher")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


for handler in logger.handlers:
    handler.setFormatter(JSONFormatter())

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="GitHub Workflow Dispatcher",
    description="Service for triggering GitHub Actions workflows via API",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
API_KEY_HEADER = APIKeyHeader(name="X-Dispatch-Token", auto_error=False)


def get_api_key(api_key: str | None = Depends(API_KEY_HEADER)) -> str:
    expected = os.getenv("DISPATCH_TOKEN")
    if not expected:
        # If no token configured, allow all (relies on network isolation)
        return "unconfigured"
    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing dispatch token",
        )
    return api_key

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    ok: bool
    service: str

class DispatchResponse(BaseModel):
    ok: bool
    dispatched: bool
    reason: str | None = None
    existing_run: dict | None = None
    ref: str | None = None
    prevent_duplicate_same_day: bool | None = None
    error: str | None = None
    status_code: int | None = None
    response: dict | None = None

class WorkflowRunSummary(BaseModel):
    id: int | None = None
    status: str | None = None
    conclusion: str | None = None
    html_url: str | None = None
    event: str | None = None
    created_at: str | None = None

class RegenerateLearningRequest(BaseModel):
    brief_date: str = Field(..., description="Brief date in YYYY-MM-DD format")
    phrase_count: int = Field(default=3, ge=2, le=8, description="Number of learning sentences (2-8)")
    language: str = Field(default="fr,ar", description="Comma-separated language codes (fr, ar, or fr,ar)")

class RegenerateLearningResponse(BaseModel):
    ok: bool
    dispatched: bool
    workflow: str = "regenerate-learning.yml"
    brief_date: str | None = None
    phrase_count: int | None = None
    error: str | None = None
    status_code: int | None = None
    response: dict | None = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _github_headers() -> dict[str, str]:
    token = _env("GITHUB_TOKEN")
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def _workflow_dispatch_url() -> str:
    owner = _env("GITHUB_OWNER")
    repo = _env("GITHUB_REPO")
    workflow = _env("GITHUB_WORKFLOW_FILE", "daily-brief.yml")
    return (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/actions/workflows/{workflow}/dispatches"
    )


def _list_runs_url(page: int = 1, per_page: int = 100) -> str:
    owner = _env("GITHUB_OWNER")
    repo = _env("GITHUB_REPO")
    workflow = _env("GITHUB_WORKFLOW_FILE", "daily-brief.yml")
    return (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/actions/workflows/{workflow}/runs?per_page={per_page}&page={page}"
    )


async def _request_json(
    client: httpx.AsyncClient,
    url: str,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[int, dict]:
    json_payload = json.dumps(payload) if payload is not None else None
    response = await client.request(method, url, content=json_payload, headers=_github_headers(), timeout=20.0)
    return response.status_code, response.json() if response.content else {}


def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse a GitHub timestamp into an aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _workflow_run_summary(run: dict) -> dict:
    return {
        "id": run.get("id"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "html_url": run.get("html_url"),
        "event": run.get("event"),
        "created_at": run.get("created_at"),
    }


async def _run_exists_today(client: httpx.AsyncClient, ref: str) -> dict | None:
    today_dubai = datetime.now(DUBAI_TZ).date()
    page = 1

    while True:
        status_code, payload = await _request_json(client, _list_runs_url(page=page))
        if status_code != 200:
            raise RuntimeError(f"Failed to list workflow runs: {status_code} {payload}")

        runs = payload.get("workflow_runs", [])
        if not runs:
            break

        for run in runs:
            if run.get("head_branch") != ref:
                continue

            created_dt = _parse_iso_datetime(run.get("created_at", ""))
            if not created_dt:
                continue

            created_dubai = created_dt.astimezone(DUBAI_TZ)
            if created_dubai.date() < today_dubai:
                return None
            if created_dubai.date() != today_dubai:
                continue

            return _workflow_run_summary(run)

        if len(runs) < 100:
            break
        page += 1
    return None


def _learning_dispatch_url() -> str:
    """Build URL to dispatch the regenerate-learning workflow."""
    owner = _env("GITHUB_OWNER")
    repo = _env("GITHUB_REPO")
    return (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/actions/workflows/regenerate-learning.yml/dispatches"
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_model=HealthResponse)
async def healthcheck():
    return HealthResponse(ok=True, service="github-workflow-dispatcher")


@app.post("/dispatch", response_model=DispatchResponse)
async def dispatch(token: str = Depends(get_api_key)):
    ref = os.getenv("GITHUB_REF", "main")
    prevent_duplicates = os.getenv("PREVENT_DUPLICATE_SAME_DAY", "1") == "1"

    logger.info("dispatch_request", extra={"ref": ref, "prevent_duplicates": prevent_duplicates})

    async with httpx.AsyncClient() as client:
        if prevent_duplicates:
            existing = await _run_exists_today(client, ref)
            if existing:
                logger.info("dispatch_skipped_duplicate", extra={"ref": ref})
                return DispatchResponse(
                    ok=True,
                    dispatched=False,
                    reason="run_already_exists_today",
                    existing_run=existing,
                )

        payload = {"ref": ref}
        status_code, response = await _request_json(
            client,
            _workflow_dispatch_url(),
            method="POST",
            payload=payload,
        )
        if status_code not in (200, 201, 204):
            logger.error("dispatch_failed", extra={"status_code": status_code, "response": response})
            return DispatchResponse(
                ok=False,
                dispatched=False,
                error="github_dispatch_failed",
                status_code=status_code,
                response=response,
            )

        logger.info("dispatch_success", extra={"ref": ref})
        return DispatchResponse(
            ok=True,
            dispatched=True,
            ref=ref,
            prevent_duplicate_same_day=prevent_duplicates,
        )


@app.post("/regenerate-learning", response_model=RegenerateLearningResponse)
async def regenerate_learning(
    req: RegenerateLearningRequest,
    token: str = Depends(get_api_key),
):
    """Trigger on-demand regeneration of language learning content for a brief date.

    Dispatches the regenerate-learning.yml workflow with the specified
    phrase_count and language parameters.
    """
    logger.info(
        "regenerate_learning_request",
        extra={
            "brief_date": req.brief_date,
            "phrase_count": req.phrase_count,
            "language": req.language,
        },
    )

    ref = os.getenv("GITHUB_REF", "main")

    payload = {
        "ref": ref,
        "inputs": {
            "brief_date": req.brief_date,
            "phrase_count": str(req.phrase_count),
            "language": req.language,
        },
    }

    async with httpx.AsyncClient() as client:
        status_code, response = await _request_json(
            client,
            _learning_dispatch_url(),
            method="POST",
            payload=payload,
        )

        if status_code not in (200, 201, 204):
            logger.error(
                "regenerate_learning_failed",
                extra={"status_code": status_code, "response": response},
            )
            return RegenerateLearningResponse(
                ok=False,
                dispatched=False,
                brief_date=req.brief_date,
                phrase_count=req.phrase_count,
                error="github_dispatch_failed",
                status_code=status_code,
                response=response,
            )

        logger.info(
            "regenerate_learning_success",
            extra={
                "brief_date": req.brief_date,
                "phrase_count": req.phrase_count,
            },
        )
        return RegenerateLearningResponse(
            ok=True,
            dispatched=True,
            brief_date=req.brief_date,
            phrase_count=req.phrase_count,
        )
