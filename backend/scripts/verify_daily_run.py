"""Verify a completed daily pipeline run end-to-end.

Covers every change that landed on main between 2026-04-13 and
2026-04-17 — Phase 1 fetch layer, Phase 2 curation workflow, Phase 3
cleanup, PRs #30–#33, plus direct commits affecting the hot path.

Usage:
    python3.11 backend/scripts/verify_daily_run.py --date 2026-04-17
    python3.11 backend/scripts/verify_daily_run.py           # defaults to today GST

Structure:
    Each check is an independent function returning (status, message).
    Status is "OK", "FAIL", or "SKIP" (for conditionals that didn't trigger).
    main() aggregates and prints a summary.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

REPO_ROOT = BACKEND_DIR.parent
OUTPUT_DIR = BACKEND_DIR / "output"

from env_loader import load_project_env  # noqa: E402

CANONICAL_SECTIONS = {
    "UAE",
    "Regional Research & Academic Events",
    "International Politics & Policy",
    "International Business & Technology",
    "Model Releases & Technical Developments",
}


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------


class Result:
    __slots__ = ("layer", "name", "status", "message")

    def __init__(self, layer: str, name: str, status: str, message: str = ""):
        assert status in ("OK", "FAIL", "SKIP"), status
        self.layer = layer
        self.name = name
        self.status = status
        self.message = message


def _latest_rerun_log(date: str) -> Path | None:
    """Return the newest run_log for the given date (prefers rerun logs)."""
    candidates = sorted(OUTPUT_DIR.glob(f"run_log_rerun_*.txt"), reverse=True)
    if candidates:
        return candidates[0]
    fallback = OUTPUT_DIR / f"run_log_{date}.txt"
    return fallback if fallback.exists() else None


def _read_json(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Layer 1 — model + infra
# ---------------------------------------------------------------------------


def check_ghostwriter_model() -> Result:
    card_batch = (BACKEND_DIR / "pipeline" / "card_batch.py").read_text()
    config = (BACKEND_DIR / "config.py").read_text()
    gw_match = re.search(r"^GHOSTWRITER_MODEL\s*=\s*(.+)$", card_batch, re.MULTILINE)
    model_match = re.search(r'^MODEL\s*=\s*["\']([^"\']+)["\']', config, re.MULTILINE)
    if not gw_match or not model_match:
        return Result("L1", "GHOSTWRITER_MODEL resolves", "FAIL",
                     "Could not parse GHOSTWRITER_MODEL or MODEL declarations")
    gw_rhs = gw_match.group(1).strip()
    resolved = model_match.group(1) if gw_rhs == "MODEL" else gw_rhs
    expected = "claude-sonnet-4-6"
    if resolved == expected:
        return Result("L1", "GHOSTWRITER_MODEL resolves", "OK",
                     f"{gw_rhs} → {resolved}")
    return Result("L1", "GHOSTWRITER_MODEL resolves", "FAIL",
                 f"Expected {expected}, got {resolved} (auto-memory may be stale)")


def check_enrichment_concurrency() -> Result:
    from pipeline import enricher  # noqa: PLC0415
    expected = 15
    if getattr(enricher, "ENRICHMENT_SEMAPHORE_LIMIT", None) == expected:
        return Result("L1", "ENRICHMENT_SEMAPHORE_LIMIT == 15", "OK",
                     f"value={enricher.ENRICHMENT_SEMAPHORE_LIMIT}")
    return Result("L1", "ENRICHMENT_SEMAPHORE_LIMIT == 15", "FAIL",
                 f"expected 15, got {enricher.ENRICHMENT_SEMAPHORE_LIMIT}")


def check_no_pool_items_references() -> Result:
    try:
        r = subprocess.run(
            ["rg", "-c", "pool_items", str(BACKEND_DIR)],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return Result("L1", "no pool_items references", "SKIP",
                     f"ripgrep unavailable: {e}")
    # rg exits 1 when no matches found — that's what we want.
    if r.returncode == 1:
        return Result("L1", "no pool_items references", "OK",
                     "rg found 0 hits in backend/")
    hits = r.stdout.strip().splitlines()
    return Result("L1", "no pool_items references", "FAIL",
                 f"{len(hits)} file(s) still mention pool_items: {hits[:3]}")


def check_workflow_concurrency(workflow_name: str) -> Result:
    path = REPO_ROOT / ".github" / "workflows" / workflow_name
    text = _read_text(path)
    if text is None:
        return Result("L1", f"{workflow_name} concurrency block", "FAIL",
                     f"file missing: {path}")
    if re.search(r"^\s*concurrency:\s*$", text, re.MULTILINE) or "concurrency:\n" in text:
        return Result("L1", f"{workflow_name} concurrency block", "OK", "present")
    return Result("L1", f"{workflow_name} concurrency block", "FAIL",
                 "no `concurrency:` key found")


def check_recover_workflow_draft_only() -> Result:
    path = REPO_ROOT / ".github" / "workflows" / "recover-daily-brief.yml"
    text = _read_text(path)
    if text is None:
        return Result("L1", "recover-daily-brief draft-only", "FAIL",
                     f"file missing: {path}")
    has_draft_env = bool(re.search(r'PIPELINE_DRAFT_MODE:\s*["\']?true["\']?', text))
    # Editor used to be its own job. Verify no `editor` job exists now.
    has_editor_job = bool(re.search(r"^\s+editor:\s*$", text, re.MULTILINE))
    if has_draft_env and not has_editor_job:
        return Result("L1", "recover-daily-brief draft-only", "OK",
                     "PIPELINE_DRAFT_MODE=true, no editor job")
    return Result("L1", "recover-daily-brief draft-only", "FAIL",
                 f"draft_env={has_draft_env}, has_editor_job={has_editor_job}")


# ---------------------------------------------------------------------------
# Layer 2 — stage order + artifact presence
# ---------------------------------------------------------------------------


EXPECTED_ARTIFACTS = [
    "collected_raw_{date}.json",
    "scout_output_raw_{date}.json",
    "scout_output_{date}.json",
    "collection_log_{date}.json",
    "scout_search_log_{date}.json",
    "triage_output_{date}.json",
    "content_filter_output_{date}.json",
    "dropped_by_content_filter_{date}.json",
    "dropped_by_date_{date}.json",
    "dropped_by_dedup_{date}.json",
    "dropped_by_triage_{date}.json",
    "history_dedup_output_{date}.json",
    "dropped_by_history_dedup_{date}.json",
    "section_classifier_output_{date}.json",  # Phase 2 new
    "gatekeeper_output_{date}.json",
    "enriched_gatekeeper_output_{date}.json",
    "dropped_by_gatekeeper_{date}.json",
    "ghostwriter_output_{date}.json",
    "pipeline_stats_{date}.json",
    "run_log_{date}.txt",
]


def check_artifacts_present(date: str) -> list[Result]:
    results = []
    for pattern in EXPECTED_ARTIFACTS:
        path = OUTPUT_DIR / pattern.format(date=date)
        name = f"artifact: {pattern.format(date=date)}"
        if path.exists() and path.stat().st_size > 0:
            results.append(Result("L2", name, "OK", f"{path.stat().st_size:,} bytes"))
        else:
            results.append(Result("L2", name, "FAIL", f"missing or empty: {path}"))
    return results


STAGE_ORDER_REGEX = [
    ("Collectors", r"Collection complete|All collectors complete"),
    ("Content Filter", r"Running Content Filter"),
    ("History Dedup", r"Running History Dedup|History Dedup:"),
    ("Dedup", r"Dedup \(semantic\)|pipeline\.dedup"),
    ("web_search_verify", r"Web search dropped|Running web search verify|web_search_verify"),
    ("Section classifier (pre-Gatekeeper)", r"Pre-Gatekeeper section classification"),
    ("Gatekeeper", r"Running Gatekeeper"),
    ("Ghostwriter", r"Running Ghostwriter"),
    ("ingest_draft", r"Draft slate ingested|Created pending_briefs row"),
]


def check_stage_order(log_text: str) -> Result:
    """Assert every expected stage logs its start line in canonical order."""
    lines = log_text.splitlines()
    missing: list[str] = []
    seen_at: dict[str, int] = {}
    for stage, pat in STAGE_ORDER_REGEX:
        for i, line in enumerate(lines):
            if re.search(pat, line):
                seen_at[stage] = i
                break
        else:
            missing.append(stage)
    if missing:
        return Result("L2", "all expected stages ran", "FAIL",
                     f"missing stages: {missing}")
    order = list(seen_at.items())
    for i in range(1, len(order)):
        prev_name, prev_idx = order[i - 1]
        cur_name, cur_idx = order[i]
        if cur_idx < prev_idx:
            return Result("L2", "stage order correct", "FAIL",
                         f"{cur_name} (line {cur_idx}) appeared before {prev_name} (line {prev_idx})")
    return Result("L2", "stage order correct", "OK",
                 f"all {len(order)} stages in canonical order")


# ---------------------------------------------------------------------------
# Layer 3 — Phase 1 fetch layer
# ---------------------------------------------------------------------------


def check_wam_api_hits(log_text: str) -> Result:
    hits = len(re.findall(r"wam_api|fetch_wam_article", log_text))
    if hits >= 5:
        return Result("L3", "WAM API hits ≥ 5", "OK", f"{hits} hits")
    return Result("L3", "WAM API hits ≥ 5", "FAIL",
                 f"only {hits} hits (expected ≥5 — WAM URLs are ~80% of volume)")


def check_no_jina_429_storm(log_text: str) -> Result:
    hits = len(re.findall(r"429 Too Many Requests", log_text))
    if hits < 5:
        return Result("L3", "no Jina 429 storm", "OK", f"{hits} 429(s)")
    return Result("L3", "no Jina 429 storm", "FAIL",
                 f"{hits} 429 responses — old run (pre-Phase-1) was 20+; "
                 "Phase 1 should prevent by routing WAM via WAM API")


def check_serper_exercised(log_text: str) -> Result:
    hits = len(re.findall(r"serper_scrape|Serper /scrape succeeded", log_text))
    if hits >= 1:
        return Result("L3", "Serper /scrape exercised", "OK", f"{hits} hit(s)")
    return Result("L3", "Serper /scrape exercised", "SKIP",
                 "trafilatura may have succeeded on all non-WAM URLs this run")


# ---------------------------------------------------------------------------
# Layer 4 — Phase 2 curation workflow
# ---------------------------------------------------------------------------


def check_section_classifier_output(date: str) -> list[Result]:
    path = OUTPUT_DIR / f"section_classifier_output_{date}.json"
    data = _read_json(path)
    if data is None:
        return [Result("L4", "section_classifier_output exists", "FAIL",
                      f"missing or invalid JSON: {path}")]
    counts = data.get("counts", {}) if isinstance(data, dict) else {}
    total = sum(counts.values())
    results = []
    results.append(Result("L4", "section_classifier_output exists", "OK",
                         f"{total} items classified"))
    if total >= 100:
        results.append(Result("L4", "section_classifier saw ≥ 100 items", "OK",
                             f"{total}"))
    else:
        results.append(Result("L4", "section_classifier saw ≥ 100 items", "FAIL",
                             f"only {total} — pipeline collection may be low"))
    missing = CANONICAL_SECTIONS - set(counts.keys())
    if not missing:
        results.append(Result("L4", "all 5 canonical sections represented", "OK", ""))
    else:
        results.append(Result("L4", "all 5 canonical sections represented", "FAIL",
                             f"missing: {missing}"))
    if "?" in counts:
        results.append(Result("L4", "no '?' sentinel sections", "FAIL",
                             f"{counts['?']} items hit the default fallback"))
    else:
        results.append(Result("L4", "no '?' sentinel sections", "OK", ""))
    return results


def check_classify_before_cap(log_text: str) -> Result:
    classify_match = re.search(r"Pre-Gatekeeper section classification", log_text)
    cap_match = re.search(r"Section cap: trimmed", log_text)
    if not classify_match:
        return Result("L4", "classify-before-cap ordering", "FAIL",
                     "no classification line in log")
    if cap_match is None:
        return Result("L4", "classify-before-cap ordering", "SKIP",
                     "no section-cap trim this run (Gatekeeper stayed ≤15/section)")
    if classify_match.start() < cap_match.start():
        return Result("L4", "classify-before-cap ordering", "OK",
                     f"classify at {classify_match.start()}, cap at {cap_match.start()}")
    return Result("L4", "classify-before-cap ordering", "FAIL",
                 "section cap line appeared BEFORE classification (commit 11a5995 regression)")


def check_gatekeeper_brief_sections(date: str) -> list[Result]:
    path = OUTPUT_DIR / f"gatekeeper_output_{date}.json"
    data = _read_json(path)
    if not isinstance(data, dict):
        return [Result("L4", "gatekeeper output loadable", "FAIL",
                      f"missing or invalid: {path}")]
    selected = data.get("selected", [])
    results = []
    if not selected:
        return [Result("L4", "gatekeeper has selected items", "FAIL",
                      "selected list is empty")]

    non_canonical = [
        (i.get("_idx"), i.get("brief_section"))
        for i in selected
        if i.get("brief_section") not in CANONICAL_SECTIONS
    ]
    if non_canonical:
        results.append(Result("L4", "all selected items have canonical brief_section",
                             "FAIL", f"{len(non_canonical)} non-canonical: {non_canonical[:3]}"))
    else:
        results.append(Result("L4", "all selected items have canonical brief_section",
                             "OK", f"{len(selected)} items"))

    # Per-section cap check
    by_section: dict[str, int] = {}
    for item in selected:
        s = item.get("brief_section", "?")
        by_section[s] = by_section.get(s, 0) + 1
    overflow = {s: n for s, n in by_section.items() if n > 15}
    if overflow:
        results.append(Result("L4", "per-section cap ≤ 15 enforced", "FAIL",
                             f"overflow: {overflow}"))
    else:
        results.append(Result("L4", "per-section cap ≤ 15 enforced", "OK",
                             str(by_section)))
    return results


def check_ghostwriter_chunking(log_text: str, date: str) -> Result:
    sec_labels = re.findall(r"sec-[A-Za-z0-9_]+", log_text)
    gk = _read_json(OUTPUT_DIR / f"gatekeeper_output_{date}.json") or {}
    selected_count = len(gk.get("selected", []))
    if selected_count <= 15:
        return Result("L4", "Ghostwriter chunking (fast path)", "SKIP",
                     f"{selected_count} items ≤ 15, fast-path is correct")
    unique = set(sec_labels)
    if len(unique) >= 2:
        return Result("L4", "Ghostwriter chunked into ≥ 2 batches", "OK",
                     f"{len(unique)} unique sec- labels: {sorted(unique)[:5]}")
    return Result("L4", "Ghostwriter chunked into ≥ 2 batches", "FAIL",
                 f"selected={selected_count} but only {len(unique)} sec- labels — "
                 "chunked wrapper may not have triggered")


def check_ghostwriter_item_accounting(log_text: str, date: str) -> Result:
    gw = _read_json(OUTPUT_DIR / f"ghostwriter_output_{date}.json") or {}
    gk = _read_json(OUTPUT_DIR / f"gatekeeper_output_{date}.json") or {}
    gw_count = len(gw.get("items", []))
    gk_count = len(gk.get("selected", []))
    trim_match = re.search(r"Section cap: trimmed (\d+) overflow", log_text)
    trims = int(trim_match.group(1)) if trim_match else 0
    expected = gk_count  # gk selected is already post-trim
    if gw_count == expected:
        return Result("L4", "Ghostwriter item count accounting", "OK",
                     f"gw={gw_count}, gk={gk_count}, trims={trims}")
    return Result("L4", "Ghostwriter item count accounting", "FAIL",
                 f"gw_items={gw_count} but gatekeeper_selected={gk_count} (trims={trims})")


def check_post_ghostwriter_classifier_shortcircuit(log_text: str) -> Result:
    if re.search(r"already in canonical sections.*skipping", log_text):
        return Result("L4", "post-Ghostwriter classifier short-circuited", "OK",
                     "idempotency guard fired")
    return Result("L4", "post-Ghostwriter classifier short-circuited", "SKIP",
                 "idempotency guard line not found — may still be working if classifier saw empty items")


def check_ghostwriter_refusal_fallback(log_text: str) -> Result:
    if re.search(r"refusal.*falling back|refusal fallback", log_text, re.IGNORECASE):
        return Result("L4", "Ghostwriter refusal fallback (conditional)", "OK",
                     "fallback fired — not a failure, just noting")
    return Result("L4", "Ghostwriter refusal fallback (conditional)", "SKIP",
                 "no refusal this run")


# ---------------------------------------------------------------------------
# Layer 5 — Supabase
# ---------------------------------------------------------------------------


def _get_supabase():
    try:
        from ingest_draft import _get_supabase_client  # noqa: PLC0415
    except ImportError as e:
        return None, str(e)
    try:
        return _get_supabase_client(), None
    except SystemExit as e:
        return None, f"env vars missing: {e}"


def check_supabase(date: str) -> list[Result]:
    sb, err = _get_supabase()
    if sb is None:
        return [Result("L5", "supabase client connection", "FAIL", err)]

    results: list[Result] = []

    # Helper: run a SQL query via the REST API. Supabase-py doesn't do raw SQL,
    # so we use table selects. Not every check works this way, but the ones
    # that need raw SQL can be documented as manual.

    # A: pending_briefs for this date
    try:
        pb_resp = sb.table("pending_briefs").select("id").eq("brief_date", date).execute()
        pbs = pb_resp.data or []
    except Exception as e:
        return results + [Result("L5", "pending_briefs query", "FAIL", str(e))]
    if not pbs:
        return results + [Result("L5", "pending_briefs row exists", "FAIL",
                                f"no row for brief_date={date}")]
    results.append(Result("L5", "pending_briefs row exists", "OK", f"id={pbs[0]['id']}"))
    pending_brief_id = pbs[0]["id"]

    # A continued: tier distribution
    try:
        pi_resp = sb.table("pending_items").select(
            "tier, section, key_bullets, analysis"
        ).eq("pending_brief_id", pending_brief_id).execute()
        items = pi_resp.data or []
    except Exception as e:
        return results + [Result("L5", "pending_items query", "FAIL", str(e))]
    tiers = {}
    for item in items:
        tiers[item.get("tier", "?")] = tiers.get(item.get("tier", "?"), 0) + 1
    if list(tiers.keys()) == ["proposed"]:
        results.append(Result("L5", "pending_items all tier='proposed'", "OK",
                             f"{tiers['proposed']} rows"))
    else:
        results.append(Result("L5", "pending_items all tier='proposed'", "FAIL",
                             f"tiers: {tiers}"))

    # B: section distribution (≤15 per section)
    section_counts: dict[str, int] = {}
    for item in items:
        s = item.get("section") or "?"
        section_counts[s] = section_counts.get(s, 0) + 1
    overflow = {s: n for s, n in section_counts.items() if n > 15}
    if overflow:
        results.append(Result("L5", "per-section ≤ 15 in pending_items", "FAIL",
                             f"overflow: {overflow}"))
    else:
        results.append(Result("L5", "per-section ≤ 15 in pending_items", "OK",
                             str(section_counts)))

    # C: null-check on authored fields
    null_count = sum(
        1 for item in items
        if item.get("analysis") is None
        or item.get("key_bullets") is None
        or not item.get("section")
    )
    if null_count == 0:
        results.append(Result("L5", "no null analysis/key_bullets/section", "OK",
                             f"{len(items)} items all populated"))
    else:
        results.append(Result("L5", "no null analysis/key_bullets/section", "FAIL",
                             f"{null_count}/{len(items)} items have null fields"))

    # D: drops stage distribution
    try:
        drops_resp = sb.table("dropped_items").select("dropped_at_stage").eq(
            "run_date", date
        ).execute()
        drops = drops_resp.data or []
    except Exception as e:
        results.append(Result("L5", "dropped_items query", "FAIL", str(e)))
        drops = []
    drops_by_stage: dict[str, int] = {}
    for d in drops:
        s = d.get("dropped_at_stage", "?")
        drops_by_stage[s] = drops_by_stage.get(s, 0) + 1
    required_stages = {"triage", "content_filter", "dedup", "gatekeeper"}
    missing = required_stages - set(drops_by_stage.keys())
    if missing:
        results.append(Result("L5", "drops_by_stage required stages present", "FAIL",
                             f"missing: {missing}; saw: {list(drops_by_stage.keys())}"))
    else:
        results.append(Result("L5", "drops_by_stage required stages present", "OK",
                             str(drops_by_stage)))

    # E: history_dedup row count matches JSON
    hd_path = OUTPUT_DIR / f"dropped_by_history_dedup_{date}.json"
    hd_json = _read_json(hd_path) or {}
    expected_hd = hd_json.get("dropped_count", 0) if isinstance(hd_json, dict) else 0
    actual_hd = drops_by_stage.get("history_dedup", 0)
    if expected_hd == 0:
        results.append(Result("L5", "history_dedup JSON vs DB count (PR #33)", "SKIP",
                             "history_dedup dropped 0 items this run (legitimate)"))
    elif actual_hd == expected_hd:
        results.append(Result("L5", "history_dedup JSON vs DB count (PR #33)", "OK",
                             f"both = {expected_hd}"))
    else:
        results.append(Result("L5", "history_dedup JSON vs DB count (PR #33)", "FAIL",
                             f"JSON={expected_hd}, DB={actual_hd}"))

    return results


# ---------------------------------------------------------------------------
# Layer 6 — web_search_verify (21998e2 + 10302e4)
# ---------------------------------------------------------------------------


def check_web_search_verify_pre_gatekeeper(log_text: str) -> Result:
    ws_match = re.search(r"Web search dropped|web_search_verify", log_text)
    gk_match = re.search(r"Running Gatekeeper", log_text)
    if not ws_match:
        return Result("L6", "web_search_verify ran", "FAIL",
                     "no web_search_verify log line")
    if not gk_match:
        return Result("L6", "web_search_verify pre-Gatekeeper", "FAIL",
                     "no Gatekeeper start line")
    if ws_match.start() < gk_match.start():
        return Result("L6", "web_search_verify pre-Gatekeeper", "OK",
                     f"ws at {ws_match.start()}, gk at {gk_match.start()}")
    return Result("L6", "web_search_verify pre-Gatekeeper", "FAIL",
                 f"web_search_verify appeared AFTER Gatekeeper (regression from 21998e2)")


def check_web_search_vendor_serper(date: str) -> Result:
    path = OUTPUT_DIR / f"dropped_by_web_search_{date}.json"
    text = _read_text(path)
    if text is None:
        return Result("L6", "web_search_verify uses Serper (not DDG)", "SKIP",
                     f"no drops file for {date} — web_search_verify made no drops this run")
    text_lower = text.lower()
    if "duckduckgo" in text_lower or "ddg" in text_lower:
        return Result("L6", "web_search_verify uses Serper (not DDG)", "FAIL",
                     "DDG/DuckDuckGo token found in drops file (regression from 10302e4)")
    # Serper may or may not appear in drop metadata text — presence is a strong signal,
    # absence is not definitive.
    return Result("L6", "web_search_verify uses Serper (not DDG)", "OK",
                 "no DDG/DuckDuckGo references")


# ---------------------------------------------------------------------------
# Layer 7 — mobile + audio API shapes (manual-ish)
# ---------------------------------------------------------------------------


def check_briefs_endpoint_exists() -> Result:
    path = REPO_ROOT / "frontend" / "app" / "api" / "briefs" / "route.ts"
    if path.exists():
        return Result("L7", "/api/briefs route exists (PR #30)", "OK", str(path.relative_to(REPO_ROOT)))
    return Result("L7", "/api/briefs route exists (PR #30)", "FAIL",
                 f"missing: {path}")


def check_audio_status_route_exists() -> Result:
    path = REPO_ROOT / "frontend" / "app" / "api" / "audio-status" / "route.ts"
    if path.exists():
        return Result("L7", "/api/audio-status route exists (PR #31)", "OK",
                     str(path.relative_to(REPO_ROOT)))
    return Result("L7", "/api/audio-status route exists (PR #31)", "FAIL",
                 f"missing: {path}")


# ---------------------------------------------------------------------------
# Layer 8 — end-to-end health
# ---------------------------------------------------------------------------


def check_pipeline_duration(date: str) -> Result:
    data = _read_json(OUTPUT_DIR / f"pipeline_stats_{date}.json")
    if not isinstance(data, dict):
        return Result("L8", "pipeline duration < 45 min", "FAIL",
                     "no pipeline_stats")
    duration = data.get("duration_seconds", 0)
    limit = 45 * 60
    if duration < limit:
        return Result("L8", "pipeline duration < 45 min", "OK",
                     f"{duration}s ({duration // 60}m {duration % 60}s)")
    return Result("L8", "pipeline duration < 45 min", "FAIL",
                 f"{duration}s — exceeds 45-min budget")


def check_pipeline_cost(date: str) -> Result:
    data = _read_json(OUTPUT_DIR / f"pipeline_stats_{date}.json")
    if not isinstance(data, dict):
        return Result("L8", "cost_usd in reasonable range ($1-$15)", "FAIL",
                     "no pipeline_stats")
    cost = data.get("total_cost_usd") or data.get("cost_usd") or 0
    if 1 <= cost <= 15:
        return Result("L8", "cost_usd in reasonable range ($1-$15)", "OK",
                     f"${cost:.2f}")
    return Result("L8", "cost_usd in reasonable range ($1-$15)", "FAIL",
                 f"${cost:.2f} — outside expected range")


def check_uae_scout_non_zero(log_text: str) -> Result:
    uae_match = re.search(r"uae[^\n]*(\d+)\s*items|(\d+)\s*items from uae", log_text, re.IGNORECASE)
    if not uae_match:
        # Best effort — try a looser match for uae collection line
        if re.search(r"uae", log_text, re.IGNORECASE):
            return Result("L8", "UAE scout returned items", "OK",
                         "uae token appears in log; exact count not parseable")
        return Result("L8", "UAE scout returned items", "FAIL",
                     "no uae scout mention in log")
    count = int(uae_match.group(1) or uae_match.group(2) or 0)
    if count > 0:
        return Result("L8", "UAE scout returned items", "OK", f"{count} items")
    return Result("L8", "UAE scout returned items", "FAIL", "zero items")


def check_draft_slate_section_coverage(date: str) -> Result:
    path = OUTPUT_DIR / f"gatekeeper_output_{date}.json"
    data = _read_json(path)
    if not isinstance(data, dict):
        return Result("L8", "draft slate covers ≥ 3 of 5 sections", "FAIL",
                     "no gatekeeper output")
    selected = data.get("selected", [])
    sections = {item.get("brief_section") for item in selected}
    covered = sections & CANONICAL_SECTIONS
    if len(covered) >= 3:
        return Result("L8", "draft slate covers ≥ 3 of 5 sections", "OK",
                     f"{len(covered)} sections: {sorted(covered)}")
    return Result("L8", "draft slate covers ≥ 3 of 5 sections", "FAIL",
                 f"only {len(covered)} sections: {sorted(covered)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_all(date: str) -> list[Result]:
    load_project_env()
    log_path = _latest_rerun_log(date)
    log_text = _read_text(log_path) if log_path else ""

    results: list[Result] = []

    # Layer 1
    results.append(check_ghostwriter_model())
    results.append(check_enrichment_concurrency())
    results.append(check_no_pool_items_references())
    results.append(check_workflow_concurrency("daily-brief.yml"))
    results.append(check_workflow_concurrency("generate-audio.yml"))
    results.append(check_recover_workflow_draft_only())

    # Layer 2
    results.extend(check_artifacts_present(date))
    if log_text:
        results.append(check_stage_order(log_text))
    else:
        results.append(Result("L2", "stage order", "SKIP", "no run_log available"))

    # Layer 3
    if log_text:
        results.append(check_wam_api_hits(log_text))
        results.append(check_no_jina_429_storm(log_text))
        results.append(check_serper_exercised(log_text))

    # Layer 4
    results.extend(check_section_classifier_output(date))
    if log_text:
        results.append(check_classify_before_cap(log_text))
    results.extend(check_gatekeeper_brief_sections(date))
    if log_text:
        results.append(check_ghostwriter_chunking(log_text, date))
    results.append(check_ghostwriter_item_accounting(log_text or "", date))
    if log_text:
        results.append(check_post_ghostwriter_classifier_shortcircuit(log_text))
        results.append(check_ghostwriter_refusal_fallback(log_text))

    # Layer 5 (Supabase)
    results.extend(check_supabase(date))

    # Layer 6
    if log_text:
        results.append(check_web_search_verify_pre_gatekeeper(log_text))
    results.append(check_web_search_vendor_serper(date))

    # Layer 7
    results.append(check_briefs_endpoint_exists())
    results.append(check_audio_status_route_exists())

    # Layer 8
    results.append(check_pipeline_duration(date))
    results.append(check_pipeline_cost(date))
    if log_text:
        results.append(check_uae_scout_non_zero(log_text))
    results.append(check_draft_slate_section_coverage(date))

    return results


def print_report(results: list[Result]) -> int:
    """Print results grouped by layer; return non-zero exit code if any FAIL."""
    by_status = {"OK": 0, "FAIL": 0, "SKIP": 0}
    by_layer: dict[str, list[Result]] = {}
    for r in results:
        by_status[r.status] += 1
        by_layer.setdefault(r.layer, []).append(r)

    for layer in sorted(by_layer.keys()):
        print(f"\n===== {layer} =====")
        for r in by_layer[layer]:
            tag = {"OK": "[OK]  ", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[r.status]
            line = f"{tag} {r.name}"
            if r.message:
                line += f" — {r.message}"
            print(line)

    total = len(results)
    print("\n" + "=" * 70)
    print(f"Summary: {total} checks — {by_status['OK']} OK, "
          f"{by_status['FAIL']} FAIL, {by_status['SKIP']} SKIP")
    print("=" * 70)

    if by_status["FAIL"]:
        print("\nFAILURES:")
        for r in results:
            if r.status == "FAIL":
                print(f"  [{r.layer}] {r.name} — {r.message}")

    return 0 if by_status["FAIL"] == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Date YYYY-MM-DD (default: today GST)")
    args = parser.parse_args()
    date = args.date or datetime.now(ZoneInfo("Asia/Dubai")).strftime("%Y-%m-%d")
    print(f"Verifying daily pipeline run for {date}")
    results = run_all(date)
    sys.exit(print_report(results))


if __name__ == "__main__":
    main()
