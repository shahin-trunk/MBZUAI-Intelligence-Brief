"""Collector health smoke tests.

Runs each collector individually and verifies it returns items.
Skips gracefully when credentials are not available (CollectorSkipped).

Usage:
    cd backend && python -m pytest tests/test_collector_health.py -v
    cd backend && python tests/test_collector_health.py
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.collector import (
    CollectorSkipped,
    collect_wam,
    collect_admo,
    collect_tii,
    collect_g42,
    collect_khazna,
    collect_presight,
)

DUBAI_TZ = ZoneInfo("Asia/Dubai")


def _run_collector(func):
    """Run a sync collector, re-raising CollectorSkipped as-is."""
    return func()


class CollectorHealthTests(unittest.TestCase):
    """Smoke tests: each collector returns at least one item."""

    def _assert_collector_returns_items(self, func):
        try:
            items = _run_collector(func)
        except CollectorSkipped:
            self.skipTest("credentials not available")
        self.assertGreater(len(items), 0, f"{func.__name__} returned no items")

    def test_wam_returns_items(self):
        self._assert_collector_returns_items(collect_wam)

    def test_admo_returns_items(self):
        self._assert_collector_returns_items(collect_admo)

    def test_tii_returns_items(self):
        self._assert_collector_returns_items(collect_tii)

    def test_g42_returns_items(self):
        self._assert_collector_returns_items(collect_g42)

    def test_khazna_returns_items(self):
        self._assert_collector_returns_items(collect_khazna)

    def test_presight_returns_items(self):
        self._assert_collector_returns_items(collect_presight)


class StaleFeedDetectionTests(unittest.TestCase):
    """Detect stale feeds by checking that scraped items have recent dates."""

    # Fixed-count scrapers that should always have fresh content
    FIXED_COUNT_SCRAPERS = {
        "admo": collect_admo,
        "tii": collect_tii,
        "g42": collect_g42,
        "khazna": collect_khazna,
    }

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse YYYY-MM-DD date string into a datetime."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=DUBAI_TZ
            )
        except ValueError:
            return None

    def test_fixed_count_scrapers_have_recent_dates(self):
        """At least 30% of items from each fixed-count scraper should have
        dates within the last 14 days."""
        now = datetime.now(DUBAI_TZ)
        cutoff = now - timedelta(days=14)

        for name, func in self.FIXED_COUNT_SCRAPERS.items():
            with self.subTest(collector=name):
                try:
                    items = _run_collector(func)
                except CollectorSkipped:
                    self.skipTest(f"{name}: credentials not available")

                if not items:
                    self.skipTest(f"{name}: returned no items")

                dated_items = [
                    it for it in items if self._parse_date(it.published_date)
                ]
                if not dated_items:
                    self.skipTest(f"{name}: no items have parseable dates")

                recent = [
                    it
                    for it in dated_items
                    if self._parse_date(it.published_date) >= cutoff
                ]
                pct = len(recent) / len(dated_items)
                self.assertGreaterEqual(
                    pct,
                    0.30,
                    f"{name}: only {pct:.0%} of dated items are within "
                    f"14 days (expected >= 30%)",
                )


if __name__ == "__main__":
    unittest.main()
