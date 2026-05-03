-- Migration 018: shrink brief_items to a narrow cross-date index.
--
-- Context: brief_items held duplicate copies of the v2 item payload
-- (key_bullets, analysis, exhibits, primary_entity, primary_entity_category)
-- that were WRITTEN by the curation/approve and edit routes but READ by
-- nothing in the frontend. The reader page uses briefs.raw_json as the
-- source of truth; brief_items is only consumed for cross-date lookups
-- by /api/flags/all, /api/admin/research, and backend/config.py history
-- dedup.
--
-- Any direct DB patch that updated these duplicate columns silently
-- drifted from briefs.raw_json with no user-visible effect (2026-04-19
-- and 2026-04-21 incidents). Removing the duplicates eliminates the
-- drift class.
--
-- raw_content NOT DROPPED: it holds scraped article text from pre-v2
-- briefs (Feb–early Apr 2026) and is not duplicated in briefs.raw_json
-- for those dates. No live code reads it (backend/config.py history
-- dedup already reads briefs.raw_json), but we keep the blob for
-- historical audit — source URLs have since paywalled or 404'd and the
-- data is irrecoverable if dropped. It's a dead column going forward
-- (no writer path touches it), not a drift risk.
--
-- audio_url, topic_relevance, news_significance, geo_lat, geo_lng,
-- geo_label: always-null placeholders across every row. Safe to drop.
--
-- Deploy ordering constraint: this migration MUST run AFTER the three
-- writer paths stop referencing the v2 columns:
--   - frontend/app/api/curation/approve/route.ts  (itemRows shape)
--   - frontend/app/api/briefs/[date]/items/[itemId]/route.ts  (columnMap)
--   - backend/ingest_brief.py  (_build_item_rows)
-- AND after backend/config.py history dedup is migrated off raw_content
-- to read from briefs.raw_json instead.
--
-- Kept on brief_items after this migration (the narrow-index shape):
--   brief_date, item_id, section, section_order, headline,
--   main_bullet, context, implication, source_name, source_url,
--   significance, composite_score, is_continuity, continuity_days,
--   raw_content  -- historical scraped article text, kept for audit

alter table brief_items
  drop column if exists key_bullets,
  drop column if exists analysis,
  drop column if exists exhibits,
  drop column if exists primary_entity,
  drop column if exists primary_entity_category,
  drop column if exists audio_url,
  drop column if exists topic_relevance,
  drop column if exists news_significance,
  drop column if exists geo_lat,
  drop column if exists geo_lng,
  drop column if exists geo_label;
