-- 014_add_primary_entity_category.sql
--
-- Adds `primary_entity_category` to brief_items and pending_items so the
-- frontend can render an industry-appropriate lucide-react icon when the
-- entity doesn't have a curated logo in entity_logos.
--
-- The category is populated by the new Entity Classifier pipeline stage
-- (backend/pipeline/entity_classifier.py) using Haiku 4.5. It reuses the
-- exact 10-value enum already on entity_logos.category (migrations 008
-- + 013) so the frontend can treat either source interchangeably.
--
-- Nullable — historical rows and classifier failures render as null and
-- fall back to the generic HelpCircle icon.

alter table brief_items
  add column if not exists primary_entity_category text
    check (primary_entity_category in (
      'company','university','government','energy','finance',
      'defense','org','model','country','other'
    ));

alter table pending_items
  add column if not exists primary_entity_category text
    check (primary_entity_category in (
      'company','university','government','energy','finance',
      'defense','org','model','country','other'
    ));

comment on column brief_items.primary_entity_category is
  'One of 10 entity_logos.category values, populated by the Entity Classifier stage. Used by the frontend to pick an industry-appropriate icon when primary_entity has no logo.';

comment on column pending_items.primary_entity_category is
  'One of 10 entity_logos.category values, populated by the Entity Classifier stage. Used by the frontend to pick an industry-appropriate icon when primary_entity has no logo.';
