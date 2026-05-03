-- Add 'country' to the entity_logos category whitelist so G20 country
-- flag entries can be inserted. The existing categories stay unchanged.

alter table entity_logos
  drop constraint if exists entity_logos_category_check;

alter table entity_logos
  add constraint entity_logos_category_check
  check (category in (
    'company',
    'university',
    'government',
    'energy',
    'finance',
    'defense',
    'org',
    'model',
    'country',
    'other'
  ));
