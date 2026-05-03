#!/usr/bin/env python3.11
"""Pull production briefs from Supabase and write Ghostwriter eval fixtures.

One-shot bootstrap script for the prompt-refactor eval harness. For each
requested date this reads ``briefs.raw_json`` from Supabase and writes a
fixture JSON to
``backend/tests/fixtures/prompt_refactor/ghostwriter/{date}.json``
in the shape the Ghostwriter expects as input.

Fixture shape (documented more fully in the README next to the files):

::

    {
      "date": "2026-04-NN",
      "gatekeeper_input": {
        "selected": [ { ...one-per-item... } ],
        "allowed_ids": [ "..." ]
      },
      "old_output": {
        "items": [ ...production output for diff/judge comparison... ]
      }
    }

Known caveat: the original scout ``raw_text`` is not persisted in the
``briefs`` table, so the fixture's ``raw_content`` is the production
Ghostwriter's ``analysis`` paragraph used as a synthetic stand-in. For a
voice refactor the evaluation is "given the same synthetic raw_content,
which prompt produces the better card?" — the limitation is deliberate
and documented.

Usage
-----

::

    cd backend && python -m evals.fetch_ghostwriter_fixtures \\
        --dates 2026-04-06,2026-04-07,2026-04-08,2026-04-09,2026-04-13

Requires ``NEXT_PUBLIC_SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY``
in the environment (set via the project-root ``.env`` or
``frontend/.env.local``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
FIXTURE_DIR = BACKEND_DIR / "tests" / "fixtures" / "prompt_refactor" / "ghostwriter"


def _env_candidates() -> list[Path]:
    """Return candidate .env / .env.local paths in load order.

    When running from a git worktree under ``.claude/worktrees/``, the
    repo's ``.env`` lives in the main checkout, not in the worktree.
    Walk up to find it.
    """
    candidates: list[Path] = []
    candidates.append(PROJECT_ROOT / ".env")
    candidates.append(PROJECT_ROOT / "frontend" / ".env.local")
    # If we're inside .claude/worktrees/<name>/, the main checkout is at
    # the parent directory three levels up.
    parts = PROJECT_ROOT.parts
    if ".claude" in parts and "worktrees" in parts:
        i = parts.index(".claude")
        main_repo = Path(*parts[:i])
        candidates.append(main_repo / ".env")
        candidates.append(main_repo / "frontend" / ".env.local")
    return candidates


def _load_env() -> None:
    """Load env vars from every candidate .env that exists.

    ``override=True`` so an empty ANTHROPIC_API_KEY="" in the shell
    doesn't prevent the real key in the .env file from loading.
    """
    for path in _env_candidates():
        if path.exists():
            load_dotenv(path, override=True)


def _supabase():
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print(
            "ERROR: NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "must be set. Check .env files.",
            file=sys.stderr,
        )
        sys.exit(1)
    return create_client(url, key)


def _build_gatekeeper_input(brief_items: list[dict], date: str) -> dict:
    """Rebuild a Ghostwriter-compatible gatekeeper_output from a brief's items.

    The original gatekeeper payload is not persisted post-pipeline, so we
    reconstruct it from ``briefs.raw_json.items`` — which is the final,
    Editor-approved output. For voice-refactor evals this is sufficient
    because the inputs are identical for v1 and v2; what we measure is
    prose quality, not selection fidelity.
    """
    selected: list[dict] = []
    for item in brief_items:
        key_bullets = item.get("key_bullets") or []
        analysis = item.get("analysis") or item.get("context") or ""
        synthetic_raw_parts: list[str] = []
        if item.get("main_bullet"):
            synthetic_raw_parts.append(item["main_bullet"])
        if analysis:
            synthetic_raw_parts.append(analysis)
        if key_bullets:
            synthetic_raw_parts.append(
                "Key facts:\n" + "\n".join(f"- {b}" for b in key_bullets)
            )
        synthetic_raw = "\n\n".join(p for p in synthetic_raw_parts if p)

        selected.append(
            {
                "id": item.get("id") or f"{date}-x{len(selected):03d}",
                "headline": item.get("headline", ""),
                "source": item.get("source_name", "unknown"),
                "source_name": item.get("source_name", "unknown"),
                "source_url": item.get("source_url") or "",
                "source_domain": item.get("source_domain", "newsletter"),
                "date": date,
                "summary": item.get("main_bullet", ""),
                "raw_content": synthetic_raw,
                "additional_context": "",
                "additional_sources": item.get("additional_sources") or [],
                "entities": item.get("entities") or [],
                "category": item.get("category", ""),
                "cluster": item.get("cluster"),
                "composite_score": float(item.get("composite_score") or 0),
                "selection_rationale": f"Reconstructed from production brief {date} for eval-fixture.",
                "brief_section": item.get("section") or "",
                "is_model_release": bool(item.get("is_model_release")),
                "model_release_data": item.get("model_release_data"),
                "primary_entity": item.get("primary_entity"),
                "depth": item.get("depth") or _depth_from_score(item.get("composite_score") or 0),
            }
        )
    return {
        "selected": selected,
        "allowed_ids": [s["id"] for s in selected],
    }


def _depth_from_score(score: float) -> str:
    score = float(score or 0)
    if score >= 8.0:
        return "full"
    if score >= 7.0:
        return "standard"
    return "brief"


def fetch_fixture(sb, date: str) -> dict | None:
    """Fetch one brief from Supabase and build a fixture dict."""
    res = sb.table("briefs").select("raw_json").eq("brief_date", date).execute()
    rows = res.data or []
    if not rows:
        print(f"  ! no brief for {date}; skipping")
        return None
    raw = rows[0]["raw_json"] or {}
    items = raw.get("items") or []
    if not items:
        print(f"  ! brief for {date} has no items; skipping")
        return None
    return {
        "date": date,
        "gatekeeper_input": _build_gatekeeper_input(items, date),
        "old_output": {"items": items},
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--dates",
        required=True,
        help="Comma-separated YYYY-MM-DD dates to fetch.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=FIXTURE_DIR,
        help=f"Output directory (default: {FIXTURE_DIR}).",
    )
    return p.parse_args()


def main() -> None:
    _load_env()
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    sb = _supabase()
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    print(f"Fetching {len(dates)} date(s) into {args.out}")

    written = 0
    for date in dates:
        print(f"- {date}")
        fixture = fetch_fixture(sb, date)
        if not fixture:
            continue
        out_path = args.out / f"{date}.json"
        out_path.write_text(
            json.dumps(fixture, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        n_items = len(fixture["gatekeeper_input"]["selected"])
        print(f"  wrote {out_path.name} ({n_items} items)")
        written += 1

    print(f"\nWrote {written}/{len(dates)} fixtures to {args.out}")


if __name__ == "__main__":
    main()
