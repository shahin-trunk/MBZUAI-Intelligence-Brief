import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request


app = Flask(__name__)
DUBAI_TZ = ZoneInfo("Asia/Dubai")


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


def _request_json(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = Request(url, data=data, method=method, headers=_github_headers())
    try:
        with urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8") or "{}"
            return response.status, json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8") or "{}"
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed
    except URLError as exc:
        raise RuntimeError(f"GitHub request failed: {exc}") from exc


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


def _run_exists_today(ref: str) -> dict | None:
    today_dubai = datetime.now(DUBAI_TZ).date()
    page = 1

    while True:
        status_code, payload = _request_json(_list_runs_url(page=page))
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


@app.get("/")
def healthcheck():
    return jsonify({"ok": True, "service": "github-workflow-dispatcher"})


@app.post("/dispatch")
def dispatch():
    ref = os.getenv("GITHUB_REF", "main")
    prevent_duplicates = os.getenv("PREVENT_DUPLICATE_SAME_DAY", "1") == "1"

    if prevent_duplicates:
        existing = _run_exists_today(ref)
        if existing:
            return jsonify(
                {
                    "ok": True,
                    "dispatched": False,
                    "reason": "run_already_exists_today",
                    "existing_run": existing,
                }
            )

    payload = {"ref": ref}
    status_code, response = _request_json(
        _workflow_dispatch_url(),
        method="POST",
        payload=payload,
    )
    if status_code not in (200, 201, 204):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "github_dispatch_failed",
                    "status_code": status_code,
                    "response": response,
                }
            ),
            502,
        )

    return jsonify(
        {
            "ok": True,
            "dispatched": True,
            "ref": ref,
            "prevent_duplicate_same_day": prevent_duplicates,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
