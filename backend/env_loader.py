from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_project_env() -> list[Path]:
    """Load shared project env files in a single, consistent order.

    `frontend/.env.local` wins for shared frontend/Supabase settings, while the
    repo-root `.env` supplies backend-only secrets that are absent there.
    Existing process env vars are never overwritten.
    """
    env_paths = [
        PROJECT_ROOT / "frontend" / ".env.local",
        PROJECT_ROOT / ".env",
    ]

    loaded: list[Path] = []
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            loaded.append(env_path)

    return loaded
