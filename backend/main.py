#!/usr/bin/env python3
"""Intelligence Dashboard — Pipeline Entry Point.

Runs the full intelligence briefing pipeline:
  Collect -> triage/date checks/dedup/content filter -> Gatekeeper ->
  Ghostwriter -> draft ingest for analyst curation.

In normal production, PIPELINE_DRAFT_MODE defaults to true, so the pipeline
writes a draft slate into pending_briefs/pending_items. The Editor/final JSON
path only runs when PIPELINE_DRAFT_MODE=false for maintenance/backfill flows.

Usage:
  python3.11 main.py                            # Full pipeline
  python3.11 main.py --from-stage content_filter  # Resume from content filter
  python3.11 main.py --from-stage ghostwriter   # Resume from ghostwriter
  python3.11 main.py --from-stage editor        # Legacy direct-publish path only
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from config import ANTHROPIC_API_KEY

LOG_PATH = Path(__file__).resolve().parent / "pipeline.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)


def _require_python_310_plus() -> None:
    """Fail fast when the runtime is too old for the type syntax used below."""
    if sys.version_info < (3, 10):
        print("ERROR: main.py requires Python 3.10+.")
        sys.exit(1)


def main():
    _require_python_310_plus()

    parser = argparse.ArgumentParser(description="Intelligence Dashboard Pipeline")
    parser.add_argument(
        "--from-stage",
        choices=["scout", "content_filter", "gatekeeper", "ghostwriter", "editor"],
        default=None,
        help="Resume from a specific stage using cached intermediate outputs.",
    )
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set. Check your .env file.")
        sys.exit(1)

    from pipeline.orchestrator import run_pipeline

    try:
        ok = asyncio.run(run_pipeline(from_stage=args.from_stage))
        if not ok:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"ERROR: Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
