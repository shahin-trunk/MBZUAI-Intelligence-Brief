-- Persist hybrid curation state and full card-shaped manual items.

alter table pending_items
  add column if not exists selected boolean not null default false,
  add column if not exists curation_order integer,
  add column if not exists primary_entity text,
  add column if not exists exhibits jsonb,
  add column if not exists updated_at timestamptz not null default now();

update pending_items
set
  primary_entity = coalesce(primary_entity, raw_item->>'primary_entity'),
  exhibits = coalesce(exhibits, raw_item->'exhibits'),
  updated_at = coalesce(updated_at, created_at);

create index if not exists idx_pending_items_selected
  on pending_items (pending_brief_id, selected, curation_order);

alter table manual_items
  add column if not exists item_id text,
  add column if not exists composite_score numeric not null default 8,
  add column if not exists key_bullets jsonb,
  add column if not exists analysis text,
  add column if not exists primary_entity text,
  add column if not exists exhibits jsonb,
  add column if not exists raw_item jsonb,
  add column if not exists depth text default 'standard',
  add column if not exists is_model_release boolean not null default false,
  add column if not exists model_release_data jsonb,
  add column if not exists selected boolean not null default true,
  add column if not exists curation_order integer,
  add column if not exists updated_at timestamptz not null default now();

update manual_items
set
  item_id = coalesce(item_id, 'manual-' || substr(id::text, 1, 8)),
  key_bullets = coalesce(key_bullets, case when main_bullet is not null then jsonb_build_array(main_bullet) else null end),
  analysis = coalesce(analysis, nullif(trim(concat_ws(' ', context, implication)), '')),
  raw_item = coalesce(
    raw_item,
    jsonb_build_object(
      'id', 'manual-' || substr(id::text, 1, 8),
      'section', section,
      'headline', headline,
      'main_bullet', main_bullet,
      'context', context,
      'implication', implication,
      'source_name', source_name,
      'source_url', source_url,
      'significance_level', coalesce(significance_level, 'medium'),
      'composite_score', composite_score,
      'depth', coalesce(depth, 'standard'),
      'is_model_release', is_model_release,
      'model_release_data', model_release_data,
      'key_bullets', key_bullets,
      'analysis', analysis,
      'primary_entity', primary_entity,
      'exhibits', exhibits
    )
  ),
  updated_at = coalesce(updated_at, created_at);

alter table manual_items
  alter column item_id set not null;

create unique index if not exists idx_manual_items_brief_item_id
  on manual_items (pending_brief_id, item_id);

create index if not exists idx_manual_items_selected
  on manual_items (pending_brief_id, selected, curation_order);
