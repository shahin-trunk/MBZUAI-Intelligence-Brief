## Database Status Report - Learning Content

### Current State (as of 2026-05-17 11:40 UTC)

**Database Findings:**
- Total briefs in database: **49**
- Briefs with learning content: **0** (NONE)
- Latest brief date: **2026-05-07**
- Latest brief audio_status: **"generating_learning_content"** (stuck in progress)

### Root Cause

The learning content generation pipeline was **started but never completed** for the brief 2026-05-07. The status got stuck at `"generating_learning_content"` which indicates:
1. The pipeline started generating learning content
2. It likely failed or timed out before completion
3. The status was never updated to `"ready"`

All other briefs (2026-05-06 and earlier) have `"ready"` status but also have **no learning content** because they were generated before the ITER 17 improvements.

### What's Missing

For each brief item that should have language learning content:
- `script4` field: **EMPTY** (should contain English teacher narration)
- `grammar` object: **EMPTY** (should have 7 fields: morphology, etymology, conjugation, register, phonetic_guide, usage_notes, cognate_note)
- `audio_url_4`: **EMPTY** (no deep dive audio)

### What's Working

- Scripts 1, 2, 3 have content and audio for existing items
- Audio exclusivity fix is deployed (no overlaps)
- UI components are ready to display script4 and grammar content
- All navigation, playback, and completion flows work correctly

### Action Taken

**Triggered GitHub Actions workflow** to regenerate learning content for brief 2026-05-07:
- Command: `gh workflow run generate-audio.yml -f brief_date=2026-05-07 -f force_regenerate=false`
- Run ID: 25989802538
- Status: **IN PROGRESS**

The workflow will:
1. Read the brief from Supabase
2. Detect existing items with language learning sections
3. Generate phrase-based learning content (v3 pipeline) using Claude
4. Create 4 scripts per phrase (teaching, transition, native, deep grammar)
5. Generate TTS audio for each script
6. Update the database with learning content and audio URLs

### Next Steps

1. **Monitor current workflow** - Wait for completion (~15-30 minutes for 3 phrases x 4 scripts x 2 languages)
2. **Verify database** - Check that script4 and grammar fields are populated
3. **Browser test** - Verify teacher narration plays correctly and grammar drawer shows content
4. **Backfill other briefs** - Run workflow for 2026-05-06, 2026-05-05, etc.

### Code Changes Deployed (ITER 17)

These improvements will take effect on content regeneration:
1. **Enhanced prompt** - Requires rich English teacher narration with word breakdowns
2. **Grammar drawer UI** - Shows script4 as primary content with "Teacher's Deep Dive" section
3. **Audio exclusivity** - Fixed overlapping audio chaos
4. **TTS language hint** - Added `lang` parameter to Argent TTS payload
5. **Bilingual validation** - Ensures >=3 English stop words in teaching scripts
