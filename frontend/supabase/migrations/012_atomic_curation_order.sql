-- Atomic "select and assign next curation_order" for either table.
-- Eliminates the race where concurrent PUTs to /api/curation/items/[itemId]
-- all read the same max(curation_order) and produce duplicates.
--
-- Uses a per-brief advisory lock so concurrent selections across the same
-- brief serialize on the server side; different briefs don't contend.
create or replace function assign_curation_order(
  p_table text,
  p_item_id uuid,
  p_brief_id uuid
) returns integer
language plpgsql
as $$
declare
  v_next integer;
  v_brief_key bigint;
begin
  -- Per-brief advisory lock (stable across transactions for the same brief).
  v_brief_key := ('x' || substr(md5(p_brief_id::text), 1, 16))::bit(64)::bigint;
  perform pg_advisory_xact_lock(v_brief_key);

  select coalesce(max(curation_order), 0) + 1
    into v_next
    from (
      select curation_order from pending_items
        where pending_brief_id = p_brief_id and selected = true
      union all
      select curation_order from manual_items
        where pending_brief_id = p_brief_id and selected = true
    ) s;

  if p_table = 'pending_items' then
    update pending_items
      set selected = true,
          curation_order = v_next,
          updated_at = now()
      where id = p_item_id
        and pending_brief_id = p_brief_id;
  elsif p_table = 'manual_items' then
    update manual_items
      set selected = true,
          curation_order = v_next,
          updated_at = now()
      where id = p_item_id
        and pending_brief_id = p_brief_id;
  else
    raise exception 'assign_curation_order: invalid table %', p_table;
  end if;

  return v_next;
end;
$$;

grant execute on function assign_curation_order(text, uuid, uuid) to authenticated, service_role;
