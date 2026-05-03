"""End-to-end regression tests for the intelligence briefing pipeline.

Loads real pipeline artifacts from the output directory and validates
structural invariants that must hold for every successful pipeline run.

Run with:
    cd backend && python -m pytest tests/test_pipeline_e2e.py -v
    cd backend && python -m unittest tests.test_pipeline_e2e -v
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BACKEND_DIR / "output"

# Fall back to the main repo output if we're in a worktree with an empty output/
# In a git worktree, .git is a file pointing to the main repo's .git/worktrees/
_dotgit = BACKEND_DIR.parent / ".git"
if _dotgit.is_file():
    # We're in a worktree — resolve main repo root via the .git file
    _gitdir = _dotgit.read_text().strip().replace("gitdir: ", "")
    # _gitdir looks like <main_repo>/.git/worktrees/<name>
    MAIN_OUTPUT_DIR = Path(_gitdir).parent.parent.parent / "backend" / "output"
else:
    MAIN_OUTPUT_DIR = BACKEND_DIR.parent / "backend" / "output"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# The 5 canonical brief sections
CANONICAL_SECTIONS = [
    "UAE",
    "Regional Research & Academic Events",
    "International Politics & Policy",
    "International Business & Technology",
    "Model Releases & Technical Developments",
]

# Artifact filename templates (prefix -> expected file pattern)
ARTIFACT_PREFIXES = [
    "collected_raw",
    "content_filter_output",
    "gatekeeper_output",
    "ghostwriter_output",
    "editor_output",
    "brief",
]


def _get_output_dir() -> Path:
    """Return the output directory that actually contains brief files."""
    if OUTPUT_DIR.exists() and list(OUTPUT_DIR.glob("brief_*.json")):
        return OUTPUT_DIR
    if MAIN_OUTPUT_DIR.exists() and list(MAIN_OUTPUT_DIR.glob("brief_*.json")):
        return MAIN_OUTPUT_DIR
    return OUTPUT_DIR  # will produce clear test failures


def _find_most_recent_date(output_dir: Path) -> str | None:
    """Find the most recent date that has a brief_*.json file."""
    briefs = sorted(output_dir.glob("brief_*.json"))
    if not briefs:
        return None
    # Extract date from filename like brief_2026-03-10.json
    match = re.search(r"brief_(\d{4}-\d{2}-\d{2})\.json$", briefs[-1].name)
    return match.group(1) if match else None


def _find_most_complete_date(output_dir: Path) -> str | None:
    """Find the most recent date that has the most pipeline artifacts.

    Prefers dates with all 6 artifact types, falling back to dates with the
    most available artifacts.
    """
    date_artifact_counts: dict[str, int] = {}
    for prefix in ARTIFACT_PREFIXES:
        for f in output_dir.glob(f"{prefix}_*.json"):
            match = re.search(r"(\d{4}-\d{2}-\d{2})\.json$", f.name)
            if match:
                d = match.group(1)
                date_artifact_counts[d] = date_artifact_counts.get(d, 0) + 1

    if not date_artifact_counts:
        return None

    # Sort by (artifact_count desc, date desc) to get most complete + most recent
    best = sorted(
        date_artifact_counts.items(),
        key=lambda x: (x[1], x[0]),
        reverse=True,
    )
    return best[0][0]


def _load_json(path: Path) -> dict | list | None:
    """Load a JSON file, returning None if it doesn't exist."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class PipelineE2ETests(unittest.TestCase):
    """End-to-end validation of pipeline artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.output_dir = _get_output_dir()
        cls.recent_date = _find_most_recent_date(cls.output_dir)
        cls.complete_date = _find_most_complete_date(cls.output_dir)

    # ------------------------------------------------------------------
    # test_brief_structure_validation
    # ------------------------------------------------------------------

    def test_brief_structure_validation(self):
        """Validate that a recent brief has correct structure and content."""
        self.assertIsNotNone(
            self.recent_date,
            f"No brief_*.json files found in {self.output_dir}",
        )

        brief_path = self.output_dir / f"brief_{self.recent_date}.json"
        brief = _load_json(brief_path)
        self.assertIsNotNone(brief, f"Could not load {brief_path}")
        self.assertIsInstance(brief, dict)

        # --- brief_metadata ---
        meta = brief.get("brief_metadata")
        self.assertIsNotNone(meta, "brief_metadata missing")
        for key in ("date", "total_items", "section_counts"):
            self.assertIn(key, meta, f"brief_metadata missing '{key}'")

        # --- items array ---
        items = brief.get("items")
        self.assertIsNotNone(items, "items array missing")
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(
            len(items), 8, f"Expected >= 8 items, got {len(items)}"
        )
        self.assertLessEqual(
            len(items), 20, f"Expected <= 20 items, got {len(items)}"
        )

        # --- per-item required fields ---
        required_fields = {"id", "headline", "section", "main_bullet"}
        for i, item in enumerate(items):
            for field in required_fields:
                self.assertIn(
                    field, item, f"Item {i} missing required field '{field}'"
                )

            # main_bullet word count
            bullet = item.get("main_bullet", "")
            word_count = len(bullet.split())
            self.assertGreaterEqual(
                word_count,
                10,
                f"Item {i} main_bullet has only {word_count} words: "
                f"{bullet[:80]}...",
            )

        # --- section coverage ---
        present_sections = {item["section"] for item in items}
        covered = present_sections & set(CANONICAL_SECTIONS)
        self.assertGreaterEqual(
            len(covered),
            4,
            f"Expected >= 4 of 5 canonical sections, got {len(covered)}: "
            f"{covered}. Missing: {set(CANONICAL_SECTIONS) - covered}",
        )

        # --- no duplicate IDs ---
        ids = [item["id"] for item in items]
        duplicates = [x for x in ids if ids.count(x) > 1]
        self.assertEqual(
            len(set(duplicates)),
            0,
            f"Duplicate item IDs found: {set(duplicates)}",
        )

    # ------------------------------------------------------------------
    # test_pipeline_artifact_completeness
    # ------------------------------------------------------------------

    def test_pipeline_artifact_completeness(self):
        """Check that all expected pipeline artifacts exist for a recent date."""
        date = self.complete_date or self.recent_date
        self.assertIsNotNone(
            date,
            f"No pipeline artifacts found in {self.output_dir}",
        )

        expected_files = [
            f"collected_raw_{date}.json",
            f"content_filter_output_{date}.json",
            f"gatekeeper_output_{date}.json",
            f"ghostwriter_output_{date}.json",
            f"editor_output_{date}.json",
            f"brief_{date}.json",
        ]

        missing = []
        for fname in expected_files:
            if not (self.output_dir / fname).exists():
                missing.append(fname)

        if missing:
            # If no single date has all artifacts, this is informational —
            # not every run retains collected_raw. Fail only if core outputs
            # (gatekeeper through brief) are missing.
            core_missing = [
                f
                for f in missing
                if not f.startswith("collected_raw")
                and not f.startswith("content_filter")
            ]
            if core_missing:
                self.fail(
                    f"Core pipeline artifacts missing for {date}: {core_missing}"
                )
            else:
                # Warn but don't fail for optional early-stage artifacts
                print(
                    f"  [INFO] Optional artifacts missing for {date}: {missing}"
                )

    # ------------------------------------------------------------------
    # test_funnel_monotonically_decreasing
    # ------------------------------------------------------------------

    def test_funnel_monotonically_decreasing(self):
        """Verify the pipeline funnel narrows at each stage.

        Uses artifact file sizes / item counts to check that
        collected >= content_filter input >= gatekeeper input >= selected.
        """
        date = self.complete_date or self.recent_date
        self.assertIsNotNone(date, "No pipeline date available")

        counts: dict[str, int | None] = {}

        # collected_raw: list of raw items
        collected = _load_json(self.output_dir / f"collected_raw_{date}.json")
        if isinstance(collected, list):
            counts["collected"] = len(collected)

        # content_filter_output: has news_count (input) and filtered_count (kept)
        cf = _load_json(self.output_dir / f"content_filter_output_{date}.json")
        if isinstance(cf, dict):
            counts["content_filter_input"] = cf.get("news_count")
            counts["content_filter_kept"] = cf.get("filtered_count")

        # gatekeeper_output: selected + dropped
        gk = _load_json(self.output_dir / f"gatekeeper_output_{date}.json")
        if isinstance(gk, dict):
            selected = gk.get("selected", [])
            dropped = gk.get("dropped", [])
            counts["gatekeeper_input"] = len(selected) + len(dropped)
            counts["gatekeeper_selected"] = len(selected)

        # brief: final item count
        brief = _load_json(self.output_dir / f"brief_{date}.json")
        if isinstance(brief, dict) and "items" in brief:
            counts["brief_items"] = len(brief["items"])

        # Build ordered funnel pairs that must be non-increasing.
        # Notes on the pipeline topology:
        # - Newsletter splitting can increase item count beyond collected_raw
        # - Content filter only processes a subset of items
        # So we only assert on stages with a true subset relationship.
        funnel_pairs = [
            ("content_filter_input", "content_filter_kept"),
            ("gatekeeper_input", "gatekeeper_selected"),
            ("gatekeeper_selected", "brief_items"),
        ]

        checked = 0
        for stage_a, stage_b in funnel_pairs:
            a = counts.get(stage_a)
            b = counts.get(stage_b)
            if a is not None and b is not None:
                self.assertGreaterEqual(
                    a,
                    b,
                    f"Funnel violation: {stage_a}={a} < {stage_b}={b} "
                    f"(date={date})",
                )
                checked += 1

        self.assertGreaterEqual(
            checked,
            1,
            f"Could not validate any funnel pairs — insufficient artifacts "
            f"for {date}. Available: {counts}",
        )

    # ------------------------------------------------------------------
    # test_brief_items_have_valid_sources
    # ------------------------------------------------------------------

    def test_brief_items_have_valid_sources(self):
        """Check that brief items have valid source URLs and names."""
        self.assertIsNotNone(self.recent_date, "No brief date available")

        brief_path = self.output_dir / f"brief_{self.recent_date}.json"
        brief = _load_json(brief_path)
        self.assertIsNotNone(brief)

        items = brief.get("items", [])
        self.assertTrue(len(items) > 0, "No items in brief")

        bad_sources = []
        for i, item in enumerate(items):
            source_url = item.get("source_url", "")
            source_name = item.get("source_name", "")

            # Skip placeholder / manually-entered / newsletter items.
            # Newsletter items often lack direct source URLs since they
            # are extracted from email digests.
            if item.get("source_origin") in ("manual", "newsletter"):
                continue

            if (
                not source_url
                or source_url in ("None", "null", "")
                or not source_url.startswith("http")
            ):
                bad_sources.append(
                    f"Item {i} ({item.get('id', '?')}): "
                    f"invalid source_url='{source_url}'"
                )
            if not source_name or len(source_name.strip()) == 0:
                bad_sources.append(
                    f"Item {i} ({item.get('id', '?')}): "
                    f"empty source_name"
                )

        self.assertEqual(
            len(bad_sources),
            0,
            f"Items with invalid sources:\n" + "\n".join(bad_sources),
        )


if __name__ == "__main__":
    unittest.main()
