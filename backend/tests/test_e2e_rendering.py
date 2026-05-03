"""
E2E Rendering Tests: Fixture injection → Supabase verification → Live pipeline test.

Run:
    cd backend
    source ../.env; source ../frontend/.env.local
    python3.11 -m pytest tests/test_e2e_rendering.py -v -s

These tests inject data into Supabase and clean up after themselves.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from env_loader import load_project_env
# Load env early so all imports that rely on env vars work
for _p in load_project_env():
    pass

from tests.inject_test_brief import _build_brief_row, _build_item_rows, _get_client

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
OUTPUT_DIR = BACKEND_DIR / "output"
TEST_DATE_FIXTURE = "2026-12-25"
TEST_DATE_PIPELINE = "2026-12-26"


def _supabase_available() -> bool:
    return bool(os.getenv("NEXT_PUBLIC_SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _api_keys_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") and os.getenv("SERPER_API_KEY"))


skip_no_supabase = pytest.mark.skipif(not _supabase_available(), reason="Supabase credentials not set")
skip_no_api = pytest.mark.skipif(not _api_keys_available(), reason="ANTHROPIC_API_KEY or SERPER_API_KEY not set")


# ---------------------------------------------------------------------------
# Fixture injection tests
# ---------------------------------------------------------------------------


class TestFixtureInjection:
    """Inject the rich fixture brief and verify it round-trips through Supabase."""

    @skip_no_supabase
    def test_inject_and_verify_fixture(self):
        fixture_path = FIXTURES_DIR / f"brief_{TEST_DATE_FIXTURE}.json"
        assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        sb = _get_client()

        try:
            # Inject
            brief_row = _build_brief_row(fixture)
            sb.table("briefs").upsert(brief_row, on_conflict="brief_date").execute()

            sb.table("brief_items").delete().eq("brief_date", TEST_DATE_FIXTURE).execute()
            item_rows = _build_item_rows(fixture)
            sb.table("brief_items").insert(item_rows).execute()

            # Verify brief row
            resp = sb.table("briefs").select("*").eq("brief_date", TEST_DATE_FIXTURE).execute()
            assert resp.data and len(resp.data) == 1, "Expected 1 brief row"
            brief = resp.data[0]
            raw_json = brief["raw_json"]
            assert raw_json["brief_metadata"]["total_items"] == 8
            assert len(raw_json["items"]) == 8

            # Verify brief_items rows
            resp = sb.table("brief_items").select("*").eq("brief_date", TEST_DATE_FIXTURE).execute()
            items = resp.data
            assert len(items) == 8, f"Expected 8 brief_items, got {len(items)}"

            # Verify model release items
            mr_items = [i for i in items if i.get("raw_content", {}).get("is_model_release")]
            assert len(mr_items) >= 3, f"Expected >=3 model release items, got {len(mr_items)}"

            # Verify exhibits preserved in raw_json
            items_with_exhibits = [
                i for i in raw_json["items"]
                if i.get("exhibits") and len(i["exhibits"]) > 0
            ]
            assert len(items_with_exhibits) >= 5, (
                f"Expected >=5 items with exhibits in raw_json, got {len(items_with_exhibits)}"
            )

            # Verify exhibit types
            exhibit_types_found = set()
            for item in raw_json["items"]:
                for ex in item.get("exhibits") or []:
                    exhibit_types_found.add(ex["type"])
            expected_types = {"benchmark_table", "metric_highlight", "timeline", "comparison_table", "raw_image"}
            assert expected_types == exhibit_types_found, (
                f"Missing exhibit types: {expected_types - exhibit_types_found}"
            )

            # Verify model_release_data in raw_json
            for item in raw_json["items"]:
                if item.get("is_model_release"):
                    mrd = item.get("model_release_data")
                    assert mrd is not None, f"model_release_data missing for {item['headline'][:50]}"
                    assert mrd.get("developer"), f"Empty developer for {item['headline'][:50]}"
                    assert mrd.get("model_name"), f"Empty model_name for {item['headline'][:50]}"

            # Verify new-format vs legacy-format model releases
            new_format_items = [
                i for i in raw_json["items"]
                if i.get("is_model_release") and i.get("model_release_data", {}).get("summary_pitch")
            ]
            legacy_format_items = [
                i for i in raw_json["items"]
                if i.get("is_model_release")
                and not i.get("model_release_data", {}).get("summary_pitch")
                and i.get("model_release_data", {}).get("specs")
            ]
            assert len(new_format_items) >= 2, f"Expected >=2 new-format model releases, got {len(new_format_items)}"
            assert len(legacy_format_items) >= 1, f"Expected >=1 legacy-format model release, got {len(legacy_format_items)}"

            # Verify benchmark data shapes
            for item in raw_json["items"]:
                mrd = item.get("model_release_data") or {}
                benchmarks = mrd.get("benchmarks")
                if benchmarks:
                    assert isinstance(benchmarks.get("models"), list), "benchmarks.models should be a list"
                    for row in benchmarks.get("rows", []):
                        assert isinstance(row.get("scores"), list), (
                            f"model_release_data benchmarks.rows[].scores should be array: {item['headline'][:40]}"
                        )

                for ex in item.get("exhibits") or []:
                    if ex["type"] == "benchmark_table":
                        for row in ex["data"].get("rows", []):
                            assert isinstance(row.get("scores"), dict), (
                                f"exhibit benchmark_table rows[].scores should be dict: {item['headline'][:40]}"
                            )

            # Verify multi-exhibit item
            multi_exhibit_items = [
                i for i in raw_json["items"]
                if len(i.get("exhibits") or []) >= 2
            ]
            assert len(multi_exhibit_items) >= 1, "Expected at least 1 item with multiple exhibits"

            print(f"\n  ALL CHECKS PASSED")
            print(f"  Brief {TEST_DATE_FIXTURE}: {len(raw_json['items'])} items")
            print(f"  Exhibit types: {sorted(exhibit_types_found)}")
            print(f"  Model releases: {len(mr_items)} (new: {len(new_format_items)}, legacy: {len(legacy_format_items)})")
            print(f"  Items with exhibits: {len(items_with_exhibits)}")
            print(f"  Multi-exhibit items: {len(multi_exhibit_items)}")
            print(f"\n  View at: http://localhost:3000/brief/{TEST_DATE_FIXTURE}")

        finally:
            # Cleanup
            sb.table("brief_items").delete().eq("brief_date", TEST_DATE_FIXTURE).execute()
            sb.table("briefs").delete().eq("brief_date", TEST_DATE_FIXTURE).execute()


# ---------------------------------------------------------------------------
# Live pipeline test
# ---------------------------------------------------------------------------


class TestLivePipelineToRendering:
    """Run enrichment + ghostwriter + editor on a real item, ingest, and verify."""

    @skip_no_supabase
    @skip_no_api
    @pytest.mark.asyncio
    async def test_live_pipeline_model_release(self):
        import anthropic
        from pipeline.enricher import enrich_item
        from pipeline.ghostwriter import run_ghostwriter
        from pipeline.model_release import build_model_release_packet
        from prompts.loader import extract_prompt_from_md
        from config import PROMPTS_DIR

        # Load a real model release item from cached data
        gatekeeper_file = OUTPUT_DIR / "enriched_gatekeeper_output_2026-04-09.json"
        if not gatekeeper_file.exists():
            gatekeeper_file = OUTPUT_DIR / "gatekeeper_output_2026-04-09.json"
        if not gatekeeper_file.exists():
            pytest.skip("No April 9 gatekeeper output available")

        data = json.loads(gatekeeper_file.read_text(encoding="utf-8"))
        selected = data.get("selected", [])
        mr_items = [
            i for i in selected
            if "model release" in i.get("brief_section", "").lower()
        ]
        if not mr_items:
            pytest.skip("No model release items in April 9 data")

        source_item = copy.deepcopy(mr_items[0])
        source_item.pop("_enrichment", None)
        source_item.pop("enriched_sources", None)
        source_item.pop("benchmark_facts", None)
        source_item.pop("key_number_facts", None)
        source_item.pop("coverage_notes", None)

        print(f"\n  Source item: {source_item.get('headline', '')[:80]}")

        # Step 1: Enrich
        client = anthropic.AsyncAnthropic()
        enriched = await enrich_item(source_item, client)
        packet = build_model_release_packet(enriched)
        enriched["benchmark_facts"] = packet["benchmark_facts"]
        enriched["key_number_facts"] = packet["key_number_facts"]
        enriched["coverage_notes"] = packet.get("coverage_notes", [])
        enriched["compiled_packet"] = packet

        print(f"  Enrichment: {len(packet['benchmark_facts'])} benchmark facts, "
              f"{len(packet['key_number_facts'])} key numbers")

        # Step 2: Ghostwriter
        enriched.setdefault("source", enriched.get("source_name", "Unknown"))
        enriched.setdefault("date", "2026-04-09")
        enriched.setdefault("date_evidence", "April 9, 2026")
        enriched.setdefault("topic_relevance", 0.9)
        enriched.setdefault("news_significance", 0.9)
        enriched.setdefault("selection_rationale", "Model release")

        gatekeeper_output = {
            "selected": [enriched],
            "dropped": [],
            "brief_summary": {
                "total_input_items": 1,
                "selected": 1,
                "dropped": 0,
                "section_distribution": {"Model Releases & Technical Developments": 1},
            },
        }

        prompt_text = extract_prompt_from_md(
            (PROMPTS_DIR / "ghostwriter_prompt.md").read_text(encoding="utf-8")
        )
        prompt_text = prompt_text.replace("{gatekeeper_output}", json.dumps(gatekeeper_output, indent=2))
        prompt_text = prompt_text.replace("{date}", TEST_DATE_PIPELINE)
        prompt_text = prompt_text.replace("{user_profile}", "Prof. Eric Xing, President of MBZUAI")
        prompt_text = prompt_text.replace("{previous_brief}", "No previous brief available.")

        gw_result, gw_usage = await run_ghostwriter(client, prompt_text)
        gw_items = gw_result.get("items", [])
        assert len(gw_items) >= 1, "Ghostwriter should produce at least 1 item"

        print(f"  Ghostwriter: {len(gw_items)} items produced")

        mr_gw = [i for i in gw_items if i.get("is_model_release")]
        if mr_gw:
            mrd = mr_gw[0].get("model_release_data", {})
            benchmarks = mrd.get("benchmarks", {})
            exhibits = mr_gw[0].get("exhibits", [])
            print(f"  Model release data: developer={mrd.get('developer')}, "
                  f"model={mrd.get('model_name')}")
            print(f"  Benchmarks: {len(benchmarks.get('rows', []))} rows")
            print(f"  Key numbers: {len(mrd.get('key_numbers', []))}")
            print(f"  Exhibits: {len(exhibits)} ({[e['type'] for e in exhibits]})")

        # Build a brief from ghostwriter output
        gw_result["date"] = TEST_DATE_PIPELINE
        brief = {
            "brief_metadata": {
                "date": TEST_DATE_PIPELINE,
                "generated_at": "2026-12-26T06:00:00+04:00",
                "total_items": len(gw_items),
                "section_counts": {},
                "lead_story_id": gw_items[0]["id"] if gw_items else "unknown",
            },
            "items": gw_items,
        }

        # Ingest into Supabase
        sb = _get_client()
        try:
            brief_row = _build_brief_row(brief)
            sb.table("briefs").upsert(brief_row, on_conflict="brief_date").execute()

            sb.table("brief_items").delete().eq("brief_date", TEST_DATE_PIPELINE).execute()
            item_rows = _build_item_rows(brief)
            if item_rows:
                sb.table("brief_items").insert(item_rows).execute()

            # Verify ingestion
            resp = sb.table("briefs").select("raw_json").eq("brief_date", TEST_DATE_PIPELINE).execute()
            assert resp.data and len(resp.data) == 1
            stored_items = resp.data[0]["raw_json"]["items"]

            stored_mr = [i for i in stored_items if i.get("is_model_release")]
            print(f"\n  INGESTED: {len(stored_items)} items for {TEST_DATE_PIPELINE}")
            print(f"  Model releases: {len(stored_mr)}")
            if stored_mr:
                mrd = stored_mr[0].get("model_release_data", {})
                print(f"  First MR: {mrd.get('developer')} / {mrd.get('model_name')}")
                benchmarks = mrd.get("benchmarks", {})
                print(f"  Benchmarks: {len(benchmarks.get('rows', []))} rows")
                print(f"  Key numbers: {len(mrd.get('key_numbers', []))}")
                exhibits = stored_mr[0].get("exhibits", [])
                print(f"  Exhibits: {len(exhibits)}")

            print(f"\n  View at: http://localhost:3000/brief/{TEST_DATE_PIPELINE}")

        finally:
            sb.table("brief_items").delete().eq("brief_date", TEST_DATE_PIPELINE).execute()
            sb.table("briefs").delete().eq("brief_date", TEST_DATE_PIPELINE).execute()
