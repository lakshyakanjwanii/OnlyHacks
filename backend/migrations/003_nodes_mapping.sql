-- =====================================================================
-- Nodes → Org mapping
-- Run AFTER 001_init_schema.sql and 002_rls_policies.sql
--
-- WHY: scan_events.node_id is a free-text code (e.g. 'CIPLA-FACTORY-MUM',
-- 'DISTRICT-HOSPITAL-NASHIK'). The original RLS policies matched this
-- directly against profiles.org_name, which breaks the moment a node's
-- display name and its profile's org_name diverge even slightly (typos,
-- renames, multiple nodes per org, etc). This migration adds an explicit
-- nodes table so a node_id maps to exactly one org_id, and RLS can join
-- on that instead of string-matching two independently-edited text
-- fields.
-- =====================================================================

-- ---------------------------------------------------------------------
-- nodes — canonical registry of every physical/logical node that can
-- appear in scan_events.node_id (factory, warehouse, hospital, vendor
-- location, etc), mapped to the org that owns/operates it.
-- ---------------------------------------------------------------------
create table nodes (
    id          uuid primary key default uuid_generate_v4(),
    node_type   node_type_enum not null,
    node_id     text not null unique,   -- matches scan_events.node_id exactly
    org_id      uuid not null,          -- matches profiles.org_id
    label       text,                   -- human-readable name, e.g. 'District Hospital, Nashik'
    created_at  timestamptz not null default now()
);

create index idx_nodes_org_id on nodes(org_id);
create index idx_nodes_node_id on nodes(node_id);

alter table nodes enable row level security;

-- Readable by everyone authenticated (it's reference/master data, not
-- sensitive) — needed so RLS subqueries on other tables can join
-- against it regardless of caller role.
create policy nodes_select on nodes for select
  using (auth.role() = 'authenticated');

-- Only state/district can register or edit nodes.
create policy nodes_insert on nodes for insert
  with check (auth_role() in ('state', 'district'));

create policy nodes_update on nodes for update
  using (auth_role() in ('state', 'district'));

-- ---------------------------------------------------------------------
-- Backfill: seed one node per distinct node_id already used in
-- scan_events / seed data, mapped to org_id NULL placeholder — teams
-- should update org_id for each row once real orgs/profiles exist.
-- Safe to run even if scan_events is empty (inserts nothing).
-- ---------------------------------------------------------------------
insert into nodes (node_type, node_id, org_id, label)
select distinct se.node_type, se.node_id, uuid_nil(), se.node_id
from scan_events se
where not exists (select 1 from nodes n where n.node_id = se.node_id)
on conflict (node_id) do nothing;